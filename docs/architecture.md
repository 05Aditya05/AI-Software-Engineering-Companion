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

The `ChatService._generate_reply` method serves as the clean isolation boundary. In Phase 4, this method was refactored to delegate to an abstract `LLMProvider` interface (`GeminiProvider`) without altering the router, conversation manager, or API contract.

---

## Phase 4: Real LLM Integration

Phase 4 integrates Google Gemini (`google-genai` SDK) behind a strict provider abstraction:

```
FastAPI Router / ChatService
        │
        ▼
   LLMProvider (abstract base class in app/providers/base.py)
        │
        ▼
   GeminiProvider (app/providers/gemini.py)
        │
        ├─ Maps application roles (user, assistant, system) -> Gemini API formats
        ├─ Extracts system instructions to GenerateContentConfig
        ├─ Enforces timeouts via HttpOptions
        └─ Converts SDK errors (ClientError, ServerError, APIError) -> LLMProviderError
```

- **Zero Leakage**: No Gemini-specific classes or types escape `app/providers/gemini.py`.
- **Test Isolation**: ChatService, router, and conversation tests use deterministic mock/fake providers; no real API key is required during test runs.
- **Error Mapping**: Provider failures (e.g. 401 Unauthorized, 429 Rate Limit, 500 Service Unavailable) map to structured HTTP 500 errors with machine-readable error codes.

---

## Phase 5: Conversational AI Assistant Persona & Multi-Turn Reasoning

Phase 5 establishes the Software Engineering Companion persona and verifies conversational multi-turn workflows:

- **Persona**: Specialized system prompt instructing the model to act as a pragmatic SE partner focusing on software design, code review, debugging root-cause analysis, and testing strategy.
- **Boundaries**: Explicit disavowal of direct file modifications unless project context is provided; acknowledging uncertainty rather than hallucinating.
- **Turn Accumulation**: Bounded session history retained across turns, enabling follow-up questions and context-aware technical recommendations.

---

## Phase 6: Project Understanding & Context Injection

Phase 6 introduces controlled, read-only project inspection and context injection into conversational prompts:

```
[Incoming Chat Request]
         │
         ▼
FastAPI Router (`app/routers/chat.py`)
         │
         ├─ Check `settings.project_root`
         │
         ├─ If configured:
         │    `ProjectService(root).build_context()`
         │    (walks directory structure, reads prioritized files up to budget caps)
         │
         ▼
`ChatService.process_message(request, project_context=...)`
         │
         ▼
`PromptBuilder.build_prompt_messages(..., project_context=...)`
         │
         ▼
System Prompt with `--- Project Context ---` block injected
         │
         ▼
LLM Provider (`GeminiProvider`)
```

### Safety and Security Guarantees:
1. **Read-Only**: Zero shell execution, zero filesystem writes.
2. **Path Traversal Protection**: All paths resolved against `project_root` with traversal detection (`../` escaping root raises `ValueError`).
3. **Secret Protection**: `.env`, `.env.*`, `secrets.json`, `credentials.json`, private keys (`id_rsa`, etc.) are unconditionally excluded.
4. **Directory Exclusions**: `node_modules`, `.git`, `.venv`, `dist`, `build`, `.next`, `__pycache__` are excluded from traversal.
5. **Budgets & Caps**: Maximum 64 KB per file (`MAX_FILE_BYTES`), maximum 40 files (`MAX_FILES`), maximum 80,000 characters total context (`MAX_CONTEXT_CHARS`).
6. **Graceful Fallback**: If project reading encounters any error or `project_root` is unset, chat continues normally without project context.

---

## Phase 7: Tool System & Permission Engine

Phase 7 introduces structured tool definitions and a permission validation engine:

- **`Tool` Base Class**: Abstract contract specifying `name`, `description`, `permission_level`, `input_schema` (JSON Schema), and `execute(params) -> ToolResult`.
- **`PermissionLevel`**: Enum defining security boundaries (`READ_ONLY`, `WRITE`, `EXECUTE`, `DESTRUCTIVE`). Default agent permissions are capped at `READ_ONLY`.
- **Read-Only Project Inspection Tools**:
  - `read_file`: Reads specific file contents with line-range slicing and size bounds.
  - `list_files`: Recursively lists directories with path traversal guards and file-type filtering.
  - `search_code`: Performs regex or substring searches across indexed project files.
  - `inspect_file`: Returns file metadata (size, line count, extension, permissions).
- **Safe Execution Boundary**: The `ToolRegistry` catches any unexpected tool exception and wraps it in a normalized `ToolResult.fail(code, message)`, preventing unhandled crashes from escaping into the orchestrator.

---

## Phase 8: Agent Orchestration (ReAct Loop)

Phase 8 implements multi-step autonomous reasoning using a ReAct (Reason + Act) loop:

```
User Prompt
     │
     ▼
AgentOrchestrator
     │
     ├─ Step 1: Model generates reasoning + tool call: {"tool": "search_code", "params": {...}}
     │   │
     │   ├─ Registry executes tool safely
     │   └─ Observation injected back into turn context
     │
     ├─ Step 2: Model processes observation -> determines next action or final answer
     │
     └─ Terminates on:
         • Explicit final answer
         • `max_steps` reached (default: 5)
         • Fatal permission violation
```

- **Step Bounding**: Guaranteed termination within `max_steps` to prevent runaway loops or unbounded token consumption.
- **Trace Accumulation**: Step-by-step tool traces recorded in memory for auditability.

---

## Phase 9: RAG & PostgreSQL pgvector Database

Phase 9 integrates persistent semantic search over project knowledge:

- **Vector Storage**: PostgreSQL 17 with the `pgvector` extension running in a containerized environment (`companion-postgres`).
- **Embedding Provider**: `GeminiEmbeddingProvider` using the `gemini-embedding-001` model (768 dimensions).
- **Chunking Pipeline**: `KnowledgeChunker` splits code and markdown documents with configurable token overlap and syntax awareness.
- **Cosine Similarity Retrieval**: `RetrievalService` executes cosine distance vector queries (`<=>` operator) against stored embeddings.
- **Dynamic Tool Registration**: `SemanticSearchTool` is conditionally registered in `ToolRegistry` when both `DATABASE_URL` and `GEMINI_API_KEY` are configured.

---

## Phase 10: Long-Term Memory & Cross-Project Learning

Phase 10 provides a cross-project repository of accumulated engineering wisdom:

- **Memory Entity**: Stores categorized engineering lessons (`decision`, `debugging_lesson`, `solution`, `preference`, `failed_approach`) with vector embeddings.
- **Contextual Filtering**: Learned memory is never blindly injected. Retrieved memories are scored against current project architecture before recommendations are formulated.
- **Tool Integration**: `SearchMemoryTool` allows the ReAct orchestrator to query past lessons relevant to the active problem.

---

## Phase 11: Testing & Debugging Agent Loop

Phase 11 implements autonomous error diagnosis and self-healing proposals:

- **`CodingAgent`**: Specialized workflow that executes test suites via subprocess within sandboxed working directories.
- **Failure Analysis**: Parses pytest, vitest, and tsc error outputs, identifying failing test cases and stack traces.
- **Self-Healing Proposal Loop**: Formulates non-destructive code patches (diff proposals) displayed in the frontend for developer review before any filesystem changes occur.

---

## Phase 12: Git Integration

Phase 12 provides safe, human-in-the-loop source control awareness:

- **`GitService`**: Safe wrapper around Git CLI executing read-only commands (`git status`, `git log`, `git diff`, `git branch`).
- **`GitInfoTool`**: Exposes read-only Git status and history to the conversational agent.
- **Commit Proposals**: Synthesizes conventional commit messages and staged diff summaries without performing autonomous write operations.
- **`GitPanel`**: Dedicated workspace UI component in Next.js displaying repository status, commit logs, and interactive diff viewers.

---

## Phase 13: Windows Desktop Companion

Phase 13 packages the companion as a native Windows desktop experience:

- **Electron 34 Architecture**: Multi-process design separating Node.js main process, secure IPC preload, and isolated renderer window.
- **System Tray**: Persistent Windows notification tray icon with quick actions (Show/Hide, DevTools, Restart Services, Quit).
- **Global Hotkeys**: `Ctrl+Alt+C` global shortcut toggles the desktop companion window from any application.
- **`ProcessManager`**: Probes local service health (`/api/health`) and renders a graceful offline fallback UI while services initialize.

---

## Phase 14: Screen Context & Permissions

Phase 14 allows visual debugging with strict privacy and trust boundaries:

- **Desktop Capturer**: Uses Electron `desktopCapturer.getSources` to capture application windows or displays.
- **Downscaled Previews**: Captures are downscaled to 1280x720 JPEG thumbnails to prevent memory exhaustion and excessive token load.
- **Explicit Trust Boundary**: All screen capture requests require affirmative user selection and confirmation. Client-supplied flags cannot bypass the native dialog.
- **Turn Isolation**: Screen captures are strictly bound to the immediate conversation turn and discarded from subsequent history.

---

## Phase 15: Docker & Infrastructure

Phase 15 provides production-ready containerization for the entire stack:

- **Multi-Stage Dockerfiles**:
  - `ai-service`: `python:3.12-slim` with compiled wheels, non-root user `appuser`, and uvicorn server.
  - `backend`: `node:22-alpine` builder (`tsc`) + minimal runtime, non-root `node` user.
  - `frontend`: `node:22-alpine` Next.js production server, non-root `node` user.
- **Docker Compose Profiles**:
  - Base profile (`docker compose up -d db`): Launches `companion-postgres` (`pgvector/pgvector:pg17`).
  - Full profile (`docker compose --profile full up -d`): Launches all 4 containers with healthcheck dependencies and internal DNS.

---

## Phase 16: Evaluation & Observability

Phase 16 establishes comprehensive instrumentation, telemetry, and evaluation:

```
Chat Turn / Tool Invocation
             │
             ▼
TelemetryService (ai-service/app/services/telemetry.py)
   • Thread-safe bounded deque (100 turns, 200 tool traces)
   • Sensitive data sanitization (API keys, passwords, base64 payloads)
   • Token estimations (~4 chars/token heuristic, labeled explicitly)
             │
             ▼
FastAPI Observability Router (`/api/observability/metrics`, `/traces`)
             │
             ▼
Express API Gateway Proxy (`/api/observability/*`)
             │
             ▼
Frontend ObservabilityPanel (Next.js)
   • Live Service Health Grid (Backend, AI Service, DB, WebSocket)
   • Turn Performance Summary & Token Totals
   • Tool Usage Distribution Chart
   • Audit Trace Table with argument inspection and outcome filters
```

- **Evaluation Benchmark Suite**: Deterministic automated tests in `tests/test_evaluation.py` assessing tool parsing accuracy, permission denial safety, injection resistance, and argument redaction.

---

## Phase 17: Polish, Documentation & Full-Stack Deployment Verification

Phase 17 finalizes the developer experience and system verification:

- **UI Polish**: Standardized loading spinners, empty states, keyboard shortcuts (`Ctrl+Enter`), and error notifications across all 6 workspace panels.
- **Automated Verification Script (`scripts/verify_stack.py`)**:
  - Validates core and optional tool registrations.
  - Verifies PostgreSQL connectivity and `vector` extension status.
  - Validates Docker Compose base and full profiles via `docker compose config`.
  - Verifies telemetry aggregation and secret redaction.
  - Probes live service health endpoints with meaningful exit codes (0 for pass, 1 for failure, 2 for live check failure).




