from __future__ import annotations

import argparse
import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any
from enum import Enum

import faiss
import numpy as np
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI
from pymongo import MongoClient, ReturnDocument
from bson import ObjectId

# Disable CrewAI interactive tracing prompt that causes timeout in containerized environments
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

from crewai.events import (
    CrewKickoffCompletedEvent,
    CrewKickoffFailedEvent,
    CrewKickoffStartedEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
    crewai_event_bus,
)
from finance_insight_service.crew import FinanceInsightCrew


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# In-memory job storage (for production, use Redis or database)
jobs = {}
jobs_lock = threading.Lock()


def _utc_now() -> datetime:
    return datetime.utcnow()


def _trim_text(value: str, limit: int = 400) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=True)


def _simplify_trace(event: dict[str, Any]) -> str:
    """Convert trace event to human-readable message with detailed context."""
    event_type = event.get("type")
    agent = event.get("agent", "")
    
    if event_type == "crew_started":
        return "Starting analysis"
    
    if event_type == "crew_completed":
        return "Analysis complete"
    
    if event_type == "task_started":
        task = event.get("task", "task")
        if agent:
            return f"Agent '{agent}' is working on {task}"
        return f"Working on: {task}"
    
    if event_type == "task_completed":
        task = event.get("task", "task")
        output = event.get("output", {})
        
        # Parse output if it's a JSON string
        task_result = output
        if isinstance(output, str):
            try:
                task_result = json.loads(output)
            except:
                task_result = {}
        
        # Audit task completion - show status and reason
        if "audit" in task.lower():
            if isinstance(task_result, dict):
                status = task_result.get("audit_status", "")
                issues = task_result.get("issues", [])
                
                if status:
                    msg = f"Audit {status.lower()}"
                    # Add first issue if rejected/partial
                    if issues and status in ["REJECTED", "PARTIAL"]:
                        first_issue = issues[0] if isinstance(issues[0], dict) else {}
                        problem = first_issue.get("problem", "")
                        if problem:
                            msg += f" - {problem[:80]}"
                    return msg
        
        # Planner task completion - show selected tools
        if "plan" in task.lower() or "manager" in task.lower():
            if isinstance(task_result, dict):
                plan = task_result.get("plan", {})
                if isinstance(plan, dict):
                    selected_tools = []
                    if plan.get("use_research"):
                        selected_tools.append("Research")
                    if plan.get("use_quant"):
                        selected_tools.append("Quant")
                    if plan.get("use_audit"):
                        selected_tools.append("Audit")
                    
                    if selected_tools:
                        return f"Plan ready → Using: {', '.join(selected_tools)}"
        
        # Default task completion
        if agent:
            return f"Agent '{agent}' completed {task}"
        return f"Completed: {task}"
    
    if event_type == "tool_started":
        tool = event.get("tool", "")
        args = event.get("args", {})
        agent_prefix = f"{agent} is " if agent else "Agent is "
        
        # Web scraping/reading tools
        if "scrape" in tool.lower() or "website" in tool.lower() or "read" in tool.lower():
            url = args.get("url", args.get("website_url", ""))
            if url:
                # Extract clean domain from URL
                domain = url.split('/')[2] if '://' in url else url.split('/')[0]
                # Remove www. prefix
                domain = domain.replace('www.', '')
                return f"{agent_prefix}reading from {domain}"
            return f"{agent_prefix}reading website content"
        
        # Search tools
        if "search" in tool.lower() or "serp" in tool.lower():
            query = args.get("query", args.get("search_query", ""))
            if query:
                return f"{agent_prefix}searching web: '{query[:60]}'"
            return f"{agent_prefix}searching the web"
        
        # Fundamentals tools
        if "fundamentals" in tool.lower():
            ticker = args.get("ticker", args.get("symbol", ""))
            if ticker:
                return f"{agent_prefix}analyzing fundamentals for {ticker}"
            return f"{agent_prefix}fetching financial data"
        
        # Market data tools
        if "market" in tool.lower() or "price" in tool.lower():
            ticker = args.get("ticker", args.get("symbol", ""))
            if ticker:
                return f"{agent_prefix}getting market data for {ticker}"
            return f"{agent_prefix}fetching market data"
        
        return f"{agent_prefix}using {tool}"
    
    if event_type == "tool_completed":
        tool = event.get("tool", "")
        output = event.get("output", {})
        args = event.get("args", {})
        
        # Web scraping completion
        if "scrape" in tool.lower() or "website" in tool.lower() or "read" in tool.lower():
            url = args.get("url", args.get("website_url", ""))
            if url:
                # Extract clean domain name
                domain = url.split('/')[2] if '://' in url else url.split('/')[0]
                # Remove www. prefix for cleaner display
                domain = domain.replace('www.', '')
                return f"Completed reading from {domain}"
            return "Website content retrieved"
        
        # Search completion
        if "search" in tool.lower() or "serp" in tool.lower():
            if isinstance(output, dict):
                results = output.get("results", [])
                if results and len(results) > 0:
                    # Try to get first result title/snippet
                    first_result = results[0] if isinstance(results[0], dict) else {}
                    title = first_result.get("title", first_result.get("name", ""))
                    snippet = first_result.get("snippet", first_result.get("description", ""))
                    
                    msg = f"Found {len(results)} results"
                    if title:
                        msg += f" → Top: {title[:150]}"
                    elif snippet:
                        msg += f" → {snippet[:150]}"
                    return msg
            return "Web search completed"
        
        # Fundamentals completion
        if "fundamentals" in tool.lower():
            ticker = args.get("ticker", args.get("symbol", ""))
            msg = "Retrieved financial data"
            if ticker:
                msg += f" for {ticker}"
            
            # Try to extract key metrics from output
            if isinstance(output, dict):
                metrics = []
                # Look for common financial metrics
                if "output_preview" in output:
                    preview = str(output["output_preview"])[:80]
                    if preview:
                        msg += f" → {preview}..."
                        return msg
                        
                for key in ["market_cap", "pe_ratio", "revenue", "eps", "price"]:
                    if key in output and output[key]:
                        metrics.append(f"{key.replace('_', ' ')}: {output[key]}")
                if metrics:
                    msg += f" → {', '.join(metrics[:2])}"
            return msg
        
        # Market data completion
        if "market" in tool.lower() or "price" in tool.lower():
            ticker = args.get("ticker", args.get("symbol", ""))
            msg = "Retrieved market data"
            if ticker:
                msg += f" for {ticker}"
            
            if isinstance(output, dict):
                # Try to extract price/data info
                if "output_preview" in output:
                    preview = str(output["output_preview"])[:80]
                    if preview:
                        msg += f" → {preview}..."
                        return msg
                        
                price = output.get("price", output.get("last_price", output.get("close", "")))
                if price:
                    msg += f" → Price: {price}"
            return msg
        
        # Generic tool completion with output preview
        msg = f"Completed {tool}"
        if isinstance(output, dict) and "output_preview" in output:
            preview = str(output["output_preview"])[:200]
            if preview:
                msg += f" → {preview}"
        elif isinstance(output, str) and output.strip():
            preview = output.strip()[:200]
            msg += f" → {preview}"
        
        return msg
    
    # Fallback
    return event.get("summary", "Processing")


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value).strip()]


def _build_search_query(query: str, tickers: Any, sites: Any) -> str:
    parts = [query.strip()] if query.strip() else []
    tickers_list = _normalize_list(tickers)
    if tickers_list:
        parts.append("(" + " OR ".join(tickers_list) + ")")
    sites_list = _normalize_list(sites)
    if sites_list:
        parts.append("(" + " OR ".join(f"site:{s}" for s in sites_list) + ")")
    return " ".join(parts).strip()


class MongoStore:
    def __init__(self, uri: str, db_name: str) -> None:
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self.threads = self.db["threads"]
        self.messages = self.db["messages"]
        self.traces = self.db["traces"]
        self.embeddings = self.db["embeddings"]
        self.meta = self.db["meta"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.threads.create_index("threadId", unique=True)
        self.threads.create_index("updatedAt")
        self.messages.create_index("threadId")
        self.messages.create_index("createdAt")
        self.traces.create_index("threadId")
        self.traces.create_index("createdAt")
        self.embeddings.create_index("vector_id", unique=True)
        self.embeddings.create_index("threadId")

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def create_thread(self, title: str) -> str:
        now = _utc_now()
        thread_oid = ObjectId()
        thread_id = str(thread_oid)
        self.threads.insert_one(
            {
                "_id": thread_oid,
                "threadId": thread_id,
                "title": title,
                "createdAt": now,
                "updatedAt": now,
                "summary": "",
            }
        )
        return thread_id

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        return self.threads.find_one({"threadId": thread_id})

    def update_thread_summary(self, thread_id: str, summary: str) -> None:
        self.threads.update_one(
            {"threadId": thread_id},
            {"$set": {"summary": summary, "updatedAt": _utc_now()}},
        )

    def touch_thread(self, thread_id: str) -> None:
        self.threads.update_one(
            {"threadId": thread_id},
            {"$set": {"updatedAt": _utc_now()}},
        )

    def add_message(
        self, thread_id: str, role: str, content: str, metadata: dict[str, Any] | None
    ) -> str:
        now = _utc_now()
        result = self.messages.insert_one(
            {
                "threadId": thread_id,
                "role": role,
                "content": content,
                "createdAt": now,
                "metadata": metadata or {},
            }
        )
        self.touch_thread(thread_id)
        return str(result.inserted_id)

    def list_messages(
        self, thread_id: str, limit: int = 30, newest_first: bool = False
    ) -> list[dict[str, Any]]:
        sort_order = -1 if newest_first else 1
        cursor = (
            self.messages.find({"threadId": thread_id})
            .sort("createdAt", sort_order)
            .limit(limit)
        )
        return list(cursor)

    def latest_thread(self) -> dict[str, Any] | None:
        return self.threads.find_one(sort=[("updatedAt", -1)])

    def list_recent_messages(self, limit: int = 30) -> list[dict[str, Any]]:
        cursor = self.messages.find().sort("createdAt", -1).limit(limit)
        messages = list(cursor)
        return list(reversed(messages))

    def add_trace(self, thread_id: str, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload["threadId"] = thread_id
        payload["createdAt"] = _utc_now()
        self.traces.insert_one(payload)

    def list_traces(self, thread_id: str, limit: int = 300) -> list[dict[str, Any]]:
        cursor = (
            self.traces.find({"threadId": thread_id})
            .sort("createdAt", 1)
            .limit(limit)
        )
        return list(cursor)

    def next_vector_id(self) -> int:
        doc = self.meta.find_one_and_update(
            {"_id": "vector_seq"},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(doc.get("value", 0))

    def save_embedding_meta(self, vector_id: int, message_id: str, thread_id: str) -> None:
        self.embeddings.insert_one(
            {
                "vector_id": vector_id,
                "message_id": message_id,
                "threadId": thread_id,
                "createdAt": _utc_now(),
            }
        )

    def fetch_embedding_meta(
        self, vector_ids: list[int], thread_id: str
    ) -> list[dict[str, Any]]:
        if not vector_ids:
            return []
        cursor = self.embeddings.find(
            {"vector_id": {"$in": vector_ids}, "threadId": thread_id}
        )
        return list(cursor)

    def fetch_messages_by_ids(self, message_ids: list[str]) -> list[dict[str, Any]]:
        if not message_ids:
            return []
        cursor = self.messages.find({"_id": {"$in": [ObjectId(m) for m in message_ids]}})
        return list(cursor)


class FaissIndex:
    def __init__(self, index_path: str) -> None:
        self.index_path = index_path
        self.lock = threading.Lock()
        self.index: faiss.Index | None = None
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)

    def _init(self, dim: int) -> None:
        base = faiss.IndexFlatIP(dim)
        self.index = faiss.IndexIDMap2(base)

    def add(self, vector_id: int, vector: np.ndarray) -> None:
        with self.lock:
            if self.index is None:
                self._init(vector.shape[1])
            self.index.add_with_ids(vector, np.array([vector_id], dtype=np.int64))
            faiss.write_index(self.index, self.index_path)

    def search(self, vector: np.ndarray, top_k: int) -> tuple[list[int], list[float]]:
        with self.lock:
            if self.index is None or self.index.ntotal == 0:
                return [], []
            scores, ids = self.index.search(vector, top_k)
        return ids[0].tolist(), scores[0].tolist()


class MemoryManager:
    def __init__(self, store: MongoStore) -> None:
        self.store = store
        self.embed_model = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_client = OpenAI(api_key=self.api_key) if self.api_key else None
        data_dir = os.getenv("FAISS_DATA_DIR", "data")
        os.makedirs(data_dir, exist_ok=True)
        index_path = os.getenv("FAISS_INDEX_PATH", os.path.join(data_dir, "faiss.index"))
        self.index = FaissIndex(index_path)

    def _embed(self, text: str) -> np.ndarray | None:
        if not text.strip():
            return None
        if not self.openai_client:
            return None
        try:
            response = self.openai_client.embeddings.create(
                model=self.embed_model,
                input=[text],
            )
        except Exception:
            return None
        vector = np.array([response.data[0].embedding], dtype=np.float32)
        faiss.normalize_L2(vector)
        return vector

    def add_message_embedding(self, message_id: str, thread_id: str, content: str) -> None:
        vector = self._embed(content)
        if vector is None:
            return
        vector_id = self.store.next_vector_id()
        self.index.add(vector_id, vector)
        self.store.save_embedding_meta(vector_id, message_id, thread_id)

    def search_related(
        self, thread_id: str, query: str, top_k: int = 6
    ) -> list[dict[str, Any]]:
        vector = self._embed(query)
        if vector is None:
            return []
        ids, scores = self.index.search(vector, top_k)
        ids = [int(val) for val in ids if val != -1]
        meta = self.store.fetch_embedding_meta(ids, thread_id)
        meta_map = {m["vector_id"]: m for m in meta}
        message_ids = [m["message_id"] for m in meta]
        messages = self.store.fetch_messages_by_ids(message_ids)
        message_map = {str(m["_id"]): m for m in messages}
        results = []
        for vector_id, score in zip(ids, scores, strict=False):
            meta_item = meta_map.get(vector_id)
            if not meta_item:
                continue
            message = message_map.get(meta_item["message_id"])
            if not message:
                continue
            results.append(
                {
                    "message_id": meta_item["message_id"],
                    "role": message.get("role"),
                    "content": message.get("content"),
                    "score": score,
                }
            )
        return results

    def build_summary(self, thread_id: str, query: str) -> str:
        recent = self.store.list_messages(thread_id, limit=6, newest_first=True)
        recent = list(reversed(recent))
        related = self.search_related(thread_id, query, top_k=6)
        seen = set()
        lines = []
        if recent:
            lines.append("Recent messages:")
            for msg in recent:
                msg_id = str(msg.get("_id"))
                seen.add(msg_id)
                content = _trim_text(str(msg.get("content", "")), 240)
                lines.append(f"- {msg.get('role')}: {content}")
        if related:
            lines.append("Relevant past context:")
            for item in related:
                if item["message_id"] in seen:
                    continue
                content = _trim_text(str(item.get("content", "")), 200)
                lines.append(f"- {item.get('role')}: {content}")
        return "\n".join(lines).strip()


def _sanitize_tool_args(tool_name: str, tool_args: Any) -> dict[str, Any]:
    if not isinstance(tool_args, dict):
        return {"raw": _trim_text(str(tool_args), 300)}
    if tool_name == "safe_python_exec":
        code = tool_args.get("code", "")
        data_json = tool_args.get("data_json")
        data_type = type(data_json).__name__
        data_len = None
        if isinstance(data_json, list):
            data_len = len(data_json)
        elif isinstance(data_json, dict):
            data_len = len(data_json.keys())
        return {
            "code_preview": _trim_text(str(code), 500),
            "data_type": data_type,
            "data_length": data_len,
        }
    sanitized = {}
    for key, value in tool_args.items():
        sanitized[key] = _trim_text(str(value), 300) if isinstance(value, str) else value
    return sanitized


def _summarize_tool_output(tool_name: str, output: Any) -> dict[str, Any]:
    if tool_name == "safe_python_exec":
        try:
            parsed = json.loads(output) if isinstance(output, str) else output
        except Exception:
            return {"status": "unknown", "output_preview": _trim_text(str(output), 300)}
        return {
            "status": parsed.get("status"),
            "error": parsed.get("error"),
        }
    if isinstance(output, (dict, list)):
        return {"output_preview": _trim_text(_safe_json(output), 300)}
    return {"output_preview": _trim_text(str(output), 300)}


def _extract_final_response(raw: Any) -> tuple[str, Any]:
    if raw is None:
        return "", raw
    text = raw if isinstance(raw, str) else str(raw)
    stripped = text.strip()
    if not stripped:
        return "", raw
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped, raw
    if isinstance(parsed, dict) and parsed.get("final_response"):
        return str(parsed["final_response"]), parsed
    return stripped, parsed


def _build_inputs(payload: dict[str, Any], conversation_summary: str) -> dict[str, Any]:
    user_request = payload.get("message", "")
    query = payload.get("query") or user_request
    tickers = payload.get("tickers", "")
    sites = payload.get("sites", "")
    symbol = payload.get("symbol", "")
    interval = payload.get("interval", "1day")
    outputsize = int(payload.get("outputsize", 260) or 260)
    horizon_days = int(payload.get("horizon_days", 30) or 30)
    provided_data = payload.get("provided_data", "")
    if isinstance(provided_data, (dict, list)):
        provided_data = json.dumps(provided_data)
    search_query = _build_search_query(query, tickers, sites)

    # Get current date/time to provide context
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.now().year
    current_month = datetime.now().strftime("%B")

    runtime_defaults = {
        "user_request": user_request,
        "current_date": current_date,
        "current_year": current_year,
        "current_month": current_month,
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "horizon_days": horizon_days,
        "provided_data": provided_data,
        "query": query,
        "tickers": tickers,
        "sites": sites,
        "days": int(payload.get("days", 7) or 7),
        "max_articles": int(payload.get("max_articles", 8) or 8),
    }

    return {
        "user_request": user_request,
        "current_date": current_date,
        "current_year": current_year,
        "conversation_summary": conversation_summary,
        "runtime_defaults": json.dumps(runtime_defaults),
        "sources_requested": str(bool(payload.get("sources_requested"))),
        "query": query,
        "tickers": tickers,
        "sites": sites,
        "days": runtime_defaults["days"],
        "max_articles": runtime_defaults["max_articles"],
        "search_query": search_query,
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "horizon_days": horizon_days,
        "request": user_request,
        "provided_data": provided_data,
    }


def _collect_traces() -> tuple[list[dict[str, Any]], threading.Lock]:
    traces: list[dict[str, Any]] = []
    lock = threading.Lock()

    def record(entry: dict[str, Any]) -> None:
        with lock:
            traces.append(entry)

    @crewai_event_bus.on(CrewKickoffStartedEvent)
    def _crew_started(_source, _event):
        record({"type": "crew_started", "summary": "Crew execution started"})

    @crewai_event_bus.on(CrewKickoffCompletedEvent)
    def _crew_completed(_source, _event):
        record({"type": "crew_completed", "summary": "Crew execution completed"})

    @crewai_event_bus.on(CrewKickoffFailedEvent)
    def _crew_failed(_source, _event):
        record({"type": "crew_failed", "summary": "Crew execution failed"})

    @crewai_event_bus.on(TaskStartedEvent)
    def _task_started(_source, event):
        task_name = getattr(event.task, "name", None) or "task"
        agent = getattr(getattr(event.task, "agent", None), "role", None)
        record(
            {
                "type": "task_started",
                "task": task_name,
                "agent": agent,
                "summary": f"Started {task_name}",
            }
        )

    @crewai_event_bus.on(TaskCompletedEvent)
    def _task_completed(_source, event):
        task_name = getattr(event.task, "name", None) or "task"
        agent = getattr(getattr(event.task, "agent", None), "role", None)
        output = getattr(event.task_output, "raw", None) if hasattr(event, "task_output") else None
        record(
            {
                "type": "task_completed",
                "task": task_name,
                "agent": agent,
                "summary": f"Completed {task_name}",
                "output": _trim_text(str(output), 800) if output else None,
            }
        )

    @crewai_event_bus.on(TaskFailedEvent)
    def _task_failed(_source, event):
        task_name = getattr(event.task, "name", None) or "task"
        agent = getattr(getattr(event.task, "agent", None), "role", None)
        record(
            {
                "type": "task_failed",
                "task": task_name,
                "agent": agent,
                "summary": f"Failed {task_name}",
            }
        )

    @crewai_event_bus.on(ToolUsageStartedEvent)
    def _tool_started(_source, event):
        record(
            {
                "type": "tool_started",
                "tool": event.tool_name,
                "agent": event.agent_role,
                "task": event.task_name,
                "args": _sanitize_tool_args(event.tool_name, event.tool_args),
                "summary": f"Tool start: {event.tool_name}",
            }
        )

    @crewai_event_bus.on(ToolUsageFinishedEvent)
    def _tool_finished(_source, event):
        record(
            {
                "type": "tool_completed",
                "tool": event.tool_name,
                "agent": event.agent_role,
                "task": event.task_name,
                "output": _summarize_tool_output(event.tool_name, event.output),
                "summary": f"Tool done: {event.tool_name}",
            }
        )

    @crewai_event_bus.on(ToolUsageErrorEvent)
    def _tool_error(_source, event):
        record(
            {
                "type": "tool_failed",
                "tool": event.tool_name,
                "agent": event.agent_role,
                "task": event.task_name,
                "summary": f"Tool failed: {event.tool_name}",
            }
        )

    return traces, lock


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-API-Key"],
            "expose_headers": ["Content-Type"],
            "supports_credentials": False
        }
    })

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "finance_insight")
    api_key = os.getenv("API_KEY", "")
    store = MongoStore(mongo_uri, mongo_db)
    memory = MemoryManager(store)
    run_lock = threading.Lock()

    def check_auth() -> bool:
        if not api_key:
            return True
        header = request.headers.get("Authorization", "")
        token = ""
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
        token = token or request.headers.get("X-API-Key", "").strip()
        return token == api_key

    @app.before_request
    def _auth_guard():
        if request.path == "/health":
            return None
        if not check_auth():
            return jsonify({"error": "Unauthorized"}), 401
        return None

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "mongo": "ok" if store.ping() else "error",
            }
        )

    @app.get("/config")
    def config():
        """Return which API services are configured"""
        return jsonify({
            "services": {
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "serper": bool(os.getenv("SERPER_API_KEY")),
                "serpapi": bool(os.getenv("SERPAPI_API_KEY")),
                "twelveData": bool(os.getenv("TWELVE_DATA_API_KEY")),
                "alphaVantage": bool(os.getenv("ALPHAVANTAGE_API_KEY")),
            },
            "capabilities": {
                "news_search": bool(os.getenv("SERPER_API_KEY") or os.getenv("SERPAPI_API_KEY")),
                "market_data": bool(os.getenv("TWELVE_DATA_API_KEY")) or "stooq_fallback",
                "fundamentals": bool(os.getenv("ALPHAVANTAGE_API_KEY")),
                "ai_agents": bool(os.getenv("OPENAI_API_KEY")),
            }
        })

    @app.get("/history")
    def history():
        thread_id = request.args.get("threadId", "").strip()
        if not thread_id:
            latest = store.latest_thread()
            thread_id = latest.get("threadId") if latest else ""
        if thread_id:
            messages = store.list_messages(thread_id, limit=60, newest_first=False)
        else:
            messages = store.list_recent_messages(limit=60)
        payload = [
            {
                "id": str(msg.get("_id")),
                "role": msg.get("role"),
                "content": msg.get("content"),
                "createdAt": msg.get("createdAt").isoformat()
                if msg.get("createdAt")
                else None,
            }
            for msg in messages
        ]
        return jsonify(payload)

    @app.get("/threads")
    def threads():
        cursor = store.threads.find().sort("updatedAt", -1).limit(50)
        threads_list = []
        for thread in cursor:
            threads_list.append({
                "id": thread.get("threadId"),
                "title": thread.get("title", "Untitled"),
                "summary": thread.get("summary", "")[:100],
                "createdAt": thread.get("createdAt").isoformat() if thread.get("createdAt") else None,
                "updatedAt": thread.get("updatedAt").isoformat() if thread.get("updatedAt") else None,
            })
        return jsonify(threads_list)

    @app.get("/trace")
    def trace():
        thread_id = request.args.get("threadId", "").strip()
        if not thread_id:
            return jsonify({"error": "threadId is required"}), 400
        events = store.list_traces(thread_id, limit=500)
        payload = [
            {
                "id": str(event.get("_id")),
                "type": event.get("type"),
                "summary": event.get("summary"),
                "task": event.get("task"),
                "tool": event.get("tool"),
                "agent": event.get("agent"),
                "args": event.get("args"),
                "output": event.get("output"),
                "createdAt": event.get("createdAt").isoformat()
                if event.get("createdAt")
                else None,
            }
            for event in events
        ]
        return jsonify(payload)

    @app.post("/chat")
    def chat():
        """Stream chat response with real-time trace updates via SSE."""
        payload = request.get_json(force=True) or {}
        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({"error": "Empty message"}), 400

        thread_id = str(payload.get("threadId", "")).strip()
        if thread_id and not store.get_thread(thread_id):
            thread_id = ""
        if not thread_id:
            thread_id = store.create_thread(message[:60])

        user_message_id = store.add_message(thread_id, "user", message, {})
        memory.add_message_embedding(user_message_id, thread_id, message)

        conversation_summary = memory.build_summary(thread_id, message)
        store.update_thread_summary(thread_id, conversation_summary)

        # Log related past conversations for debugging
        related = memory.search_related(thread_id, message, top_k=3)
        if related:
            print(f"📚 Found {len(related)} related past conversations")
            for rel in related:
                print(f"  - Score: {rel['score']:.3f} | {rel['content'][:80]}...")

        def generate_stream():
            """Generate SSE stream with real-time trace updates."""
            print("[STREAM] Starting SSE stream generation")
            traces: list[dict[str, Any]] = []
            events_to_send: list[str] = []
            lock = threading.Lock()

            def emit_trace(entry: dict[str, Any]) -> None:
                print(f"[EMIT_TRACE] Called with type={entry.get('type')}")
                with lock:
                    traces.append(entry)
                    # Queue simplified message to send
                    simple_msg = _simplify_trace(entry)
                    event_data = json.dumps({
                        "type": "trace",
                        "message": simple_msg,
                        "detail": {
                            "type": entry.get("type"),
                            "agent": entry.get("agent"),
                            "task": entry.get("task"),
                            "tool": entry.get("tool"),
                        }
                    })
                    events_to_send.append(f"data: {event_data}\n\n")
                    print(f"[TRACE] {simple_msg}")  # Debug log
                    print(f"[EMIT_TRACE] Queued event, total in queue: {len(events_to_send)}")

            @crewai_event_bus.on(CrewKickoffStartedEvent)
            def _crew_started(_source, _event):
                emit_trace({"type": "crew_started", "summary": "Crew execution started"})

            @crewai_event_bus.on(CrewKickoffCompletedEvent)
            def _crew_completed(_source, _event):
                emit_trace({"type": "crew_completed", "summary": "Crew execution completed"})

            @crewai_event_bus.on(CrewKickoffFailedEvent)
            def _crew_failed(_source, _event):
                emit_trace({"type": "crew_failed", "summary": "Crew execution failed"})

            @crewai_event_bus.on(TaskStartedEvent)
            def _task_started(_source, event):
                task_name = getattr(event.task, "name", None) or "task"
                agent = getattr(getattr(event.task, "agent", None), "role", None)
                emit_trace({
                    "type": "task_started",
                    "task": task_name,
                    "agent": agent,
                    "summary": f"Started {task_name}",
                })

            @crewai_event_bus.on(TaskCompletedEvent)
            def _task_completed(_source, event):
                task_name = getattr(event.task, "name", None) or "task"
                agent = getattr(getattr(event.task, "agent", None), "role", None)
                output = getattr(event.task_output, "raw", None) if hasattr(event, "task_output") else None
                emit_trace({
                    "type": "task_completed",
                    "task": task_name,
                    "agent": agent,
                    "summary": f"Completed {task_name}",
                    "output": _trim_text(str(output), 800) if output else None,
                })

            @crewai_event_bus.on(TaskFailedEvent)
            def _task_failed(_source, event):
                task_name = getattr(event.task, "name", None) or "task"
                agent = getattr(getattr(event.task, "agent", None), "role", None)
                emit_trace({
                    "type": "task_failed",
                    "task": task_name,
                    "agent": agent,
                    "summary": f"Failed {task_name}",
                })

            @crewai_event_bus.on(ToolUsageStartedEvent)
            def _tool_started(_source, event):
                emit_trace({
                    "type": "tool_started",
                    "tool": event.tool_name,
                    "agent": event.agent_role,
                    "task": event.task_name,
                    "args": _sanitize_tool_args(event.tool_name, event.tool_args),
                    "summary": f"Tool start: {event.tool_name}",
                })

            @crewai_event_bus.on(ToolUsageFinishedEvent)
            def _tool_finished(_source, event):
                emit_trace({
                    "type": "tool_completed",
                    "tool": event.tool_name,
                    "agent": event.agent_role,
                    "task": event.task_name,
                    "args": _sanitize_tool_args(event.tool_name, event.tool_args),
                    "output": _summarize_tool_output(event.tool_name, event.output),
                    "summary": f"Tool done: {event.tool_name}",
                })

            @crewai_event_bus.on(ToolUsageErrorEvent)
            def _tool_error(_source, event):
                emit_trace({
                    "type": "tool_failed",
                    "tool": event.tool_name,
                    "agent": event.agent_role,
                    "task": event.task_name,
                    "summary": f"Tool failed: {event.tool_name}",
                })

            # Execute crew with scoped handlers
            inputs = _build_inputs(payload, conversation_summary)
            print(f"[STREAM] Starting crew execution with inputs: {list(inputs.keys())}")
            
            # Flag to track completion
            execution_complete = threading.Event()
            execution_result = {}
            
            def run_crew():
                try:
                    print("[CREW] Starting crew thread")
                    with run_lock:
                        crew = FinanceInsightCrew().build_crew()
                        print("[CREW] Crew built, starting kickoff")
                        result = crew.kickoff(inputs=inputs)
                        execution_result['result'] = result
                        print("[CREW] Crew execution completed successfully")
                except Exception as e:
                    print(f"[CREW] Error during execution: {e}")
                    import traceback
                    traceback.print_exc()
                    execution_result['error'] = str(e)
                finally:
                    execution_complete.set()
                    print("[CREW] Crew thread finished")
            
            # Start crew execution in background
            crew_thread = threading.Thread(target=run_crew)
            crew_thread.start()
            print("[STREAM] Crew thread started, beginning event polling")
            
            # Stream events as they come in with keepalive
            events_sent = 0
            keepalive_counter = 0
            last_event_time = time.time()
            KEEPALIVE_INTERVAL = 10  # Send keepalive every 10 seconds
            
            while not execution_complete.is_set():
                with lock:
                    while events_to_send:
                        event = events_to_send.pop(0)
                        events_sent += 1
                        last_event_time = time.time()
                        print(f"[STREAM] Yielding event #{events_sent}")
                        yield event
                
                # Send keepalive as data event if no events for KEEPALIVE_INTERVAL seconds
                current_time = time.time()
                if current_time - last_event_time > KEEPALIVE_INTERVAL:
                    keepalive_counter += 1
                    last_event_time = current_time
                    # Send as data event so proxies recognize it as activity
                    keepalive_msg = f"data: {json.dumps({'type': 'heartbeat', 'count': keepalive_counter})}\n\n"
                    print(f"[STREAM] Sending heartbeat #{keepalive_counter}")
                    yield keepalive_msg
                
                execution_complete.wait(timeout=0.5)  # Check every 500ms
            
            print(f"[STREAM] Execution complete, sending remaining events")
            # Yield any remaining events
            with lock:
                while events_to_send:
                    event = events_to_send.pop(0)
                    events_sent += 1
                    print(f"[STREAM] Yielding final event #{events_sent}")
                    yield event
            
            # Wait for thread to complete
            crew_thread.join()
            print(f"[STREAM] Crew thread joined, total events sent: {events_sent}")
            
            # Check for errors
            if 'error' in execution_result:
                print(f"[STREAM] Crew execution error: {execution_result['error']}")
                yield f"data: {json.dumps({'type': 'error', 'message': execution_result['error']})}\n\n"
                return
            
            result = execution_result.get('result')
            if not result:
                print("[STREAM] No result from crew execution")
                yield f"data: {json.dumps({'type': 'error', 'message': 'No result from crew'})}\n\n"
                return

            print("[STREAM] Extracting final response")
            # Extract and save response  
            try:
                final_response, raw_output = _extract_final_response(result)
                assistant_text = final_response or str(raw_output)
                print(f"[STREAM] Assistant response length: {len(assistant_text)} chars")
                
                print("[STREAM] Saving to MongoDB")
                assistant_id = store.add_message(thread_id, "assistant", assistant_text, {})
                print(f"[STREAM] Message saved with ID: {assistant_id}")
                
                print("[STREAM] Adding embedding")
                memory.add_message_embedding(assistant_id, thread_id, assistant_text)
                print("[STREAM] Embedding added")
                
                # Send final response
                trace_payload = [
                    {
                        "type": event.get("type"),
                        "agent": event.get("agent"),
                        "task": event.get("task"),
                        "tool": event.get("tool"),
                        "output": event.get("output"),
                        "summary": event.get("summary"),
                    }
                    for event in traces
                ]
                
                final_data = json.dumps({
                    "type": "response",
                    "reply": assistant_text,
                    "threadId": thread_id,
                    "traces": trace_payload,
                })
                print(f"[STREAM] Sending final response, payload size: {len(final_data)} bytes")
                yield f"data: {final_data}\n\n"
                print("[STREAM] Final response sent successfully")
            except Exception as e:
                print(f"[STREAM] Error preparing final response: {e}")
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': f'Error preparing response: {str(e)}'})}\n\n"

        return app.response_class(
            generate_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    # ============= NEW ASYNC JOB-BASED ENDPOINTS =============
    
    @app.post("/chat/async")
    def chat_async():
        """Start async chat job and return job ID immediately."""
        payload = request.get_json(force=True) or {}
        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({"error": "Empty message"}), 400

        thread_id = str(payload.get("threadId", "")).strip()
        if thread_id and not store.get_thread(thread_id):
            thread_id = ""
        if not thread_id:
            thread_id = store.create_thread(message[:60])

        # Create job
        job_id = str(uuid.uuid4())
        
        with jobs_lock:
            jobs[job_id] = {
                "id": job_id,
                "status": JobStatus.PENDING,
                "thread_id": thread_id,
                "message": message,
                "traces": [],
                "result": None,
                "error": None,
                "created_at": _utc_now().isoformat(),
                "updated_at": _utc_now().isoformat(),
            }
        
        # Start background job
        def run_job():
            print(f"[JOB {job_id}] Starting background job")
            with jobs_lock:
                jobs[job_id]["status"] = JobStatus.RUNNING
                jobs[job_id]["updated_at"] = _utc_now().isoformat()
            
            try:
                print(f"[JOB {job_id}] Adding user message")
                # Add user message
                user_message_id = store.add_message(thread_id, "user", message, {})
                memory.add_message_embedding(user_message_id, thread_id, message)

                conversation_summary = memory.build_summary(thread_id, message)
                store.update_thread_summary(thread_id, conversation_summary)

                # Setup trace collection
                traces: list[dict[str, Any]] = []
                trace_lock = threading.Lock()

                def emit_trace(entry: dict[str, Any]) -> None:
                    print(f"[JOB {job_id}] Trace: {entry.get('type')}")
                    with trace_lock:
                        traces.append(entry)
                        simple_msg = _simplify_trace(entry)
                        with jobs_lock:
                            jobs[job_id]["traces"].append({
                                "type": entry.get("type"),
                                "message": simple_msg,
                                "agent": entry.get("agent"),
                                "task": entry.get("task"),
                                "tool": entry.get("tool"),
                                "timestamp": _utc_now().isoformat(),
                            })
                            jobs[job_id]["updated_at"] = _utc_now().isoformat()

                print(f"[JOB {job_id}] Building crew")
                # Execute crew
                inputs = _build_inputs(payload, conversation_summary)
                
                print(f"[JOB {job_id}] Executing crew.kickoff()")
                with run_lock:
                    crew = FinanceInsightCrew().build_crew()
                    
                    # Add callback to collect events
                    original_events = []
                    def event_callback(event):
                        print(f"[JOB {job_id}] Event received: {type(event).__name__}")
                        original_events.append(event)
                        # Emit trace based on event type
                        if isinstance(event, CrewKickoffStartedEvent):
                            emit_trace({"type": "crew_started", "summary": "Crew execution started"})
                        elif isinstance(event, CrewKickoffCompletedEvent):
                            emit_trace({"type": "crew_completed", "summary": "Crew execution completed"})
                        elif isinstance(event, TaskStartedEvent):
                            task_name = getattr(event.task, "name", None) or "task"
                            agent = getattr(getattr(event.task, "agent", None), "role", None)
                            emit_trace({"type": "task_started", "task": task_name, "agent": agent, "summary": f"Started {task_name}"})
                        elif isinstance(event, TaskCompletedEvent):
                            task_name = getattr(event.task, "name", None) or "task"
                            agent = getattr(getattr(event.task, "agent", None), "role", None)
                            emit_trace({"type": "task_completed", "task": task_name, "agent": agent, "summary": f"Completed {task_name}"})
                    
                    # Subscribe to all events temporarily
                    unsub_list = []
                    for event_cls in [CrewKickoffStartedEvent, CrewKickoffCompletedEvent, TaskStartedEvent, TaskCompletedEvent]:
                        unsub = crewai_event_bus.on(event_cls)(lambda src, evt, cls=event_cls: event_callback(evt))
                        unsub_list.append(unsub)
                    
                    try:
                        result = crew.kickoff(inputs=inputs)
                    finally:
                        # Unsubscribe
                        for unsub in unsub_list:
                            if callable(unsub):
                                unsub()

                # Extract and save response
                final_response, raw_output = _extract_final_response(result)
                assistant_text = final_response or str(raw_output)
                assistant_id = store.add_message(thread_id, "assistant", assistant_text, {})
                memory.add_message_embedding(assistant_id, thread_id, assistant_text)

                # Update job with result
                with jobs_lock:
                    jobs[job_id]["status"] = JobStatus.COMPLETED
                    jobs[job_id]["result"] = {
                        "reply": assistant_text,
                        "threadId": thread_id,
                    }
                    jobs[job_id]["updated_at"] = _utc_now().isoformat()

            except Exception as e:
                print(f"[JOB {job_id}] Error: {e}")
                import traceback
                traceback.print_exc()
                with jobs_lock:
                    jobs[job_id]["status"] = JobStatus.FAILED
                    jobs[job_id]["error"] = str(e)
                    jobs[job_id]["updated_at"] = _utc_now().isoformat()

        thread = threading.Thread(target=run_job, daemon=True)
        thread.start()

        return jsonify({"jobId": job_id, "threadId": thread_id, "status": JobStatus.PENDING})

    @app.get("/chat/async/<job_id>/status")
    def get_job_status(job_id: str):
        """Get job status and latest traces."""
        with jobs_lock:
            job = jobs.get(job_id)
            if not job:
                return jsonify({"error": "Job not found"}), 404
            
            return jsonify({
                "jobId": job["id"],
                "status": job["status"],
                "threadId": job["thread_id"],
                "traces": job["traces"][-10:],  # Last 10 traces
                "traceCount": len(job["traces"]),
                "updatedAt": job["updated_at"],
            })

    @app.get("/chat/async/<job_id>/result")
    def get_job_result(job_id: str):
        """Get final job result."""
        with jobs_lock:
            job = jobs.get(job_id)
            if not job:
                return jsonify({"error": "Job not found"}), 404
            
            if job["status"] == JobStatus.PENDING or job["status"] == JobStatus.RUNNING:
                return jsonify({"error": "Job not yet completed", "status": job["status"]}), 425
            
            if job["status"] == JobStatus.FAILED:
                return jsonify({"error": job["error"], "status": job["status"]}), 500
            
            return jsonify({
                "jobId": job["id"],
                "status": job["status"],
                "result": job["result"],
                "traces": job["traces"],
            })

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Finance Insight API server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
