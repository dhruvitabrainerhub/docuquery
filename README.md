# 📄 DocuQuery — AI-Powered Document Q&A (RAG)

> **Phase 1** — Django REST API · ChromaDB Vector Store · Celery Async Processing · OpenRouter LLM

DocuQuery is a production-ready **Retrieval-Augmented Generation (RAG)** backend built with Django. Upload PDF documents, automatically embed them into a vector store, then ask natural-language questions and receive accurate answers with **source citations** — all powered by `gpt-4o-mini` via OpenRouter.

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                     Client / API Consumer                │
└──────────────────────┬───────────────────────────────────┘
                       │ REST API (DRF)
┌──────────────────────▼───────────────────────────────────┐
│                   Django Application                     │
│                                                          │
│   ┌─────────────┐   ┌──────────────┐   ┌─────────────┐  │
│   │  Upload PDF │──▶│  Celery Task │──▶│  ChromaDB   │  │
│   │   (DRF API) │   │  (Async)     │   │  Vector DB  │  │
│   └─────────────┘   └──────────────┘   └──────┬──────┘  │
│                                                │         │
│   ┌─────────────────────────────────────────── ▼ ──────┐ │
│   │  Chat API  →  MultiQueryRetriever  →  GPT-4o-mini  │ │
│   │                                   (via OpenRouter) │ │
│   └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
         │                           │
    PostgreSQL DB              Redis Broker
   (Metadata, Chat)         (Celery Queue)
```

### Key Design Decisions

| Component | Technology | Reason |
|---|---|---|
| Web Framework | Django 4.2 + DRF | Robust ORM, admin, REST support |
| Embedding Model | `all-MiniLM-L6-v2` (HuggingFace) | Free, CPU-friendly, high quality |
| Vector Store | ChromaDB (persistent) | Lightweight, local, no cloud needed |
| LLM | GPT-4o-mini via OpenRouter | Low cost, OpenAI-compatible API |
| Task Queue | Celery + Redis | Async document processing, retries |
| Scheduler | Celery Beat | Nightly re-indexing at 02:00 UTC |
| Database | PostgreSQL | Reliable metadata & chat history |
| Monitoring | Flower | Real-time Celery task dashboard |

---

## 🚀 Features

- **📤 PDF Upload & Auto-Processing** — Upload a PDF and Celery automatically queues embedding in the background via Django signals
- **🧩 Smart Text Chunking** — `RecursiveCharacterTextSplitter` with 500-token chunks and 100-token overlap for context continuity
- **🔍 Multi-Query Retrieval** — LLM generates multiple sub-queries from a single question to maximise recall
- **💬 Contextual Chat Sessions** — Full conversation history stored per session (UUID-keyed); assistant resolves pronouns/references across turns
- **📌 Source Citations** — Every answer returns exact source file(s) and page numbers relied upon
- **🔄 Nightly Re-indexing** — Celery Beat re-embeds all processed documents at 02:00 UTC automatically
- **♻️ Auto Cleanup** — Deleting a document triggers a Django signal that purges its vectors from ChromaDB
- **📊 Admin Dashboard** — Full Django admin interface for Documents, ChatSessions, and ChatMessages
- **🐳 Docker Ready** — One-command `docker-compose up` starts all 6 services

---

## 📁 Project Structure

```
django wirh rag project phase 1/
├── Dockerfile                  # Python 3.12-slim image (CPU optimized)
├── docker-compose.yml          # 6-service orchestration
├── requirements.txt            # Base dependencies
├── requirements-cpu.txt        # CPU-only PyTorch build (used in Docker)
├── .env                        # Environment variables (not committed)
├── .gitignore
└── DocuQuery/                  # Django project root
    ├── manage.py
    ├── chroma_db/              # Persistent ChromaDB vector store
    ├── media/
    │   └── documents/          # Uploaded PDF files
    ├── DocuQuery/              # Django config package
    │   ├── settings.py         # All settings (env-driven)
    │   ├── urls.py             # Root URL conf → api/ prefix
    │   ├── celery.py           # Celery app setup
    │   ├── asgi.py
    │   └── wsgi.py
    └── Docchat/                # Core RAG application
        ├── models.py           # Documents, ChatSession, ChatMessage
        ├── serializers.py      # DRF serializer + PDF validation
        ├── views.py            # API views (Upload, Process, Chat, Status)
        ├── urls.py             # App-level URL routing
        ├── tasks.py            # Celery tasks (process, reindex)
        ├── signals.py          # Auto-trigger embedding on upload
        ├── admin.py            # Admin registrations
        └── services/
            ├── parser.py       # PDF text extraction (pypdf, per-page)
            ├── chunker.py      # RecursiveCharacterTextSplitter
            ├── embeddings.py   # ChromaDB + HuggingFace singleton
            └── rag_pipeline.py # ChatOpenAI via OpenRouter
```

---

## ⚙️ Environment Variables

Create a `.env` file in the project root (same level as `docker-compose.yml`):

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
DB_NAME=docuquery
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_HOST=localhost         # Use 'db' when running via Docker
DB_PORT=5432

# LLM (OpenRouter)
OPENROUTER_API_KEY=sk-or-...

# Celery / Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

> **Note:** Never commit `.env` to version control. It is already listed in `.gitignore`.

---

## 🐳 Quick Start — Docker (Recommended)

### Prerequisites
- Docker & Docker Compose installed

### Run all services

```bash
# 1. Clone the repo and enter the directory
cd "django wirh rag project phase 1"

# 2. Create your .env file (see above)
cp .env.example .env   # then edit values

# 3. Start everything
docker-compose up --build
```

This starts **6 containers**:

| Container | Port | Role |
|---|---|---|
| `docuquery_app` | `8000` | Django REST API |
| `docuquery_db` | `5433` | PostgreSQL 16 database |
| `redis` | `6379` | Redis broker (internal) |
| `celery_worker` | — | Async task processor (2 workers) |
| `celery_beat` | — | Scheduler (nightly re-index) |
| `flower` | `5555` | Celery monitoring dashboard |

Access:
- **API**: http://localhost:8000/api/
- **Admin**: http://localhost:8000/admin/
- **Flower**: http://localhost:5555/

---

## 🖥️ Local Development (Without Docker)

### Prerequisites
- Python 3.12+
- PostgreSQL running locally
- Redis running locally (`redis-server`)

### Setup

```bash
# 1. Create & activate a virtual environment
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
cp .env.example .env   # then fill in values

# 4. Run migrations
cd DocuQuery
python manage.py migrate

# 5. Create a superuser (for Django admin)
python manage.py createsuperuser

# 6. Start the Django server
python manage.py runserver
```

### Start Celery (separate terminals)

```bash
# Terminal 2 — Worker
cd DocuQuery
celery -A DocuQuery worker --loglevel=info -E --concurrency=2

# Terminal 3 — Beat scheduler
cd DocuQuery
celery -A DocuQuery beat --loglevel=info

# Terminal 4 — Flower dashboard (optional)
cd DocuQuery
celery -A DocuQuery flower --port=5555
```

---

## 📡 API Reference

Base URL: `http://localhost:8000/api/`

### 1. Upload Document

```http
POST /api/upload/
Content-Type: multipart/form-data
```

| Field | Type | Description |
|---|---|---|
| `title` | string | Human-readable document name |
| `file` | file | PDF file (only `.pdf` accepted) |

**Response:**
```json
{
  "id": 1,
  "title": "Annual Report 2024",
  "file": "/media/documents/report.pdf",
  "upload_at": "2026-07-21T08:00:00Z",
  "processed": false
}
```

> ✅ A Celery task is **automatically triggered** via Django signal on successful upload. No manual processing step needed.

---

### 2. Check Processing Status

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

Document status values: `PENDING` → `PROCESSING` → `DONE` | `FAILED`

---

### 3. Force Re-process Document

```http
POST /api/process/{document_id}/
Content-Type: application/json

{ "force": true }
```

**Response:**
```json
{ "message": "Document processed successfully." }
```

---

### 4. Create Chat Session

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

### 5. Chat (Ask a Question)

```http
POST /api/chat/{session_id}/
Content-Type: application/json
```

| Field | Type | Description |
|---|---|---|
| `question` | string | Natural-language question |

**Response:**
```json
{
  "answer": "The revenue increased by 12% in Q3 due to new product launches...",
  "sources": [
    {
      "file": "documents/annual_report.pdf",
      "pages": [5, 12, 18]
    }
  ]
}
```

> 💡 The chat endpoint uses **conversation history** from the session — follow-up questions with pronouns ("What about *it*?") are resolved correctly.

---

## 🧠 RAG Pipeline — How It Works

```
PDF Upload
    │
    ▼
[pypdf] Extract text per page → [{page: 1, text: "..."}, ...]
    │
    ▼
[RecursiveCharacterTextSplitter] chunk_size=500, overlap=100
    │
    ▼
[HuggingFace all-MiniLM-L6-v2] Generate embeddings (384 dimensions)
    │
    ▼
[ChromaDB] Store chunks + metadata {document_id, source, page, chunk_id}
    │
    ▼  ── At query time ──────────────────────────────────────
    │
[MultiQueryRetriever] LLM generates 3–5 sub-queries from user question
    │
    ▼
[ChromaDB] Similarity search → top 20 chunks across all sub-queries
    │
    ▼
[Deduplication] Max 5 chunks per source file, exact-match filtering
    │
    ▼
[GPT-4o-mini via OpenRouter] Answer + PAGES_USED:n,n,n
    │
    ▼
[Parse response] Extract answer text + source page references
    │
    ▼
Return {answer, sources: [{file, pages}]}
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
| `processed` | BooleanField | `True` when embedding is complete |
| `task_id` | CharField | Celery task ID for status tracking |
| `status` | CharField | `PENDING / PROCESSING / DONE / FAILED` |

### `ChatSession`

| Field | Type | Description |
|---|---|---|
| `id` | UUIDField (PK) | Unique session identifier |
| `title` | CharField | Session title |
| `created_at` | DateTimeField | Auto-set on creation |

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

- **Triggered by**: Django `post_save` signal on new document upload
- **Retries**: Up to 3 times with 60-second countdown on failure
- **Steps**: Delete old vectors → Extract text → Chunk → Embed → Store in ChromaDB → Mark `DONE`

### `reindex_all_documents()`

- **Triggered by**: Celery Beat at **02:00 UTC every night**
- **Purpose**: Re-embed all processed documents (handles model updates, schema changes)

---

## 🔧 Configuration Reference

### ChromaDB Path

```python
# settings.py
CHROMA_DB_PATH = str(BASE_DIR / 'chroma_db')
```

### Embedding Model

```python
# services/embeddings.py
model_name = 'sentence-transformers/all-MiniLM-L6-v2'
```

### Chunking Parameters

```python
# services/chunker.py
chunk_size = 500
chunk_overlap = 100
separators = ["\n\n", "\n", ". ", " ", ""]
```

### LLM

```python
# services/rag_pipeline.py
model = 'openai/gpt-4o-mini'
base_url = 'https://openrouter.ai/api/v1'
```

---

## 🛡️ Error Handling

| Scenario | Behavior |
|---|---|
| Non-PDF file uploaded | `400 Bad Request` — serializer validation rejects it |
| Document already processed | `400` — unless `force=true` is sent |
| File missing from disk | `404` — prompts re-upload |
| No text extracted from PDF | `400` — informs client |
| Empty question sent | `400` — `question is required` |
| Celery task fails | Auto-retry ×3 (60s gap), then marks document `FAILED` |
| Document deleted | `post_delete` signal purges its ChromaDB vectors automatically |

---

## 📊 Monitoring

### Flower (Celery Dashboard)

Visit **http://localhost:5555** to monitor:
- Active / completed / failed tasks in real-time
- Worker status and concurrency
- Task retry history

### Django Admin

Visit **http://localhost:8000/admin/** to:
- Browse uploaded documents and their processing status
- View all chat sessions and individual messages
- Filter documents by `processed` status
- Search documents by title

---

## 🔒 Security Notes

- `SECRET_KEY` is loaded from environment — never hardcode it
- `DEBUG=False` in production — set via `.env`
- `ALLOWED_HOSTS` is configurable via environment
- PDF-only validation is enforced at the serializer level
- CSRF middleware is active (use session auth or disable for pure API usage)

---

## 📦 Dependencies

### Core
| Package | Version | Purpose |
|---|---|---|
| Django | latest | Web framework |
| djangorestframework | latest | REST API |
| psycopg2-binary | latest | PostgreSQL adapter |
| python-dotenv | latest | `.env` file loading |

### AI / RAG
| Package | Version | Purpose |
|---|---|---|
| langchain | 0.3.26 | LLM orchestration |
| langchain-openai | latest | ChatOpenAI client |
| langchain-chroma | latest | ChromaDB integration |
| langchain-huggingface | latest | HuggingFace embeddings |
| langchain-text-splitters | latest | Recursive text chunking |
| chromadb | latest | Vector store |
| sentence-transformers | latest | `all-MiniLM-L6-v2` model |
| pypdf | latest | PDF text extraction |

### Async / Infrastructure
| Package | Version | Purpose |
|---|---|---|
| celery | 5.5.3 | Task queue |
| redis | 6.2.0 | Message broker |
| flower | 2.0.1 | Celery monitoring |

---

## 🗺️ Roadmap (Phase 2+)

- [ ] JWT / Token Authentication for multi-user support
- [ ] Support for `.docx`, `.txt`, `.md` file types
- [ ] Frontend UI (React or Next.js)
- [ ] Streaming LLM responses via Server-Sent Events
- [ ] Per-user document isolation
- [ ] pgvector support as alternative to ChromaDB
- [ ] Rate limiting and API key management

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📄 License

This project is for educational and development purposes. See `LICENSE` for details.

---

<div align="center">

**Built with ❤️ using Django · LangChain · ChromaDB · Celery · OpenRouter**

</div>
