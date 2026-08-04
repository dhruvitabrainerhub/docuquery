# 📄 DocuQuery — AI-Powered Document Q&A (RAG)

> **Full Stack RAG System** — Django REST API · WebSocket Streaming · ChromaDB · Celery · OpenRouter LLM · ELK Stack

DocuQuery is a production-ready **Retrieval-Augmented Generation (RAG)** backend built with Django. Upload PDF documents, automatically embed them into a vector store, then ask natural-language questions via **real-time WebSocket streaming** and receive accurate answers with **source citations** — all powered by `gpt-4o-mini` via OpenRouter.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Client / API Consumer                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API (DRF) + WebSocket (Channels)
┌──────────────────────▼──────────────────────────────────────┐
│                    Django Application                       │
│                                                             │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │  Upload PDF │──▶│  Celery Task │──▶│    ChromaDB     │  │
│  │  (DRF API)  │   │  (Async)     │   │   Vector DB     │  │
│  └─────────────┘   └──────────────┘   └────────┬────────┘  │
│                                                 │           │
│  ┌──────────────────────────────────────────────▼────────┐  │
│  │  WebSocket → MultiQueryRetriever → GPT-4o-mini        │  │
│  │              Streams tokens live (word-by-word)       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
    PostgreSQL DB        Redis Broker         ELK Stack
   (Metadata, Chat)    (Celery + WS)    (Logs → Kibana)
```

---

## 🚀 Features

- **📤 PDF Upload & Auto-Processing** — Upload a PDF → Django signal → Celery queues embedding automatically
- **🧩 Smart Text Chunking** — `RecursiveCharacterTextSplitter` with 1000-token chunks and 200-token overlap
- **🔍 Multi-Query Retrieval** — LLM generates 3–5 sub-queries from a single question to maximise recall
- **⚡ Real-Time Streaming** — WebSocket streams answer tokens word-by-word as LLM generates them
- **💬 Contextual Chat Sessions** — Full conversation history per session (UUID-keyed); pronouns resolved across turns
- **📌 Source Citations** — Every answer returns exact source file(s) and page numbers
- **🔐 JWT Authentication** — Register/Login with access + refresh tokens; WebSocket auth via `?token=` query param
- **👥 Multi-User Isolation** — Each user's documents are isolated; RAG retrieval is scoped per user
- **🔄 Nightly Re-indexing** — Celery Beat re-embeds all documents at 02:00 UTC automatically
- **📢 WebSocket Notifications** — Celery notifies connected clients when document processing completes
- **📊 Admin Dashboard** — Color-coded status, re-embed action, full document & chat management
- **📈 ELK Stack Logging** — Structured logs → Logstash → Elasticsearch → Kibana dashboards
- **🌸 Flower Dashboard** — Real-time Celery task monitoring
- **🐳 Docker Ready** — Multi-profile Docker Compose (core / celery / elk)

---

## 📁 Project Structure

```
DocuQuery/
├── Dockerfile
├── docker-compose.yml          # Profiles: default, celery, elk
├── requirements.txt
├── requirements-cpu.txt        # CPU-only PyTorch (Docker)
├── .env                        # Environment variables
├── logstash/
│   └── pipeline/
│       └── logstash.conf       # Logstash TCP → Elasticsearch
└── DocuQuery/                  # Django project root
    ├── manage.py
    ├── DocuQuery/
    │   ├── settings.py
    │   ├── urls.py
    │   ├── celery.py
    │   ├── asgi.py             # Daphne + Django Channels
    │   └── wsgi.py
    └── Docchat/
        ├── models.py           # Documents, ChatSession, ChatMessage
        ├── serializers.py      # DRF serializer + PDF validation
        ├── views.py            # Upload, Process, Session, Status
        ├── urls.py             # REST API routes
        ├── consumers.py        # WebSocket ChatConsumer (streaming)
        ├── routing.py          # WebSocket URL patterns
        ├── tasks.py            # Celery: process_document, reindex
        ├── signals.py          # post_save → trigger Celery task
        ├── middleware.py       # JWT auth for WebSocket
        ├── auth_views.py       # Register / Login / JWT
        ├── admin.py            # Admin with color status + re-embed
        ├── log_handler.py      # Elasticsearch logging handler
        └── services/
            ├── parser.py       # pypdf — extract text per page
            ├── chunker.py      # RecursiveCharacterTextSplitter
            ├── embeddings.py   # ChromaDB + HuggingFace singleton
            ├── rag_pipeline.py # ChatOpenAI via OpenRouter
            └── rag_service.py  # RAGService — retrieve + stream
```

---

## 🐳 Quick Start — Docker (Recommended)

### Prerequisites
- Docker & Docker Compose installed
- OpenRouter API key

### 1. Clone & configure

```bash
git clone <repo-url>
cd DocuQuery
cp .env.example .env   # fill in values
```

### 2. Start core services

```bash
docker compose up -d --build
```

### 3. Start with Celery (recommended)

```bash
docker compose --profile celery up -d --build
```

### 4. Start with ELK logging (optional)

```bash
docker compose --profile celery --profile elk up -d --build
```

### Containers

| Container | Port | Role |
|---|---|---|
| `docuquery_app` | `8000` | Django + Daphne (HTTP + WebSocket) |
| `docuquery_db` | `5433` | PostgreSQL 16 |
| `redis` | `6379` | Redis broker |
| `chromadb` | `8001` | ChromaDB vector store |
| `celery_worker` | — | Async task processor |
| `celery_beat` | — | Nightly re-index scheduler |
| `flower` | `5555` | Celery monitoring |
| `elasticsearch` | `9200` | Log storage |
| `logstash` | `5000` | Log ingestion |
| `kibana` | `5601` | Log visualization |

### Access

| Service | URL |
|---|---|
| API | http://localhost:8000/api/ |
| Admin | http://localhost:8000/admin/ |
| Flower | http://localhost:5555/ |
| Kibana | http://localhost:5601/ |

---

## 🖥️ Local Development (Without Docker)

```bash
# 1. Virtual environment
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Migrate & create superuser
cd DocuQuery
python manage.py migrate
python manage.py createsuperuser

# 5. Start server
daphne -b 0.0.0.0 -p 8000 DocuQuery.asgi:application
```

```bash
# Terminal 2 — Celery Worker
celery -A DocuQuery worker --loglevel=info -E --concurrency=2

# Terminal 3 — Celery Beat
celery -A DocuQuery beat --loglevel=info

# Terminal 4 — Flower (optional)
celery -A DocuQuery flower --port=5555
```

---

## 🔑 Environment Variables

```env
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=docuquery
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=db
DB_PORT=5432

# Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
REDIS_URL=redis://redis:6379/0

# ChromaDB
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# LLM
OPENROUTER_API_KEY=your-openrouter-key

# ELK (optional)
ELK_ENABLED=false
LOGSTASH_HOST=logstash
LOGSTASH_PORT=5000
```

---

## 📡 API Reference

Base URL: `http://localhost:8000/api/`

### Authentication

```http
POST /api/auth/register/
Content-Type: application/json

{ "username": "john", "password": "secret123", "email": "john@example.com" }
```

```http
POST /api/auth/login/
Content-Type: application/json

{ "username": "john", "password": "secret123" }
```

**Response:**
```json
{
  "tokens": {
    "access": "eyJhbGc...",
    "refresh": "eyJhbGc..."
  }
}
```

```http
POST /api/auth/refresh/
Content-Type: application/json

{ "refresh": "eyJhbGc..." }
```

> All endpoints below require `Authorization: Bearer <access_token>`

---

### Upload Document

```http
POST /api/upload/
Content-Type: multipart/form-data

title: "Annual Report"
file: report.pdf
```

**Response:**
```json
{
  "id": 1,
  "title": "Annual Report",
  "file": "/media/documents/report.pdf",
  "upload_at": "2026-08-04T10:00:00Z",
  "processed": false,
  "status": "PENDING"
}
```

> Celery task is **automatically triggered** via Django signal — no manual step needed.

---

### Check Processing Status

```http
GET /api/documents/{document_id}/status/
```

**Response:**
```json
{
  "document_id": 1,
  "task_id": "abc123-...",
  "document_status": "DONE",
  "celery_status": "SUCCESS",
  "processed": true
}
```

Status flow: `PENDING` → `PROCESSING` → `DONE` | `FAILED`

---

### Force Re-process Document

```http
POST /api/process/{document_id}/
```

---

### Create Chat Session

```http
POST /api/session/
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "New Chat"
}
```

---

## 🔌 WebSocket — Real-Time Streaming Chat

```
ws://localhost:8000/ws/chat/{session_id}/?token={access_token}
```

### Connect & Send Question

```javascript
const ws = new WebSocket(
  `ws://localhost:8000/ws/chat/${sessionId}/?token=${token}`
);

ws.onopen = () => ws.send(JSON.stringify({ question: "What is Python?" }));

ws.onmessage = (e) => {
  const event = JSON.parse(e.data);

  if (event.type === "retrieving_done") console.log("🔍 Searching docs...");
  else if (event.type === "token")      process.stdout.write(event.content);
  else if (event.type === "complete")   console.log("\nSources:", event.sources);
};
```

### Event Types

| Event | Fields | Description |
|---|---|---|
| `connection` | `user_id`, `session_id` | Connection established |
| `retrieving_done` | — | Document retrieval complete, tokens starting |
| `token` | `content` | One word/token of the answer |
| `complete` | `answer`, `sources` | Full answer + source citations |
| `document_ready` | `document_id` | Celery finished processing a document |
| `error` | `message` | Something went wrong |

---

## 🧠 RAG Pipeline

```
PDF Upload
    │
    ▼
[pypdf] Extract text per page
    │
    ▼
[RecursiveCharacterTextSplitter] chunk_size=1000, overlap=200
    │
    ▼
[HuggingFace all-MiniLM-L6-v2] Generate embeddings (384 dimensions)
    │
    ▼
[ChromaDB] Store chunks + metadata {document_id, user_id, source, page}
    │
    ▼  ── At query time ─────────────────────────────────────────
    │
[MultiQueryRetriever] LLM generates 3–5 sub-queries
    │
    ▼
[ChromaDB] Similarity search → top 20 chunks
    │
    ▼
[User filter] Only this user's documents
    │
    ▼
[Deduplication] Max 5 chunks per source
    │
    ▼
[GPT-4o-mini via OpenRouter] Generate answer with SOURCES_USED
    │
    ▼
[Stream tokens] word-by-word via WebSocket
    │
    ▼
[Parse] Extract clean answer + source citations
    │
    ▼
Return tokens live + {answer, sources: [{file, pages}]}
```

---

## 🗄️ Data Models

### `Documents`

| Field | Type | Description |
|---|---|---|
| `id` | Auto PK | Document identifier |
| `title` | CharField | Document title |
| `file` | FileField | Stored at `media/documents/` |
| `upload_at` | DateTimeField | Auto-set on creation |
| `processed` | BooleanField | `True` when embedding complete |
| `status` | CharField | `PENDING / PROCESSING / DONE / FAILED` |
| `task_id` | CharField | Celery task ID |
| `user` | FK → User | Owner |

### `ChatSession`

| Field | Type | Description |
|---|---|---|
| `id` | UUIDField (PK) | Unique session identifier |
| `title` | CharField | Session title |
| `created_at` | DateTimeField | Auto-set on creation |
| `user` | FK → User | Owner |

### `ChatMessage`

| Field | Type | Description |
|---|---|---|
| `id` | Auto PK | Message identifier |
| `session` | FK → ChatSession | Owning session |
| `role` | CharField | `user` or `assistant` |
| `content` | TextField | Message body |
| `created_at` | DateTimeField | Auto-set on creation |

---

## ⚡ Celery Tasks

### `process_document_task(document_id)`
- **Triggered by**: Django `post_save` signal on upload
- **Retries**: 3 times with 60s countdown
- **Steps**: Delete old vectors → Extract → Chunk → Embed → Store → Mark `DONE` → Notify WebSocket

### `reindex_all_documents()`
- **Triggered by**: Celery Beat at **02:00 UTC nightly**
- **Purpose**: Re-embed all processed documents with 30s stagger

---

## 📊 Monitoring

### Flower — http://localhost:5555
- Active / completed / failed tasks
- Worker status and concurrency
- Task retry history

### Django Admin — http://localhost:8000/admin/
- Color-coded document status
- Re-embed selected documents action
- Browse chat sessions and messages

### Kibana — http://localhost:5601
- All Django + Celery + WebSocket logs
- Filter by tag: `celery`, `websocket`, `rag`
- Filter by level: `ERROR`, `WARNING`, `INFO`

---

## 🔒 Security

- JWT access tokens (60 min) + refresh tokens (7 days)
- WebSocket authenticated via `?token=` query param
- Per-user document isolation in ChromaDB
- PDF-only file validation at serializer level
- `SECRET_KEY` and credentials loaded from environment only

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| Django + DRF | Web framework + REST API |
| django-channels + daphne | WebSocket support |
| djangorestframework-simplejwt | JWT authentication |
| langchain 0.3.26 | LLM orchestration |
| langchain-openai | ChatOpenAI via OpenRouter |
| langchain-chroma | ChromaDB integration |
| langchain-huggingface | HuggingFace embeddings |
| chromadb | Vector store |
| sentence-transformers | `all-MiniLM-L6-v2` model |
| pypdf | PDF text extraction |
| celery 5.5.3 + redis | Async task queue |
| flower | Celery monitoring |
| python-logstash | Structured logging to ELK |
| whitenoise | Static file serving |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📄 License

This project is for educational and development purposes.

---

<div align="center">

**Built with ❤️ using Django · LangChain · ChromaDB · Celery · Django Channels · OpenRouter · ELK Stack**

</div>
