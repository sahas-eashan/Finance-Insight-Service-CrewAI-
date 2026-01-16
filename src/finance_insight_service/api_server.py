from __future__ import annotations

import argparse
import json
import os
import threading
from datetime import datetime
from typing import Any

import faiss
import numpy as np
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI
from pymongo import MongoClient, ReturnDocument
from bson import ObjectId

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

    runtime_defaults = {
        "user_request": user_request,
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
    CORS(app, resources={r"/*": {"origins": "*"}})

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

        inputs = _build_inputs(payload, conversation_summary)
        with run_lock, crewai_event_bus.scoped_handlers():
            traces, _ = _collect_traces()
            crew = FinanceInsightCrew().build_crew()
            result = crew.kickoff(inputs=inputs)

        final_response, raw_output = _extract_final_response(result)
        assistant_text = final_response or str(raw_output)
        assistant_id = store.add_message(thread_id, "assistant", assistant_text, {})
        memory.add_message_embedding(assistant_id, thread_id, assistant_text)

        # Return traces directly with response (ephemeral, not stored)
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

        return jsonify(
            {
                "reply": assistant_text,
                "threadId": thread_id,
                "traces": trace_payload,
            }
        )

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
