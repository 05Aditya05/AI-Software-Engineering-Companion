# AI Software Engineering Companion

An AI-powered software engineering companion that lives alongside the developer during software development. It understands your projects, helps plan and write code, runs tests, debugs failures, maintains engineering knowledge, and reuses lessons across projects.

## Vision

This is not a generic chatbot. It is a **contextual engineering partner** designed around:

- **Project Context** — understands your codebase, architecture, and dependencies
- **Knowledge** — indexes and retrieves relevant project information
- **Memory** — remembers engineering lessons and reuses them across projects
- **Tools** — reads files, searches code, runs commands, executes tests
- **Agents** — orchestrates specialized workflows (planning, coding, testing, debugging, Git)
- **Permissions** — human-in-the-loop for risky operations, autonomous for safe ones
- **Desktop Integration** — eventually operates as a Windows desktop companion

## Architecture

```
Frontend (Next.js + React + TypeScript + Tailwind CSS)
    ↕ REST + WebSocket
Backend (Node.js + TypeScript + Express)
    ↕ HTTP
AI Service (Python + FastAPI + Pydantic)
    ↕
PostgreSQL + pgvector (via Docker)
```

## Project Structure

```
AI-Software-Engineering-Companion/
├── frontend/          → Next.js 15 + React + TypeScript + Tailwind CSS
├── backend/           → Node.js + TypeScript + Express API server
├── ai-service/        → Python + FastAPI AI service
├── docs/              → Architecture and design documentation
├── .env.example       → Environment variable template
├── package.json       → Root monorepo scripts
└── .gitignore         → Git exclusions
```

## Quick Start

### Prerequisites

- **Node.js** 24+ and **npm** 11+
- **Python** 3.12+ and **pip**
- **Git** 2.50+

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd AI-Software-Engineering-Companion

# 2. Install frontend dependencies
cd frontend && npm install && cd ..

# 3. Install backend dependencies
cd backend && npm install && cd ..

# 4. Set up Python virtual environment
cd ai-service
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
cd ..

# 5. Configure environment
copy .env.example .env
# Edit .env with your settings
```

### Running Services

From the project root:

```bash
# Frontend (http://localhost:3000)
npm run dev:frontend

# Backend (http://localhost:3001)
npm run dev:backend

# AI Service (http://localhost:8000)
npm run dev:ai
```

### Health Checks

- Frontend: http://localhost:3000
- Backend: http://localhost:3001/api/health
- AI Service: http://localhost:8000/api/health
- AI Service Docs: http://localhost:8000/docs

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React, TypeScript, Tailwind CSS |
| Backend | Node.js, TypeScript, Express |
| AI Service | Python, FastAPI, Pydantic |
| Database | PostgreSQL + pgvector (planned) |
| Desktop | Electron (planned) |
| LLM | Provider-abstracted (OpenAI, Anthropic, etc.) |

## Development Phases

| Phase | Description | Status |
|---|---|---|
| 0 | Environment audit | ✅ Complete |
| 1 | Project skeleton | ✅ Complete |
| 2 | Frontend ↔ Backend communication | 🔲 Planned |
| 3 | Python AI service core | 🔲 Planned |
| 4 | LLM provider abstraction | 🔲 Planned |
| 5 | Basic conversational assistant | 🔲 Planned |
| 6 | Project/codebase understanding | 🔲 Planned |
| 7 | Tool system | 🔲 Planned |
| 8 | Agent orchestration | 🔲 Planned |
| 9 | RAG + Database | 🔲 Planned |
| 10 | Long-term memory | 🔲 Planned |
| 11 | Testing/debugging loop | 🔲 Planned |
| 12 | Git integration | 🔲 Planned |
| 13 | Windows desktop companion | 🔲 Planned |
| 14 | Screen context + permissions | 🔲 Planned |
| 15 | Docker/infrastructure | 🔲 Planned |
| 16 | Evaluation/observability | 🔲 Planned |
| 17 | Polish/documentation/deployment | 🔲 Planned |

## License

ISC

## Author

Aaditya Sharma
