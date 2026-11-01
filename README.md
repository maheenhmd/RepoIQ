# 🚀 RepoIQ

### Understand Your Code. Defend Your Decisions.

**RepoIQ is an AI-powered, repository-aware technical interview platform that turns real GitHub projects into personalized technical interviews.**

Instead of testing only theoretical programming knowledge, RepoIQ asks developers to explain the architecture, implementation, and engineering decisions behind their own code.

It combines **GitHub integration, code embeddings, hybrid retrieval, RAG, and an adaptive AI interviewer** to create a practical, code-grounded interview experience.

> **Development Status:** Active MVP development. Repository ingestion, retrieval, text-based AI interviews, answer evaluation, and interview reports have been implemented. End-to-end reliability, evaluation accuracy, saved-interview recovery, and performance optimization are ongoing. Voice interviews, authentication, and production deployment are not yet implemented.

---

## 🎯 Why RepoIQ?

Writing code and understanding every decision behind it are two different skills.

RepoIQ helps developers:

- 🧠 Understand their own codebases more deeply.
- 💻 Practice technical interviews using real project code.
- 🏗️ Explain architecture, implementation, and design trade-offs.
- 🔍 Identify knowledge gaps through contextual feedback.
- 📈 Review interview performance and track improvement over time.

**The goal is simple: Evaluate understanding, not just the ability to write code.**

## ✨ Features

| Feature | Description | Status |
|---|---|---|
| 🔗 GitHub Integration | Repository metadata, discovery, and source retrieval | ✅ Implemented |
| 📂 Smart File Filtering | Prioritize relevant files and exclude unnecessary content | ✅ Implemented |
| 🧩 Code Chunking | Split source files into searchable code units | ✅ Implemented |
| ⚙️ Background Ingestion | Process and store repository contents using workers | ✅ Implemented |
| 🗄️ PostgreSQL + pgvector | Persist repository data, interviews, and vector embeddings | ✅ Implemented |
| 🧠 Semantic & Hybrid Retrieval | Retrieve code using embeddings, text matching, and ranking | ✅ Implemented |
| 🔍 RAG-Based Context | Supply relevant repository evidence to the AI interviewer | ✅ Implemented |
| 🤖 AI Question Generation | Generate technical questions grounded in repository code | ✅ Implemented |
| 💬 Multi-Turn Text Interviews | Ask questions, evaluate answers, and generate follow-ups | ✅ Working MVP |
| 📊 Answer Evaluation | Produce correctness feedback and performance assessments | ⚠️ Refinement ongoing |
| 📝 Interview Reports | Saved answers, scores, feedback, and supporting citations | ✅ Implemented |
| ✨ Animated Report UI | Performance-based feedback and motivational report presentation | ⚠️ Verification pending |
| 💾 Saved Interview Recovery | Retrieve existing interviews and continue unfinished sessions | ⚠️ Known lookup issue |
| 🎙️ Voice AI Interviewer | Spoken questions and microphone-based responses | 🔜 Planned |
| 👤 Authentication & Dashboard | User accounts and personal interview management | 🔜 Planned |
| 📈 Long-Term Progress Tracking | Compare interviews and visualize improvement | 🔜 Planned |
| ☁️ Production Deployment | Publicly hosted, production-ready application | 🔜 Planned |

## ⚙️ How It Works

```text
       GitHub Repository URL
                 |
                 v
       Repository Discovery
          & File Filtering
                 |
                 v
       Background Ingestion
          & Code Chunking
                 |
                 v
        Code Embeddings
                 |
                 v
       PostgreSQL + pgvector
                 |
                 v
       Hybrid Code Retrieval
                 |
                 v
      Relevant Code Evidence
                 |
                 v
        RAG + Local LLM
                 |
                 v
       AI Technical Interview
                 |
          +------+------+
          |             |
          v             v
       Question      Developer
       Generation      Answer
          |             |
          +------+------+
                 |
                 v
       Feedback & Follow-up
                 |
                 v
       Saved Interview Report
```

The interviewer uses retrieved code context to generate questions, assess responses, and continue the conversation.

The current MVP supports **text-based interviews**. Voice interaction is a future milestone.

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js, React, TypeScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL, Neon |
| ORM & Migrations | SQLAlchemy, Alembic |
| Vector Search | pgvector |
| Repository Integration | GitHub REST API |
| Code Embeddings | CodeRankEmbed |
| Retrieval | Semantic search, PostgreSQL full-text search, hybrid ranking |
| AI / LLM | Ollama, Qwen2.5-Coder |
| AI Architecture | Retrieval-Augmented Generation (RAG) |
| Background Processing | Python ingestion and embedding workers |
| Python Package Management | uv |
| Testing | pytest |

The current local development setup uses `qwen2.5-coder:1.5b` with Ollama. Model selection and inference performance may evolve.

## 🏗️ Project Architecture

```text
RepoIQ/
├── backend/
│   ├── app/
│   │   ├── api/             # API endpoints
│   │   ├── core/            # Application configuration
│   │   ├── db/              # Database models and access
│   │   ├── integrations/    # GitHub and LLM integrations
│   │   ├── schemas/         # Data validation
│   │   ├── services/        # Retrieval and interview logic
│   │   ├── workers/         # Background processing
│   │   └── main.py          # FastAPI entry point
│   ├── alembic/             # Database migrations
│   ├── tests/               # Backend tests
│   └── pyproject.toml
│
├── frontend/
│   └── src/
│       ├── app/             # Next.js routes
│       ├── components/      # Reusable UI
│       └── lib/             # API client and utilities
│
├── docs/                    # Architecture and technical docs
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.12
- Node.js and npm
- uv package manager
- Git
- PostgreSQL with pgvector (Neon supported)
- Ollama with a compatible local model

### 1. Clone the repository

```bash
git clone https://github.com/maheenhmd/RepoIQ.git
cd RepoIQ
```

### 2. Set up the backend

```bash
cd backend
uv sync
```

Create a `.env` file using `.env.example` as the configuration reference.

Configure your database connection, AI model, embedding settings, and any required GitHub credentials.

Example database configuration:

```dotenv
DATABASE_URL=postgresql+psycopg://...
DIRECT_DATABASE_URL=postgresql+psycopg://...
```

Use the example environment file for the complete, current configuration schema.

**Never commit `.env` files or credentials.**

### 3. Apply database migrations

```bash
uv run alembic upgrade head
```

### 4. Prepare Ollama

Install Ollama and download the local model used by the current development setup:

```bash
ollama pull qwen2.5-coder:1.5b
```

### 5. Start the FastAPI backend

```bash
uv run --no-sync python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend: http://127.0.0.1:8000

API documentation: http://127.0.0.1:8000/docs

### 6. Start the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open:

http://localhost:3000/interview

### 7. Run background workers

Repository ingestion and code embedding require their respective background workers.

Follow [the backend MVP documentation](docs/backend-mvp.md) for the project's current worker setup and operational instructions.

Previously indexed repositories should not need re-ingestion simply to view saved interviews.

### 8. Run backend tests

From the `backend` directory:

```bash
uv run --no-sync python -m pytest -v
```

Passing unit tests does not necessarily establish end-to-end LLM reliability; manual integration checks are also required.

---

## 🧠 Interview Experience

The intended interview workflow is:

1. Paste a public GitHub repository URL.
2. Import and index the repository if it has not already been processed.
3. Select an interview difficulty and turn limit.
4. Optionally specify topics to practice.
5. Answer AI-generated, repository-specific technical questions.
6. Receive feedback and contextual follow-up questions.
7. Complete the interview and review the performance report.

Interview records and reports are stored for subsequent retrieval.

### Performance Reports

The report interface includes or is being refined to support:

- Overall interview score and assessment summary.
- Topic-level performance.
- Strengths and improvement opportunities.
- Supporting repository citations.
- Personalized recommendations.
- Performance-aware animations and encouraging messages.

Evaluation results are experimental and should not be treated as an authoritative measure of engineering ability.

## 🚧 Current Limitations

RepoIQ is still an actively developed MVP.

- **Existing repository lookup:** Previously indexed repositories may incorrectly return `Not Found`, preventing saved interviews from appearing in the UI. Recovery and lookup behavior need verification.
- **Local inference speed:** CPU-based Ollama inference can produce noticeable response delays.
- **Assessment reliability:** Small models may generate unsupported technical claims or overly generous scores. Evidence grounding, question diversity, and scoring consistency need further validation.
- **Interview recovery:** Persistence is implemented, but refresh, resume, and completed-report navigation require additional end-to-end checks.
- **Frontend reliability:** Recently implemented report animations and citation handling still require manual verification.
- **Voice and user accounts:** Not yet implemented.
- **Production readiness:** Authentication, security review, deployment, and broader integration testing remain pending.

## 🗺️ Development Roadmap

- [x] **Phase 1:** FastAPI foundation and GitHub integration
- [x] **Phase 2:** PostgreSQL models, migrations, and repository ingestion
- [x] **Phase 3:** Code chunking, embeddings, and hybrid RAG retrieval
- [x] **Phase 4:** AI question generation and multi-turn text interviews
- [x] **Phase 5:** Initial Next.js interview interface, persistence, and reports
- [ ] **Phase 6:** Interview reliability, scoring accuracy, performance, and resume UX
- [ ] **Phase 7:** Voice-enabled AI interviewer
- [ ] **Phase 8:** Authentication, user dashboard, and progress analytics
- [ ] **Phase 9:** Production deployment, security hardening, and end-to-end testing

## 📚 Documentation

- [Repository Ingestion](docs/ingestion.md)
- [Code Chunking](docs/chunking.md)
- [Backend MVP & Manual Runbook](docs/backend-mvp.md)
- [Architecture](docs/architecture.md)
- [Development Milestones](docs/milestones.md)

## 🔐 Security Principles

RepoIQ treats imported repositories as untrusted data.

The project is designed around these principles:

- Do not execute imported source code during analysis.
- Filter unnecessary or potentially sensitive repository files.
- Keep API keys and database credentials outside version control.
- Validate external API inputs and model-generated outputs.
- Ground interview questions and assessments in retrieved code evidence.
- Protect stored repository and interview data.

These are design principles; a complete production security audit remains pending.

## 💡 Vision

**AI can help you write code. RepoIQ helps you prove you understand it.**

RepoIQ aims to make technical interviews more practical, personalized, and grounded in real engineering experience.

---

**🚀 RepoIQ — Beyond the Code. Understand the Engineering.**