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

---

## Phase 2: Communication Architecture

Phase 2 establishes the end-to-end communication pipeline across all three services.

### 1. Request Flow (REST Pipeline)

```
[User]
   │  Types message in Chat UI
   ▼
[Next.js Frontend] (port 3000)
   │
   │  POST http://localhost:3001/api/chat
   │  Headers: Content-Type: application/json
   │  Payload: { "message": "...", "conversationId": "..." }
   ▼
[Node.js / Express Backend] (port 3001)
   │  1. Validates body is valid JSON
   │  2. Validates `message` is non-empty trimmed string (returns 400 on error)
   │  3. Validates optional `conversationId`
   │
   │  POST http://localhost:8000/api/chat/
   │  Timeout: 10,000ms (configurable via AI_SERVICE_TIMEOUT_MS)
   │  Payload: { "message": "...", "conversation_id": "..." }
   ▼
[Python / FastAPI AI Service] (port 8000)
   │  1. Pydantic schema validation (`ChatRequest`)
   │  2. Assigns or preserves session UUID
   │  3. Returns deterministic structured response (`ChatResponse`)
   ▼
[Node.js / Express Backend]
   │  1. Validates AI response format (returns 502 on malformed response)
   │  2. Returns normalized envelope: { "status": "success", "data": { ... } }
   ▼
[Next.js Frontend]
   │  Renders assistant message bubble with metadata badges
   ▼
[User]
```

### 2. WebSocket Infrastructure

- **Path**: `ws://localhost:3001/ws`
- **Purpose**: Establishes a persistent bi-directional channel for subsequent phases.
  - In Phase 2: Handles connection lifecycle, handshake confirmation (`type: "connection"`), and heartbeat ping/pong (`type: "ping"` -> `type: "pong"`).
  - In Phase 4/5: Streams LLM response tokens in real-time as they are generated.
  - In Phase 7/8: Streams live tool execution events, agent state transitions, and background status updates to the UI.

### 3. Error Handling Architecture

The system enforces strict error boundaries to prevent sensitive details or stack traces from leaking to the client:

| Scenario | HTTP Status | Error Code | Client Message |
|---|---|---|---|
| **Empty or whitespace message** | `400 Bad Request` | `INVALID_MESSAGE` | Field 'message' is required and must be a non-empty string. |
| **Malformed JSON body** | `400 Bad Request` | `INVALID_REQUEST_BODY` | Request body must be a valid JSON object. |
| **Invalid conversation ID format** | `400 Bad Request` | `INVALID_CONVERSATION_ID` | Field 'conversationId' must be a non-empty string if provided. |
| **AI service unreachable (offline)** | `502 Bad Gateway` | `AI_SERVICE_UNAVAILABLE` | AI service is currently unreachable. Please verify that the AI service is running. |
| **AI service request timeout** | `504 Gateway Timeout` | `GATEWAY_TIMEOUT` | AI service request timed out after Xms. |
| **AI service 5xx or bad schema** | `502 Bad Gateway` | `AI_SERVICE_ERROR` / `MALFORMED_AI_RESPONSE` | Sanitized error without internal stack traces. |

### 4. Environment Variables

| Variable | Service | Default | Description |
|---|---|---|---|
| `PORT` | Backend | `3001` | Express HTTP server port |
| `NODE_ENV` | Backend | `development` | Runtime environment mode |
| `AI_SERVICE_URL` | Backend | `http://localhost:8000` | Target URL for AI service proxying |
| `AI_SERVICE_TIMEOUT_MS` | Backend | `10000` | Timeout threshold for AI service calls |
| `FRONTEND_URL` | Backend | `http://localhost:3000` | Allowed origin for CORS validation |
| `NEXT_PUBLIC_BACKEND_URL` | Frontend | `http://localhost:3001` | REST API base URL for client fetch requests |
| `NEXT_PUBLIC_WS_URL` | Frontend | `ws://localhost:3001/ws` | WebSocket server URL for real-time channel |
| `HOST` | AI Service | `0.0.0.0` | Bind host for FastAPI/uvicorn |
| `DEBUG` | AI Service | `true` | FastAPI debug flag (disables docs in prod) |

---

## Phase 3: Python AI Service Core

Phase 3 refactors the internal Python AI Service into a modular, clean, and testable domain architecture. It decouples business rules from the FastAPI transport layer, preparing a structured foundation for Phase 4 LLM provider integration.

### 1. Internal AI Service Architecture

```
                 [HTTP / REST Request from Backend]
                                 │
                                 ▼
                     FastAPI Router (`app/routers/chat.py`)
                                 │
                     ChatRequest (Pydantic validation)
                                 │
                                 ▼
                    Service Layer (`app/services/chat_service.py`)
                     ┌───────────┴───────────┐
                     ▼                       ▼
          `ConversationManager`       `PromptBuilder`
         (`services/conversation.py`) (`services/prompt.py`)
                     │                       │
           • Session resolution       • System prompt injection
           • Bounded history storage  • History formatting
           • Message role tracking    • Normalized message list
                     │                       │
                     └───────────┬───────────┘
                                 │
                 Structured Response Generation
            (Deterministic mock in Phase 3 / LLM hook in Phase 4)
                                 │
                                 ▼
                   Pydantic `ChatResponse` Model
                                 │
                                 ▼
                     [HTTP / REST 200 OK Response]
```

### 2. Core Abstractions

| Component | File | Responsibility |
|---|---|---|
| **Schemas** | `app/schemas/chat.py` | Typed Pydantic models for request, response, message entities (`ChatMessage`, `MessageRole`), and error envelopes (`ErrorResponse`). |
| **Conversation Manager** | `app/services/conversation.py` | Manages in-memory multi-turn sessions with bounded message retention (`max_conversation_history`), session creation, and message appending. |
| **Prompt Builder** | `app/services/prompt.py` | Assembles normalized message sequences (`system`, `history`, `user`) for LLMs, including optional project context injection. |
| **Chat Service** | `app/services/chat_service.py` | Core orchestrator coordinating input validation, session tracking, prompt construction, response generation, and turn recording. |
| **Custom Exceptions** | `app/exceptions.py` | Domain-level exceptions (`AIServiceException`, `ValidationError`, `SessionNotFoundError`) mapped to structured HTTP responses by centralized handlers. |

### 3. Preparation for Phase 4 (LLM Provider Abstraction)

The `ChatService._generate_reply` method serves as the clean isolation boundary. In Phase 4, this method will delegate to an abstract `LLMProvider` interface (OpenAI, Anthropic, Ollama, etc.) without altering the router, conversation manager, or API contract.


