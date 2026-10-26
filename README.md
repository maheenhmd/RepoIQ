# 🚀 RepoIQ

### Understand Your Code. Defend Your Decisions.

**RepoIQ is an AI-powered, repository-aware technical interview platform** that transforms GitHub projects into personalized technical interviews.

Public GitHub metadata, file discovery/filtering, bounded ingestion preview, automatic PostgreSQL-backed ingestion, and multi-language code chunking are implemented. See [ingestion documentation](docs/ingestion.md) and [chunking documentation](docs/chunking.md). (feat: add automatic ingestion and multi-language code chunking)

Instead of asking generic programming questions, RepoIQ analyzes your actual codebase and challenges you to explain its architecture, implementation, and engineering decisions.

> 🚧 **Status:** Under active development. GitHub integration and PostgreSQL foundation are implemented; RAG and AI interviews are upcoming.

---

## 🎯 Why RepoIQ?

Building a project doesn't always mean understanding every engineering decision behind it.

RepoIQ helps developers:

- 🧠 Understand their own codebases more deeply.
- 🎤 Prepare for project-based technical interviews.
- 🏗️ Explain architecture and technical decisions.
- 🔍 Identify knowledge gaps and improve engineering skills.
- 📈 Track interview performance and progress.

**The goal: Evaluate understanding, not just the ability to write code.**

## ✨ Key Features

| Feature | Description | Status |
|---|---|---|
| 🔗 GitHub Integration | Import repositories and explore source files | ✅ Implemented |
| 📂 Smart File Filtering | Identify relevant code and exclude unnecessary files | ✅ Implemented |
| 🗄️ PostgreSQL Database | Database models and migrations using Neon | ✅ Implemented |
| 🔄 Scalable Ingestion | Resumable, version-aware repository processing | 🔜 Planned |
| 🧠 RAG Code Analysis | Understand and retrieve relevant code using embeddings | 🔜 Planned |
| 🤖 AI Interviewer | Generate repository-specific technical questions | 🔜 Planned |
| 📊 Answer Evaluation | Assess technical reasoning and provide feedback | 🔜 Planned |
| 💬 Text Interviews | Interactive technical interview sessions | 🔜 Planned |
| 🎙️ Voice Interviewer | Real-time AI interviews using LiveKit | 🔜 Planned |
| 📈 Progress Tracking | Interview history, scores, and improvement insights | 🔜 Planned |

## ⚙️ How It Works

```text
🔗 GitHub Repository
         |
         v
📂 Source Code Discovery & Filtering
         |
         v
🧩 Code Chunking & Embeddings
         |
         v
🗄️ PostgreSQL + pgvector
         |
         v
🔍 RAG-Based Context Retrieval
         |
         v
🤖 AI Technical Interviewer
         |
    +----+----+
    |         |
    v         v
💬 Text    🎙️ Voice
    |         |
    +----+----+
         |
         v
📊 Evaluation & Feedback
```

*This represents the planned complete workflow.*

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| 🎨 Frontend | Next.js, React, TypeScript |
| 🐍 Backend | Python, FastAPI |
| 🗄️ Database | PostgreSQL, Neon |
| 🔧 ORM & Migrations | SQLAlchemy, Alembic |
| 🔗 Repository Integration | GitHub REST API |
| 🧠 AI & Retrieval | RAG, Embeddings, pgvector (planned) |
| 🎙️ Voice AI | LiveKit (planned) |
| 📦 Package Management | uv |
| 🧪 Testing | pytest |

## 🏗️ Architecture

```text
RepoIQ/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── integrations/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
├── docs/
│   ├── architecture.md
│   └── milestones.md
└── README.md
```

## 🚀 Getting Started

**Prerequisites:** Python 3.12, uv, Git, and PostgreSQL (Neon).

**1. Clone and install dependencies**

```bash
git clone <YOUR_REPOSITORY_URL>
cd RepoIQ/backend
uv sync
```

**2. Configure database**

Create a `.env` file from `.env.example` and add your Neon connection strings.

```dotenv
DATABASE_URL=postgresql+psycopg://...
DIRECT_DATABASE_URL=postgresql+psycopg://...
```

Never commit your `.env` file.

**3. Apply migrations**

```bash
uv run alembic upgrade head
```

**4. Run the backend**

```bash
uv run python -m uvicorn app.main:app --reload
```

API documentation: `http://127.0.0.1:8000/docs`

**5. Run tests**

```bash
uv run python -m pytest -v
```

## 🗺️ Development Roadmap

- [x] **Phase 1:** FastAPI, GitHub integration, source discovery and PostgreSQL foundation
- [ ] **Phase 2:** Scalable ingestion and storage optimization
- [ ] **Phase 3:** Code chunking, embeddings and RAG retrieval
- [ ] **Phase 4:** AI question generation, text interviews and answer evaluation
- [ ] **Phase 5:** Next.js interview dashboard and user experience
- [ ] **Phase 6:** LiveKit real-time voice interviewer
- [ ] **Phase 7:** Production deployment, security and performance optimization

## 🔐 Security Principles

RepoIQ treats imported repositories as untrusted data. Source code is never executed during analysis. Secrets, sensitive files, API credentials, and database connections must be handled securely.

## 💡 Vision

RepoIQ is built around one idea:

**AI can help you write code. RepoIQ helps you prove you understand it.**

The platform aims to make technical interviews more practical, personalized, and grounded in real engineering experience.

---

**🚀 RepoIQ — Beyond the Code. Understand the Engineering.**
