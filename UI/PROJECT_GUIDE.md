# Sentinel AI UI - Implementation & Backend Integration Guide

This document summarizes what was built in the UI, how the frontend is wired, and
how to connect it to a Flask + MongoDB backend for chat history and agent output.

## What was implemented

- Next.js (App Router + TypeScript) UI in `web/`.
- Full chat layout with sidebar, top bar, and centered chat view.
- Dark/light mode toggle with smooth transitions.
- Real typing input (textarea) with Enter-to-send.
- History list and buttons are wired to real pages or behaviors.
- Settings page for API URL + API key (stored locally).
- Placeholder pages for Agents, Workflows, Knowledge Base, History, Help.

## Key UI routes

- `/` main chat UI
- `/settings` API authentication + connection test
- `/history` history overview (supports `?title=...`)
- `/agents`, `/workflows`, `/knowledge-base`, `/help` (placeholders)

## How the frontend talks to your backend

Frontend integration lives in `web/lib/api.ts`:

- `GET /health` used by the Settings page test button.
- `GET /history` used by the chat view to preload history.
- `POST /chat` used to send a message to the agent.

### Request headers

If an API key is set in `/settings`, the UI sends:

- `Authorization: Bearer <apiKey>`
- `X-API-Key: <apiKey>`

### Message format expected by the UI

The UI accepts any of the following shapes:

- `GET /history` returns:
  - `[{ id, role, content, createdAt }, ...]` OR
  - `{ messages: [...] }` OR
  - `{ data: [...] }`

- `POST /chat` returns:
  - `{ reply: "text", threadId }`, OR
  - `{ messages: [ ... ], threadId }`

### Environment option

You can set a default backend URL in `web/.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:5000
```

The Settings page overrides this per browser (stored in `localStorage`).

## MongoDB data model (suggested)

Use two collections: `threads` and `messages`.

### threads

```
{
  _id: ObjectId,
  title: "Deployment checklist",
  userId: "user-123",
  createdAt: ISODate,
  updatedAt: ISODate,
  metadata: {}
}
```

### messages

```
{
  _id: ObjectId,
  threadId: ObjectId,
  role: "user" | "assistant" | "system",
  content: "message text",
  createdAt: ISODate,
  metadata: {}
}
```

Recommended indexes:

- `messages.threadId`
- `messages.createdAt`
- `threads.userId`

## Flask + MongoDB example (minimal)

This is a simple reference backend. Replace `run_agent()` with your CrewAI call.

```
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

client = MongoClient("mongodb://localhost:27017")
db = client["sentinel_ai"]
threads = db["threads"]
messages = db["messages"]

def run_agent(user_message, thread_id=None):
    # TODO: integrate CrewAI pipeline here
    return f"Echo: {user_message}"

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/history")
def history():
    # Example: return last 30 messages overall
    cursor = messages.find().sort("createdAt", -1).limit(30)
    data = []
    for doc in cursor:
        data.append({
            "id": str(doc["_id"]),
            "role": doc["role"],
            "content": doc["content"],
            "createdAt": doc["createdAt"].isoformat()
        })
    return jsonify(list(reversed(data)))

@app.post("/chat")
def chat():
    payload = request.get_json(force=True) or {}
    user_message = payload.get("message", "").strip()
    thread_id = payload.get("threadId")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    now = datetime.utcnow()

    if thread_id:
        thread_oid = ObjectId(thread_id)
    else:
        thread_oid = threads.insert_one({
            "title": user_message[:40],
            "userId": "demo",
            "createdAt": now,
            "updatedAt": now,
        }).inserted_id

    user_doc = {
        "threadId": thread_oid,
        "role": "user",
        "content": user_message,
        "createdAt": now,
    }
    messages.insert_one(user_doc)

    assistant_text = run_agent(user_message, thread_id=str(thread_oid))

    assistant_doc = {
        "threadId": thread_oid,
        "role": "assistant",
        "content": assistant_text,
        "createdAt": datetime.utcnow(),
    }
    messages.insert_one(assistant_doc)

    return jsonify({
        "reply": assistant_text,
        "threadId": str(thread_oid),
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

## CrewAI integration notes

- Put the CrewAI run inside `/chat`.
- If you have tools or agents that return structured output, map it into
  `assistant` messages or expand the API to return `messages: []`.
- For multi-agent responses, return an array of messages instead of a single `reply`.

## History management ideas

- Store one thread per chat session.
- Update `threads.updatedAt` whenever a new message is inserted.
- Add a `GET /threads` endpoint for richer sidebar history (titles, last updated).
- Add `GET /threads/<id>` to load a full conversation.

## Security notes

- API keys stored in localStorage are fine for local dev only.
- For production, use server-side auth (sessions/JWT) and do not expose keys.
- Use HTTPS and restrict CORS origins to your frontend domain.

## Run the UI

```
cd web
npm install
npm run dev
```

Then open `http://localhost:3000`.
