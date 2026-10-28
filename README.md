# AI Software Engineering Companion

An AI-powered software engineering companion that lives alongside the developer during software development. It understands your projects, helps plan and write code, runs tests, debugs failures, maintains engineering knowledge, and reuses lessons across projects.

## Vision

This is not a generic chatbot. It is a **contextual engineering partner** designed around:

- **Project Context** — understands your codebase, architecture, and dependencies
- **Knowledge** — indexes and retrieves relevant project information via pgvector
- **Memory** — remembers engineering lessons and reuses them across projects
- **Tools** — reads files, searches code, runs commands, executes tests safely
- **Agents** — orchestrates specialized workflows (planning, coding, testing, debugging, Git)
- **Permissions** — human-in-the-loop for risky operations, autonomous for safe ones
- **Desktop Companion** — operates as a native Windows desktop companion with system tray and screen context
- **Observability** — live metrics, token estimations, audit traces, and evaluation benchmarks

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│             Windows Desktop (Electron 34)                │
│       System Tray • Screen Context • Process Manager     │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│          Frontend (Next.js 15 + React + TypeScript)      │
│     Chat • Knowledge • Memory • Agent • Git • Metrics    │
│     Port: 3000                                           │
└───────────────────────────┬──────────────────────────────┘
                            │ REST + WebSocket
┌───────────────────────────▼──────────────────────────────┐
│          Backend (Node.js + Express + TypeScript)        │
│     API Gateway • Reverse Proxy • WebSocket Server       │
│     Port: 3001                                           │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼──────────────────────────────┐
│           AI Service (Python 3.12 + FastAPI)             │
│   Gemini Provider • ReAct Orchestrator • Telemetry Buffer│
│   Port: 8000                                             │
└─────────────┬──────────────────────────────┬─────────────┘
              │                              │
┌─────────────▼──────────────┐ ┌─────────────▼─────────────┐
│  PostgreSQL 17 + pgvector  │ │     Local Project Code    │
│  Knowledge & Memory Store  │ │     Read-Only Sandboxed   │
│  Port: 5432                │ │     Traversal Protection  │
└────────────────────────────┘ └───────────────────────────┘
```

---

## Project Structure

```
AI-Software-Engineering-Companion/
├── frontend/               → Next.js 15 + React 19 + TypeScript + Tailwind CSS
├── backend/                → Node.js + TypeScript + Express API gateway & WebSocket
├── ai-service/             → Python + FastAPI + Pydantic + SQLAlchemy + Gemini SDK
├── desktop/                → Electron Windows Desktop Companion (Tray, Shortcuts, Screen Context)
├── scripts/                → Full-stack verification & deployment validation scripts
│   └── verify_stack.py     → Automated service health, database, tool & Docker check
├── docs/                   → Architecture and technical documentation
│   └── architecture.md     → Detailed 17-phase system architecture
├── docker-compose.yml      → Multi-service Docker Compose configuration (base & full profiles)
├── .env.example            → Environment variable template
├── knowledge.md            → Detailed architectural knowledge base & verification history
└── package.json            → Root monorepo orchestrator scripts
```

---

## Development Phases Status

All 17 original roadmap phases are complete and verified:

| Phase | Description | Status |
|---|---|---|
| **Phase 0** | Environment audit | ✅ Complete & Verified |
| **Phase 1** | Project skeleton | ✅ Complete & Verified |
| **Phase 2** | Frontend ↔ Backend communication | ✅ Complete & Verified |
| **Phase 3** | Python AI service core | ✅ Complete & Verified |
| **Phase 4** | LLM provider abstraction (Google Gemini) | ✅ Complete & Verified |
| **Phase 5** | Conversational assistant persona & multi-turn reasoning | ✅ Complete & Verified |
| **Phase 6** | Project/codebase understanding & context injection | ✅ Complete & Verified |
| **Phase 7** | Tool system & permission engine | ✅ Complete & Verified |
| **Phase 8** | Agent orchestration (ReAct loop & step bounding) | ✅ Complete & Verified |
| **Phase 9** | RAG + PostgreSQL pgvector database integration | ✅ Complete & Verified |
| **Phase 10** | Long-term memory & cross-project learning | ✅ Complete & Verified |
| **Phase 11** | Testing & debugging agent loop | ✅ Complete & Verified |
| **Phase 12** | Git integration (read-only queries & commit proposal) | ✅ Complete & Verified |
| **Phase 13** | Windows desktop companion (Electron tray & global hotkeys) | ✅ Complete & Verified |
| **Phase 14** | Screen context + explicit user permission boundary | ✅ Complete & Verified |
| **Phase 15** | Docker & infrastructure (multi-stage builds & compose profiles) | ✅ Complete & Verified |
| **Phase 16** | Evaluation & observability (telemetry buffer, audit traces, UI panel) | ✅ Complete & Verified |
| **Phase 17** | Polish, documentation & full-stack deployment verification | ✅ Complete & Verified |

---

## Quick Start

### Prerequisites

- **Node.js** 22+ (tested with v22.14.0) and **npm** 10+
- **Python** 3.12+ (or 3.14) with virtual environment support
- **Docker** and **Docker Compose** v2+ (for PostgreSQL + pgvector)
- **Git** 2.40+

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd AI-Software-Engineering-Companion

# 2. Install dependencies across all packages
npm run install:all

# 3. Configure environment
copy .env.example .env
copy ai-service\.env.example ai-service\.env
# Edit .env and ai-service\.env with your GEMINI_API_KEY and database settings
```

### Starting the Database

Start the PostgreSQL 17 container with the `pgvector` extension:

```bash
npm run docker:db
```

### Running Local Development Services

In separate terminal windows, start each service:

```bash
# Terminal 1: AI Service (FastAPI)
npm run dev:ai

# Terminal 2: Backend Gateway (Express)
npm run dev:backend

# Terminal 3: Frontend Web UI (Next.js)
npm run dev:frontend
```

Or start the native Windows Desktop Companion:

```bash
# Terminal 4: Windows Desktop Companion (Electron)
npm run dev:desktop
```

---

## Docker Deployment

The repository includes production-ready multi-stage Dockerfiles for all three services and a dual-profile `docker-compose.yml`.

| Command | Description |
|---|---|
| `npm run docker:db` | Starts the PostgreSQL + pgvector container (`companion-postgres`) |
| `npm run docker:full` | Starts all services (`db`, `ai-service`, `backend`, `frontend`) |
| `npm run docker:down` | Gracefully stops and removes all containers |
| `npm run docker:config` | Validates the interpolated Docker Compose full configuration |

---

## Health Checks & Endpoints

| Service | Port | Health Check | Documentation |
|---|---|---|---|
| **Frontend UI** | 3000 | http://localhost:3000/api/health | http://localhost:3000 |
| **Backend Gateway** | 3001 | http://localhost:3001/api/health | http://localhost:3001/api/health |
| **AI Service** | 8000 | http://localhost:8000/api/health/ | http://localhost:8000/docs |
| **PostgreSQL + pgvector** | 5432 | `pg_isready -U companion_user -d companion_db` | — |

---

## Full-Stack Stack Verification

Run the automated verification script to validate tool registrations, database connectivity, vector extension, Docker configuration, and telemetry:

```bash
npm run verify:stack
```

Or run directly with python:

```bash
ai-service\.venv\Scripts\python.exe scripts/verify_stack.py
# Optional flags:
#   --require-live   (Fails if live HTTP service endpoints are not running)
#   --skip-db        (Skips PostgreSQL connectivity check)
```

---

## Testing & Quality Assurance

Each component features dedicated automated test suites:

```bash
# AI Service (382 tests passing)
cd ai-service
.\.venv\Scripts\python.exe -m pytest -q

# Backend API Gateway (12 tests passing)
npm run test:backend

# Desktop Companion (20 tests passing)
npm run test:desktop

# Observability & Evaluation Suite
cd ai-service
.\.venv\Scripts\python.exe -m pytest tests/test_evaluation.py -q
```

---

## Troubleshooting

### Database Connection Fails
- Verify `companion-postgres` is running: `docker ps --filter name=companion-postgres`.
- If container is stopped, run `npm run docker:db`.
- Check credentials in `.env` and `ai-service/.env`. Ensure `DATABASE_URL` matches `postgresql+asyncpg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:5432/<POSTGRES_DB>`.

### Port Already in Use
- Port 3000: Next.js frontend
- Port 3001: Express backend gateway
- Port 8000: FastAPI AI service
- Port 5432: PostgreSQL database
- Free up blocked ports using Windows Resource Monitor or `netstat -ano | findstr :<port>`.

### Screen Context Permissions in Electron
- Screen context capture requires explicit user confirmation.
- Captures are downscaled (max 1280x720) JPEG thumbnails to preserve memory.
- Screen captures are strictly bound to user interaction; client-supplied flags cannot bypass explicit permission.

### Missing Dependencies
- Run `npm run install:all` to ensure all packages in `frontend/`, `backend/`, `desktop/`, and `ai-service/` are installed.

---

## License

ISC License.

## Author

Aaditya Sharma
