# 📄 DocuQuery — AI-Powered Document Q&A (RAG)

> **Full Stack RAG System** — Django · WebSocket Streaming · ChromaDB · Celery · OpenRouter · ELK Stack

DocuQuery is a production-ready **Retrieval-Augmented Generation (RAG)** backend. Upload PDFs, auto-embed them into a vector store, then chat via **real-time WebSocket streaming** with source citations — powered by `gpt-4o-mini` via OpenRouter.

---

## 🏗️ Architecture

```
Client
  │
  ├── REST API (DRF) ──► Upload PDF ──► Django Signal ──► Celery ──► ChromaDB
  │
  └── WebSocket (ws://) ──► MultiQueryRetriever ──► GPT-4o-mini ──► Stream tokens
                                    │
                          PostgreSQL · Redis · ELK Stack
```

---

## 🚀 Features

- **📤 PDF Upload** — Upload triggers Django signal → Celery auto-embeds in background
- **🔍 Multi-Query Retrieval** — LLM generates 3–5 sub-queries to maximise recall
- **⚡ WebSocket Streaming** — Tokens streamed word-by-word in real-time
- **💬 Chat History** — Full conversation history per session; pronouns resolved across turns
- **📌 Source Citations** — Every answer includes source file + page numbers
- **🔐 JWT Auth** — Register/Login with access + refresh tokens; WebSocket auth via `?token=`
- **👥 Multi-User Isolation** — RAG retrieval scoped per user in ChromaDB
- **✏️ Auto Chat Title** — First 6 words of question auto-set as session title
- **🧹 Orphan Cleanup** — Missing PDF files auto-removed from ChromaDB + DB every 10 min
- **🔄 Nightly Re-indexing** — Celery Beat re-embeds all documents at 02:00 UTC
- **📊 Admin Dashboard** — Color-coded status, re-embed action
- **📈 ELK Logging** — Structured logs → Logstash → Elasticsearch → Kibana
- **🐳 Docker Ready** — Multi-profile Compose (core / celery / elk)

---

## 📁 Project Structure

```
DocuQuery/
├── Dockerfile
├── docker-compose.yml          # Profiles: default, celery, elk
├── requirements.txt
├── .env.example
├── logstash/pipeline/logstash.conf
└── DocuQuery/
    ├── manage.py
    ├── DocuQuery/
    │   ├── settings.py
    │   ├── celery.py
    │   └── asgi.py
    └── Docchat/
        ├── models.py           # Documents, ChatSession, ChatMessage
        ├── serializers.py      # PDF validation
        ├── views.py            # Upload, Process, Session, Status
        ├── consumers.py        # WebSocket streaming
        ├── tasks.py            # Celery tasks
        ├── signals.py          # post_save → Celery
        ├── middleware.py       # JWT WebSocket auth
        ├── auth_views.py       # Register / Login
        ├── admin.py
        └── services/
            ├── parser.py       # PDF text extraction
            ├── chunker.py      # Text splitting
            ├── embeddings.py   # ChromaDB + HuggingFace
            ├── rag_pipeline.py # ChatOpenAI via OpenRouter
            └── rag_service.py  # Retrieve + stream
```

---

## 🐳 Quick Start

```bash
# Clone & configure
git clone <repo-url>
cd DocuQuery
cp ".env.example" .env   # fill in values

# Core services only
docker compose up -d --build

# With Celery (recommended)
docker compose --profile celery up -d --build

# With ELK logging (optional)
docker compose --profile celery --profile elk up -d --build
```

| Service | URL |
|---|---|
| API | http://localhost:8000/api/ |
| Admin | http://localhost:8000/admin/ |
| Flower | http://localhost:5555/ |
| Kibana | http://localhost:5601/ |

---

## 📡 API Reference

> All endpoints require `Authorization: Bearer <access_token>` except auth routes.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register/` | Register new user |
| POST | `/api/auth/login/` | Login → get tokens |
| POST | `/api/auth/refresh/` | Refresh access token |
| POST | `/api/upload/` | Upload PDF |
| GET | `/api/documents/{id}/status/` | Check processing status |
| POST | `/api/process/{id}/` | Force re-process document |
| POST | `/api/session/` | Create chat session |

Status flow: `PENDING` → `PROCESSING` → `DONE` | `FAILED`

---

## 🔌 WebSocket Chat

```
ws://localhost:8000/ws/chat/{session_id}/?token={access_token}
```

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/chat/${sessionId}/?token=${token}`);

ws.onopen = () => ws.send(JSON.stringify({ question: "What is Python?" }));

ws.onmessage = (e) => {
  const event = JSON.parse(e.data);
  if (event.type === "retrieving_done") console.log("🔍 Searching...");
  else if (event.type === "token")      process.stdout.write(event.content);
  else if (event.type === "complete")   console.log("\nSources:", event.sources);
};
```

| Event | Description |
|---|---|
| `connection` | Connected successfully |
| `retrieving_done` | Retrieval done, streaming starts |
| `token` | One word of the answer |
| `complete` | Full answer + source citations |
| `document_ready` | Document processing finished |
| `title_update` | Session title auto-updated |
| `error` | Something went wrong |

---

## ⚡ Celery Tasks

| Task | Trigger | Purpose |
|---|---|---|
| `process_document_task` | post_save signal | Extract → Chunk → Embed → Store → Notify |
| `generate_chat_title` | First message | Auto-set session title from first 6 words |
| `cleanup_missing_files` | Every 10 min | Remove orphaned vectors + DB records |
| `reindex_all_documents` | 02:00 UTC nightly | Re-embed all documents |

---

## 🗄️ Data Models

| Model | Key Fields |
|---|---|
| `Documents` | `title`, `file`, `status`, `processed`, `task_id`, `user` |
| `ChatSession` | `id (UUID)`, `title`, `user` |
| `ChatMessage` | `session`, `role (user/assistant)`, `content` |

---

## 📊 Monitoring

- **Flower** `http://localhost:5555` — Celery task monitoring
- **Django Admin** `http://localhost:8000/admin/` — Color-coded document status, re-embed action
- **Kibana** `http://localhost:5601` — Filter logs by `celery`, `websocket`, `rag` tags

---

## 📦 Tech Stack

| Package | Purpose |
|---|---|
| Django + DRF | Web framework + REST API |
| django-channels + daphne | WebSocket support |
| simplejwt | JWT authentication |
| langchain 0.3.26 | LLM orchestration |
| langchain-openai | GPT-4o-mini via OpenRouter |
| chromadb | Vector store |
| sentence-transformers | `all-MiniLM-L6-v2` embeddings |
| pypdf | PDF text extraction |
| celery + redis | Async task queue |
| python-logstash | ELK structured logging |

---

## 📄 License

This project is for educational and development purposes.

<div align="center">

**Built with ❤️ using Django · LangChain · ChromaDB · Celery · Django Channels · OpenRouter · ELK Stack**

</div>
