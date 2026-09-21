# Architecture Overview

## System Architecture

The AI Software Engineering Companion is a three-service architecture:

```
┌──────────────────────────────────────────────────────────┐
│                    User / Developer                       │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│              Frontend (Next.js + React)                   │
│                                                           │
│  • Chat interface                                         │
│  • Project explorer                                       │
│  • Task/plan view                                         │
│  • Observability panel                                    │
│  • Port: 3000                                             │
└──────────────────────┬───────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼───────────────────────────────────┐
│             Backend (Node.js + Express)                    │
│                                                           │
│  • API gateway                                            │
│  • Permission manager                                     │
│  • Tool executor (file I/O, shell, Git)                   │
│  • Session manager                                        │
│  • Port: 3001                                             │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼───────────────────────────────────┐
│            AI Service (Python + FastAPI)                   │
│                                                           │
│  • Orchestrator agent                                     │
│  • Planning agent                                         │
│  • Knowledge agent                                        │
│  • Coding agent                                           │
│  • Testing agent                                          │
│  • Debugging agent                                        │
│  • Git agent                                              │
│  • LLM provider abstraction                               │
│  • Embedding provider abstraction                         │
│  • Port: 8000                                             │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│           Storage (PostgreSQL + pgvector)                  │
│                                                           │
│  • Projects, files, code chunks                           │
│  • Memories, decisions, tasks                             │
│  • Conversations, tool executions                         │
│  • Test runs, agent runs                                  │
│  • Vector embeddings for semantic search                  │
└──────────────────────────────────────────────────────────┘
```

## Why Three Services?

| Service | Language | Responsibility | Why this language? |
|---|---|---|---|
| **Frontend** | TypeScript | UI rendering, user interaction | React/Next.js is the standard for rich web UIs |
| **Backend** | TypeScript | Tool execution, permissions, file/shell/Git ops | Node.js excels at file I/O, shell commands, and native Windows integration |
| **AI Service** | Python | LLM orchestration, agents, RAG, embeddings | Python has the richest AI/ML ecosystem (LangChain, OpenAI SDK, etc.) |

Separating the backend from the AI service allows:

1. **Independent scaling** — The AI service can be scaled or replaced without affecting tool execution.
2. **Security boundary** — The backend controls all filesystem/shell access; the AI service only makes requests through it.
3. **Language optimization** — Each service uses the language best suited for its role.
4. **Testability** — Each service can be tested in isolation.

## Knowledge vs Memory

This distinction is fundamental to the system design:

### Knowledge (Current Project)
Information about the project being worked on right now:
- Source code, files, folders
- Architecture, APIs, dependencies
- Documentation, configuration
- Current Git state

### Memory (Learned Engineering Wisdom)
Useful information accumulated from development experience:
- Debugging lessons
- Architectural decisions and their outcomes
- Reusable solutions
- Developer preferences
- Failed approaches and why they failed

**Key rule**: Memory is NEVER blindly applied. The system must:
1. Retrieve potentially relevant memory
2. Compare with current project context
3. Determine actual relevance
4. Present or use appropriately

## Agent Architecture

Agents are not independent LLM services. They are specialized workflows sharing the same underlying LLM with different system prompts, tools, and execution patterns.

| Agent | Role |
|---|---|
| **Orchestrator** | Intent understanding, workflow routing, coordination |
| **Planner** | Task decomposition, risk identification, plan generation |
| **Knowledge** | Project understanding, code/doc retrieval |
| **Coder** | Code generation and modification via tools |
| **Tester** | Test discovery, execution, result interpretation |
| **Debugger** | Error analysis, hypothesis formation, fix proposals |
| **Git** | Repository state inspection, branch/commit management |

## Security Model

- API keys in `.env` only, never committed
- Tool execution with permission tiers (auto-approve / ask-user / deny)
- Filesystem access restricted to project workspace
- No automatic Git push
- No hidden screen capture
- No external data upload without consent
- Audit logging for all tool executions
- Repository content treated as potentially untrusted input
