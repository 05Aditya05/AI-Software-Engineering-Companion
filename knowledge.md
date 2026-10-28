# AI Software Engineering Companion — Project Knowledge Base (`knowledge.md`)

> **उद्देश्य (Purpose):** यह फ़ाइल पूरे प्रोजेक्ट की अब तक की प्रोग्रेस, आर्किटेक्चर, सर्विसेज़, कॉन्फ़िगरेशन, टेस्टिंग और आगे के फेज़ेज़ का कम्प्लीट नॉलेज बेस है, ताकि डेवलपमेंट और डिबगिंग में हमेशा पूरी मदद मिले।

---

## 1. प्रोजेक्ट ओवरव्यू (Project Overview)

**AI Software Engineering Companion** एक प्रोडक्शन-ग्रेड 3-टियर आर्किटेक्चर वाला AI असिस्टेंट है जो सॉफ़्टवेयर डेवलपर्स के लिए डिज़ाइन, आर्किटेक्चर, कोड रिव्यू, डिबगिंग, टेस्टिंग स्ट्रेटेजी और प्रोजेक्ट समझ में एक सच्चा साथी (Companion) बनता है।

### 3-टियर आर्किटेक्चर (Three-Service Architecture)

```
┌───────────────────────────────────────────────────────────────┐
│               1. Frontend (Next.js + React)                   │
│  - पोर्ट: 3000                                                │
│  - चैट UI, प्रोजेक्ट एक्सप्लोरर, टास्क प्रोग्रेस, WebSocket स्टेटस │
└──────────────────────────────┬────────────────────────────────┘
                               │ HTTP / WebSocket (REST + WS)
┌──────────────────────────────▼────────────────────────────────┐
│               2. Backend (Node.js + Express + TS)             │
│  - पोर्ट: 3001                                                │
│  - API गेटवे, इनपुट वैलिडेशन, प्रॉक्सी, एरर हैंडलिंग, WS सर्वर  │
└──────────────────────────────┬────────────────────────────────┘
                               │ HTTP (REST)
┌──────────────────────────────▼────────────────────────────────┐
│               3. AI Service (Python + FastAPI)                │
│  - पोर्ट: 8000                                                │
│  - LLM प्रोवाइडर (Google Gemini 2.0 Flash)                   │
│  - प्रोजेक्ट अंडरस्टैंडिंग (ProjectService - सुरक्षित फ़ाइल एनालिसिस) │
│  - इन-मेमोरी कन्वर्सेशन हिस्ट्री और सेशन ट्रैकिंग             │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. अब तक के पूरे हुए फेज़ (Completed Phases Summary)

| Phase | Git Commit | मुख्य कार्य (Key Accomplishments) |
|---|---|---|
| **Phase 1** | `2e7cece` | **Project Skeleton**: तीनों सर्विसेज़ (Frontend, Backend, AI Service) का बेसिक ढाँचा, पैकेज और निर्भरताएँ सेटअप की गईं। |
| **Phase 2** | `4187330` | **Inter-Service Communication**: Frontend ↔ Backend ↔ AI Service का पूरा एंड-टू-एंड फ्लो, WebSocket `/ws` और REST `/api/chat` गेटवे तैयार किया गया। |
| **Phase 3** | `be06e8a` | **AI Service Core**: FastAPI सर्विस का क्लीन आर्किटेक्चर: Pydantic स्कीमाज़, `ConversationManager`, `PromptBuilder`, `ChatService` और सेंट्रलाइज़्ड एक्सेप्शन हैंडलिंग। |
| **Phase 4** | `0e97ada` | **Real LLM Integration**: Google Gemini (`google-genai` SDK) का इंटीग्रेशन। `LLMProvider` एब्सट्रैक्शन, `GeminiProvider`, रोल मैपिंग (`user`, `model`, `system`), टाइमआउट और एरर कन्वर्जन। |
| **Phase 5** | `22f75e6` | **Conversational AI Assistant Persona**: SE Companion का व्यवहार, स्पष्ट बाउंड्रीज़ (झूठा क्लेम न करना, अनिश्चितता स्वीकारना), और मल्टी-टर्न चैट हिस्ट्री रिटेंशन। |
| **Phase 6** | `d6460cd` | **Project Understanding & Context Injection**: `ProjectService` बनाया गया जो प्रोजेक्ट रूट से सेफ, रीड-ओनली फ़ाइलें और स्ट्रक्चर पढ़कर LLM प्रॉम्प्ट में इंजेक्ट करता है। |
| **Phase 7** | `3c7bfa6` | **Read-Only Tool System**: `ToolRegistry`, `PermissionLevel`, और 4 रीड-ओनली टूल्स (`list_files`, `read_file`, `search_code`, `inspect_file`) का सुरक्षित एग्जीक्यूशन फ्रेमवर्क (36 टेस्ट्स)। |
| **Phase 8** | `b47aa8a` | **Agent Orchestration**: `AgentOrchestrator` जो LLM और ToolRegistry के बीच बाउंडेड लूप (अधिकतम 3 स्टेप्स), सुरक्षित JSON डिसीजन पार्सिंग, टूल प्रॉम्प्ट इंजेक्शन, और ChatService इंटीग्रेशन प्रदान करता है (19 टेस्ट्स)। |

---

## 3. फ़ाइल स्ट्रक्चर और मुख्य डायरेक्टरीज़ (Core Structure)

```
AI-Software-Engineering-Companion/
├── knowledge.md                  <-- यह नॉलेज बेस फ़ाइल
├── docs/
│   └── architecture.md           <-- विस्तृत तकनीकी आर्किटेक्चर दस्तावेज़
│
├── frontend/                     <-- Next.js 16 + React 19 + TypeScript
│   ├── src/app/
│   │   ├── page.tsx              <-- मुख्य चैट UI इंटरफ़ेस
│   │   └── api/health/route.ts   <-- हेल्थ चेक
│   └── package.json
│
├── backend/                      <-- Express + TypeScript
│   ├── src/
│   │   ├── app.ts                <-- एक्सप्रेस ऐप, मिडलवेयर, रूट्स
│   │   ├── server.ts             <-- HTTP व WebSocket सर्वर बूटस्ट्रैप
│   │   ├── routes/chat.ts        <-- AI Service को रिक्वेस्ट भेजने वाला रूट
│   │   └── websocket/index.ts    <-- लाइव WebSocket कनेक्शन हैंडलर
│   └── package.json
│
└── ai-service/                   <-- FastAPI + Python 3.14 (Virtualenv: .venv)
    ├── app/
    │   ├── main.py               <-- FastAPI ऐप और सेंट्रलाइज़्ड एरर हैंडलर्स
    │   ├── config.py             <-- Pydantic Settings (ENV लोडर)
    │   ├── exceptions.py         <-- डोमेन एक्सेप्शन्स (LLMProviderError, ValidationError)
    │   ├── schemas/chat.py       <-- Pydantic मॉडल्स (ChatRequest, ChatResponse, ChatMessage)
    │   ├── providers/
    │   │   ├── base.py           <-- LLMProvider एब्सट्रैक्ट क्लास व LLMResponse
    │   │   └── gemini.py         <-- Google Gemini SDK प्रोवाइडर
    │   ├── tools/                <-- [Phase 7] टूल सिस्टम
    │   │   ├── base.py           <-- PermissionLevel, ToolDefinition, ToolResult
    │   │   ├── registry.py       <-- ToolRegistry (रजिस्ट्रेशन, परमिशन चेक, एग्जीक्यूशन)
    │   │   └── project_tools.py  <-- 4 रीड-ओनली टूल्स (list_files, read_file, search_code, inspect_file)
    │   ├── services/
    │   │   ├── chat_service.py   <-- कोर चैट सर्विस (Phase 8 में ToolRegistry व Orchestrator सपोर्ट)
    │   │   ├── agent_orchestrator.py <-- [Phase 8] एजेंटिक लूप, JSON पार्सर, टूल कॉलिंग इंजन
    │   │   ├── conversation.py   <-- इन-मेमोरी सेशन व हिस्ट्री मैनेजर
    │   │   ├── prompt.py         <-- प्रॉम्प्ट बिल्डर व कॉन्टेक्स्ट कंपोज़र
    │   │   └── project_service.py<-- सेफ रीड-ओनली फ़ाइल व स्ट्रक्चर स्कैनर
    │   └── routers/chat.py       <-- /api/chat/ एंडपॉइंट (टूल रजिस्ट्री व प्रॉम्प्ट इंजेक्शन)
    ├── tests/                    <-- 139 कम्प्लीट यूनिट/इंटीग्रेशन टेस्ट्स (Phase 1-8)
    │   ├── test_tools.py         <-- Phase 7 के 36 टेस्ट्स
    │   └── test_agent_orchestrator.py <-- Phase 8 के 19 टेस्ट्स
    └── requirements.txt
```

---

## 4. एनवायरनमेंट सेटिंग्स (.env Configuration)

### अति-महत्वपूर्ण: Gemini Model Name
> ⚠️ **IMPORTANT NOTE ON GEMINI MODEL:**
> Google Gemini API में मॉडल का नाम हमेशा सही और ऑफिशियल होना चाहिए:
> - ✅ **मान्य नाम (Valid):** `gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`
> - ❌ **अमान्य नाम (Invalid):** `gemini-3.8-flash` (यह API द्वारा 500 / Server Error या Not Found देगा क्योंकि यह मॉडल API में मौजूद नहीं है)।

### `ai-service/.env` (Python AI Service)
```ini
HOST=0.0.0.0
PORT=8000
DEBUG=true
BACKEND_URL=http://localhost:3001

# Gemini LLM Provider (Phase 4)
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
LLM_TIMEOUT_MS=30000

# Project Understanding (Phase 6)
# प्रोजेक्ट का एब्सोल्यूट पाथ (अगर खाली छोड़ेंगे तो बिना कोड कॉन्टेक्स्ट के नॉर्मल चैट चलेगी)
PROJECT_ROOT=e:\AI-Software-Engineering-Companion
```

### `backend/.env` (Node.js Backend)
```ini
PORT=3001
NODE_ENV=development
AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_TIMEOUT_MS=30000
FRONTEND_URL=http://localhost:3000
```

### `frontend/.env.local` (Next.js Frontend)
```ini
NEXT_PUBLIC_BACKEND_URL=http://localhost:3001
NEXT_PUBLIC_WS_URL=ws://localhost:3001/ws
```

---

## 5. सर्विसेज़ को लोकली रन करने के कमांड्स (How to Run Services)

### 1. AI Service (Python FastAPI)
```powershell
cd e:\AI-Software-Engineering-Companion\ai-service
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- URL: `http://localhost:8000`
- Health check: `http://localhost:8000/api/health/`
- Docs: `http://localhost:8000/docs`

### 2. Backend Service (Node.js Express)
```powershell
cd e:\AI-Software-Engineering-Companion\backend
npm run dev
```
- URL: `http://localhost:3001`
- Health check: `http://localhost:3001/api/health`

### 3. Frontend (Next.js)
```powershell
cd e:\AI-Software-Engineering-Companion\frontend
npm run dev
```
- URL: `http://localhost:3000`

---

## 6. टेस्टिंग और वेरिफिकेशन चीटशीट (Testing & Verification)

### AI Service Tests (Pytest)
सारे 139 टेस्ट्स (Phase 1-8) चलाने के लिए:
```powershell
cd e:\AI-Software-Engineering-Companion\ai-service
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

### Backend Build
```powershell
cd e:\AI-Software-Engineering-Companion\backend
npm run build
```

### Frontend Build
```powershell
cd e:\AI-Software-Engineering-Companion\frontend
npm run build
```

### PowerShell से सीधा API टेस्ट करना:
```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/chat/" `
  -ContentType "application/json" `
  -Body '{"message":"Hello Companion! Explain what you can currently do in this project."}'
```

---

## 7. फेज़ 6: सुरक्षा और सीमाएँ (Security & Boundaries Enforced)

Phase 6 (`ProjectService`) में कई सुरक्षा लेयर्स लगाई गई हैं:
1. **Read-Only Enforced:** यह सर्विस केवल फ़ाइलें पढ़ती है; किसी भी फ़ाइल को मॉडिफाई या डिलीट नहीं कर सकती। कोई शेल कमांड रन नहीं होता।
2. **Path Traversal Protection:** `../` या बाहर के पाथ से प्रोजेक्ट रूट से बाहर जाने की कोई भी कोशिश `ValueError` द्वारा ब्लॉक हो जाती है।
3. **Secret Files Protection:** `.env`, `.env.*`, `secrets.json`, `credentials.json`, `id_rsa` जैसी सेंसिटिव फ़ाइलें कभी नहीं पढ़ी जातीं।
4. **Directory Exclusions:** `node_modules`, `.git`, `.venv`, `dist`, `build`, `.next`, `__pycache__` को स्कैनिंग से बाहर रखा गया है।
5. **Budget & Caps:** 
   - प्रति फ़ाइल अधिकतम साइज़: **64 KB**
   - अधिकतम पढ़ी जाने वाली फ़ाइलें: **40**
   - कुल कॉन्टेक्स्ट लिमिट: **80,000 कैरेक्टर्स**
6. **Graceful Fallback:** यदि `PROJECT_ROOT` कॉन्फ़िगर नहीं है या पाथ गलत है, तो भी चैट क्रैश नहीं होती बल्कि बिना प्रोजेक्ट कॉन्टेक्स्ट के सहज रूप से काम करती है।

---

## 8. फेज़ 7: रीड-ओनली टूल सिस्टम (Phase 7: Read-Only Tool System Deep Dive)

### 8.1 आर्किटेक्चर और कोर कंपोनेंट्स (`app/tools/`)
Phase 7 में AI Service के अंदर एक सुरक्षित, एक्सटेंसिबल और रीड-ओनली टूल सिस्टम लागू किया गया:

1. **`PermissionLevel` Enum (`app/tools/base.py`):**
   - `READ_ONLY`: सुरक्षित निरीक्षण टूल्स (फ़ाइल लिस्टिंग, पढ़ना, कोड खोजना, मेटाडेटा)।
   - `PROMPT_CONFIRM`: वे ऑपरेशन्स जिनमें यूजर की मंज़ूरी आवश्यक होगी (भविष्य के फेज़ेज़ के लिए)।
   - `EXECUTE_COMMAND`: शेल या टर्मिनल कमांड्स (सख्ती से नियंत्रित)।
   - `ADMIN`: सिस्टम-लेवल या हाई-इम्पैक्ट एक्शन।
   *वर्तमान गारंटी:* वर्तमान फेज़ केवल और केवल `READ_ONLY` टूल्स को ही रजिस्टर और एग्जीक्यूट करने की अनुमति देता है।

2. **`ToolResult` Dataclass (`app/tools/base.py`):**
   - हर टूल का रिस्पॉन्स स्ट्रक्चर्ड और प्रिडिक्टेबल होता है:
     ```python
     ToolResult.ok(tool_name="...", data={...}, metadata={...})
     ToolResult.fail(tool_name="...", code="...", message="...", details={...})
     ```
   - यह JSON सीरियलाइज़ेबल है और Pydantic के साथ पूरी तरह संगत है।

3. **`ToolRegistry` (`app/tools/registry.py`):**
   - टूल्स का सेंट्रलाइज़्ड कैटलॉग।
   - टूल एग्जीक्यूट करने से पहले परमिशन लेवल चेक करता है (`max_allowed_permission`).
   - अगर कोई टूल `READ_ONLY` से ज़्यादा परमिशन मांगता है या अनरजिस्टर्ड है, तो `TOOL_PERMISSION_DENIED` या `TOOL_NOT_FOUND` एरर लौटाता है, सर्विस क्रैश नहीं होती।

### 8.2 उपलब्ध 4 रीड-ओनली टूल्स (`app/tools/project_tools.py`)

| टूल का नाम | काम (Description) | इनपुट पैरामीटर्स (Args) | सुरक्षा नियम |
|---|---|---|---|
| `list_files` | प्रोजेक्ट फ़ोल्डर का स्ट्रक्चर देखना | `path: str = "."`, `max_depth: int = 3` | डायरेक्टरी एक्सक्लूज़न (`.git`, `node_modules`, `.venv`), पाथ ट्रैवर्सल ब्लॉक |
| `read_file` | किसी विशिष्ट फ़ाइल का कंटेंट पढ़ना | `path: str` | 64 KB साइज़ लिमिट, सीक्रेट फ़ाइलें ब्लॉक, सिर्फ़ टेक्स्ट फ़ाइलें |
| `search_code` | प्रोजेक्ट में किसी शब्द/कोड को खोजना | `query: str`, `path: str = "."`, `max_results: int = 20`, `case_sensitive: bool = False` | सुरक्षित रीजीप-समान सर्च, एक्सक्लूडेड फ़ोल्डर्स को स्किप करना |
| `inspect_file` | फ़ाइल का मेटाडेटा जानना | `path: str` | पाथ ट्रैवर्सल और सीक्रेट ब्लॉक, साइज़/लाइन्स/एक्सटेंशन/MTime लौटाना |

---

## 9. फेज़ 8: एजेंट ऑर्केस्ट्रेशन और टूल लूप (Phase 8: Agent Orchestration Deep Dive)

### 9.1 एजेंटिक रीज़निंग लूप (`app/services/agent_orchestrator.py`)
एजेंट ऑर्केस्ट्रेटर LLM और `ToolRegistry` के बीच एक नियंत्रित, बाउंडेड लूप (Bounded Loop) चलाता है:

```
User Prompt (+ Project Context + Tool Instructions)
                      │
                      ▼
            ┌───────────────────┐
            │   LLM Provider    │ ◄──────────────────────────────┐
            └─────────┬─────────┘                                │
                      │                                          │
            [LLM Response / Decision]                            │
                      │                                          │
         Is it a Tool Call or Final Answer?                      │
                      │                                          │
      ┌───────────────┴───────────────┐                          │
      ▼                               ▼                          │
[Tool Call JSON]               [Final Answer]                    │
      │                               │                          │
Step < MAX_TOOL_STEPS (3)?            ▼                          │
      │ No ──► Force Final Prompt ─► Return                      │
      │ Yes                                                      │
      ▼                                                          │
ToolRegistry.execute()                                           │
      │                                                          │
[Tool Result Formatted] ─────────────────────────────────────────┘
```

### 9.2 टूल प्रॉम्प्ट का प्रारूप (Exact Tool Prompt Format)
जब प्रोजेक्ट रूट सेट होता है, तो `build_tool_prompt_section` द्वारा सिस्टम प्रॉम्प्ट में निम्न निर्देश जोड़े जाते हैं:

```text
You have access to the following read-only project inspection tools.
When you need to answer a question about this project's source code, structure, or files, you MUST use these tools rather than guessing.

To use a tool, respond with ONLY a JSON block in this exact format:
{"action": "tool", "tool": "<tool_name>", "arguments": {<args>}}

Available tools:
  - list_files: List files and directories within the project workspace.  Args: ['path', 'max_depth']
  - read_file: Read the content of a project file (up to 64 KB).  Args: ['path']
  - search_code: Search for a text string or code pattern across project files.  Args: ['query', 'path', 'max_results', 'case_sensitive']
  - inspect_file: Inspect a file's metadata (size, lines, extension, modification time) without reading full content.  Args: ['path']

Rules:
- All tools are read-only. You cannot modify, create, or delete files.
- You cannot execute shell commands.
- Do NOT invent file contents. Use tools to obtain real data.
- Tool results are authoritative. If a tool says a file does not exist, it does not exist.
- If you do NOT need project information, answer directly without a tool call.
- When answering, clearly state if information is unavailable.
```

### 9.3 टूल कॉल JSON और पार्सिंग लॉजिक
1. **टूल कॉल इनवोकेशन सिंटैक्स:**
   ```json
   {
     "action": "tool",
     "tool": "search_code",
     "arguments": {
       "query": "ChatService",
       "path": "."
     }
   }
   ```
2. **पार्सर की सहनशीलता (Robust Parsing):**
   - ```` ```json ... ``` ```` वाले मार्कडाउन ब्लॉक को ऑटोमैटिकली डिटेक्ट करता है।
   - सीधे टेक्स्ट में एम्बेडेड `{ ... }` को भी खोज निकालता है।
   - यदि JSON अमान्य है, `action != "tool"`, या `tool` नाम गायब है, तो यह बिना क्रैश हुए इसे डायरेक्ट आंसर (Final Answer) मानकर यूजर को लौटा देता है।

3. **लूप फीडबैक साइकिल (`[Tool Result]`):**
   टूल रन होने के बाद उसका रिजल्ट LLM को इस फॉर्मेट में मिलता है:
   ```text
   [Tool Result]
   {
     "success": true,
     "tool_name": "read_file",
     "data": {
       "path": "src/app.py",
       "content": "def main():\n    return 'Hello World'\n"
     }
   }
   ```

4. **हार्ड स्टेप लिमिट (`MAX_TOOL_STEPS = 3`):**
   - एक रिक्वेस्ट पर अधिकतम 3 टूल कॉल्स की अनुमति है।
   - 3 स्टेप्स पूरे होने पर ऑर्केस्ट्रेटर LLM को स्पष्ट संदेश भेजता है: *"You have used the maximum number of tool calls. Please provide your final answer now based on the information gathered so far."*
   - **डिफेंसिव प्रोटेक्शन:** यदि इसके बाद भी LLM फिर से टूल कॉल करता है, तो ऑर्केस्ट्रेटर टूल रन नहीं करता, बल्कि सुरक्षित फॉलबैक संदेश लौटा देता है।

### 9.4 ChatService व API इंटीग्रेशन
- `ChatService.process_message(..., tool_registry=...)`:
  - जब `tool_registry` मौजूद होता है, तो कॉल `AgentOrchestrator` के ज़रिए जाती है।
  - जब `tool_registry` नहीं होता, तो Phase 5/6 का डायरेक्ट-LLM पाथ चलता है (जीरो रिग्रेशन)।
  - रिस्पॉन्स मेटाडेटा में `agent_steps_used` और `agent_tool_calls` दर्ज होते हैं।
- `routers/chat.py`:
  - `_get_tool_registry()` द्वारा लेज़ी-इनिशियलाइज़्ड रजिस्ट्री बनाता है।
  - `default_chat_service` को ही टूल रजिस्ट्री इंजेक्ट करके इस्तेमाल करता है, जिससे टेस्ट्स में प्रोवाइडर मॉकिंग पूरी तरह बनी रहती है।

---

## 10. सामान्य समस्याएं और समाधान (Common Gotchas & Troubleshooting)

1. **`LLM_SERVER_ERROR` या 500 एरर आना:**
   - **कारण:** `.env` में `GEMINI_MODEL=gemini-3.8-flash` लिखा होना।
   - **समाधान:** इसे बदलकर `GEMINI_MODEL=gemini-2.0-flash` करें और uvicorn सर्वर को रीस्टार्ट करें।
2. **PowerShell में Python पाथ:**
   - Windows पर सीधे `python` चलाने के बजाय हमेशा वर्चुअल एनवायरनमेंट वाला एग्जीक्यूटबल उपयोग करें: `.\.venv\Scripts\python.exe`.
3. **API Key की सुरक्षा:**
   - अपनी असली API Key को कभी भी Git में कमिट न करें। असली की हमेशा केवल लोकल `.env` में रखें, जो `.gitignore` में सुरक्षित है।
4. **LLMResponse instantiation में `raw` कीवर्ड:**
   - `LLMResponse` क्लास (`app/providers/base.py`) में केवल 3 फ़ील्ड्स हैं: `text`, `model`, `provider`। कभी भी `raw={}` पास न करें।
5. **यूनिट टेस्ट्स में Singleton Services:**
   - `default_chat_service` को ही हमेशा इम्पोर्ट और टेस्ट्स में मॉकिंग के लिए उपयोग करें ताकि रूटर्स और सर्विस लेयर एक ही प्रोवाइडर इंस्टैंस शेयर करें।
6. **Gemini 429 Quota / Rate Limit Handling:**
   - जब Google Gemini API पर फ्री टियर कोटा समाप्त होता है (HTTP 429 `RESOURCE_EXHAUSTED`), तो AI Service इसे जेनेरिक 500 बनाने के बजाय HTTP 429 `LLM_RATE_LIMIT` के रूप में लौटाती है।
   - Backend इस एरर कोड को ड्रॉप करने के बजाय Frontend को फॉरवर्ड करता है।
   - Frontend इसे तुरंत पहचानकर स्पष्ट निर्देश दिखाता है: *"Gemini API quota/rate limit exceeded. Please retry later or use another configured model/provider."* (10 सेकंड के गलत टाइमआउट की जगह तत्काल रिस्पॉन्स)।
7. **Agent Orchestration Timeout (`aiServiceTimeoutMs`):**
   - Agentic Tool Loops में एकाधिक LLM कॉल्स (प्लानिंग + ऑब्जर्वेशन + फाइनल आंसर) होती हैं।
   - Backend का डिफ़ॉल्ट टाइमआउट 10s से बढ़ाकर 60s किया गया है ताकि वैध टूल लूप 10 सेकंड पर prematurely abort न हो।

---

## 11. फेज़ 8 E2E वेरिफिकेशन रिपोर्ट (Phase 8 Full Verification)

Phase 8 की लाइव E2E टेस्टिंग (End-to-End) सफलतापूर्वक संपन्न हो गई है। इसका फाइनल कमिट है: **`247dc68`**

### वेरिफिकेशन परिणाम (Verification Results):
- **Real Gemini E2E Succeeded:** लाइव Gemini मॉडल के साथ सफलतापूर्वक टेस्ट पास हुआ।
- **Actual Tool Flow Used:** एजेंट ने अपनी स्वेच्छा से 2 स्टेप्स लिए: पहले `search_code` (GeminiProvider कहाँ है खोजने के लिए), और फिर `read_file` (पूरी क्लास पढ़कर सही उत्तर देने के लिए)। 
- **Tests Passed:** कुल 140 Python (Pytest) यूनिट व इंटीग्रेशन टेस्ट्स 100% पास हुए।
- **Builds Passed:** Backend (`tsc`) और Frontend (`next build`) दोनों के प्रोडक्शन बिल्ड्स सफलतापूर्वक पास हुए।
- **429 Quota Propagation Verified:** जब टूल लूप के बाद लाइव Gemini API का फ्री-टीयर कोटा खत्म हुआ, तो `HTTP 429` (Rate Limit Exceeded) बिना किसी हैंग या क्रैश के AI Service → Backend → Frontend तक सही UI मैसेज के साथ सफलतापूर्वक प्रोपगेट हुआ।

### वर्तमान स्थिति और अगला कदम (Project Status)
- **Status:** Phase 1 से लेकर Phase 8 तक का पूरा काम 100% वेरिफाई और कमिट हो चुका है।
- **Next Phase:** अब प्रोजेक्ट **Phase 9** (Project Knowledge / RAG Foundation) के लिए तैयार है।

---

## 12. फेज़ 9: Project Knowledge / RAG Foundation (PLANNING ONLY)

Phase 9 का उद्देश्य AI Companion को "Project Knowledge" से लैस करना है, जिससे वह पूरे प्रोजेक्ट को समझे बिना सारी फ़ाइलें एक साथ LLM को भेजे। इसके लिए RAG (Retrieval-Augmented Generation) पाइपलाइन का निर्माण किया जाएगा।

### 12.1 Project Knowledge vs Long-Term Memory (स्पष्ट सीमा)
- **Project Knowledge (Phase 9):** यह केवल वर्तमान प्रोजेक्ट का "तथ्यात्मक सत्य" है (जैसे सोर्स कोड, आर्किटेक्चर डॉक्स, API कॉन्ट्रैक्ट्स)। यदि कोई फ़ाइल डिलीट होती है, तो उसका नॉलेज भी सिस्टम से हट जाना चाहिए। 
- **Long-Term Memory (भविष्य के फेज़):** यह डेवलपर की प्राथमिकताएं, पिछली गलतियों से सीखे गए सबक (lessons learned), और डिबगिंग सेशंस का सारांश है जो फ़ाइल डिलीट होने के बाद भी बरकरार रहता है।
*Phase 9 पूरी तरह से Project Knowledge पर केंद्रित होगा।*

### 12.2 Indexing Strategy (क्या इंडेक्स होगा और क्या नहीं)
**क्या इंडेक्स होगा (Included):**
- सोर्स कोड (Python, TypeScript, JS, TSX, HTML, CSS, etc.)
- दस्तावेज़ (Markdown, README, आर्किटेक्चर डॉक्स)
- कॉन्फ़िगरेशन डॉक्स (अगर सेंसिटिव नहीं हैं)

**क्या इंडेक्स नहीं होगा (Excluded - Security First):**
- `.env`, `secrets.json`, `.pem`, और अन्य क्रेडेंशियल्स।
- `node_modules`, `.venv`, `__pycache__`, `.git`, `dist`, `build`, `.next` (बिल्ड और डिपेंडेंसी फ़ोल्डर्स)।
- इमेजेज़, बाइनरीज़, और जेनरेटेड फ़ाइलें (जैसे `package-lock.json`, `poetry.lock`)।
*(Phase 6 का `ProjectService` पहले से ही इन एक्सक्लूज़न को मैनेज करता है, RAG उसी का उपयोग करेगा।)*

### 12.3 Chunking Strategy
- **Approach:** Syntax-aware और Line-based chunking का हाइब्रिड।
- **Limit:** 500-1000 टोकन्स (लगभग 2000-4000 कैरेक्टर्स) प्रति चंक, 10-15% ओवरलैप के साथ ताकि कॉन्टेक्स्ट न टूटे।
- **Metadata:** हर चंक के साथ मेटाडेटा स्टोर किया जाएगा: `file_path`, `line_start`, `line_end`, `commit_hash` (या `mtime`), और `chunk_index`।

### 12.4 Embedding Strategy
- **Provider:** Google Gemini Embeddings (`text-embedding-004` या समान) का उपयोग किया जाएगा क्योंकि हम पहले से ही Gemini का उपयोग कर रहे हैं। 
- **Abstraction:** एक `EmbeddingProvider` इंटरफ़ेस बनाया जाएगा (जैसे `LLMProvider` है) ताकि भविष्य में OpenAI या लोकल मॉडल्स पर स्विच करना आसान हो।
- **Batching:** API रेट लिमिट्स (429) से बचने के लिए एम्बेडिंग्स को छोटे बैचेज़ (उदा. 50 चंक्स प्रति बैच) में प्रोसेस किया जाएगा।

### 12.5 Vector Storage (PostgreSQL + pgvector)
- **क्यों PostgreSQL + pgvector?** 
  - यह एक रिलायबल, ACID-कंप्लायंट डेटाबेस है। 
  - `pgvector` सीधा SQL से सिमेंटिक सर्च (`<->`, `<#>`, `<=>`) की अनुमति देता है।
  - अलग से Pinecone/Milvus जैसी सर्विस मैनेज करने की ज़रूरत नहीं है।
  - इसमें हम मेटाडेटा पर नॉर्मल SQL फ़िल्टरिंग (जैसे `file_path LIKE 'backend/%'`) और वेक्टर सर्च को एक साथ जोड़ सकते हैं।
- **Schema:** एक `project_knowledge` टेबल होगी जिसमें `id`, `file_path`, `content`, `metadata` (JSONB), और `embedding` (VECTOR) कॉलम्स होंगे। इंडेक्सिंग के लिए HNSW (Hierarchical Navigable Small World) इंडेक्स का उपयोग किया जाएगा।

### 12.6 Retrieval Strategy
- **Flow:** Query → Embedding → HNSW Vector Search (Top-K) → Metadata Filtering → Chunks → Context Injection.
- **Top-K:** टॉप 5-10 प्रासंगिक चंक्स निकाले जाएंगे ताकि प्रॉम्प्ट का कॉन्टेक्स्ट साइज़ लिमिट में रहे।
- **Threshold:** एक सिमिलैरिटी थ्रेशोल्ड (e.g., 0.7) सेट किया जाएगा ताकि अप्रासंगिक चंक्स LLM को न भेजे जाएं।

### 12.7 Incremental Re-indexing
- पूरे प्रोजेक्ट को बार-बार एम्बेड करने से बचने के लिए, फ़ाइल की `mtime` (Modification Time) या Git Hash को ट्रैक किया जाएगा।
- **New/Modified:** केवल बदली गई या नई फ़ाइलों को ही दोबारा चंक और एम्बेड किया जाएगा।
- **Deleted:** डेटाबेस से पुरानी फ़ाइलों के चंक्स को डिलीट कर दिया जाएगा।

### 12.8 Integration with AgentOrchestrator
- **हाइब्रिड अप्रोच:** RAG रिट्रीवल को एक नए टूल `semantic_search` के रूप में `ToolRegistry` में रजिस्टर किया जाएगा।
- `AgentOrchestrator` आवश्यकता पड़ने पर (जैसे "how does authentication work?") इस टूल को कॉल करेगा, बिल्कुल वैसे ही जैसे वह `search_code` का उपयोग करता है। इससे LLM खुद तय करेगा कि उसे सटीक कीवर्ड सर्च चाहिए या सिमेंटिक सर्च।

### 12.9 Docker Usage
- **Docker Desktop:** इसका उपयोग **केवल** PostgreSQL + pgvector के कंटेनर को होस्ट करने के लिए किया जाएगा। 
- हम नेटिव PostgreSQL इंस्टॉल नहीं करेंगे ताकि डेवलपर की मशीन क्लीन रहे और `docker-compose.yml` से कोई भी एक कमांड में डेटाबेस स्टार्ट कर सके।

### 12.10 Phase 9 Implementation Milestones

- **Phase 9.1: Infrastructure & DB Setup** (Docker Compose for Postgres+pgvector, SQLAlchemy models).
- **Phase 9.2: Embedding Provider Abstraction** (Gemini Embeddings integration).
- **Phase 9.3: Knowledge Ingestion & Chunking** (File reading, chunking logic, sync mechanism).
- **Phase 9.4: Vector Indexing & Storage** (Saving chunks to DB with metadata).
- **Phase 9.5: Semantic Retrieval Engine** (Vector search queries, similarity scoring).
- **Phase 9.6: Agent Integration** (`semantic_search` tool for ToolRegistry).
- **Phase 9.7: Incremental Sync** (Automatically tracking changes and updating DB).

### 12.11 Dependencies to Install (Not Installed Yet)
1. **Docker Desktop**: डेटाबेस रन करने के लिए।
2. **PostgreSQL / pgvector image**: `ankane/pgvector` (Docker image).
3. **Python Libraries (AI Service)**:
   - `sqlalchemy`: ORM के लिए।
   - `asyncpg` या `psycopg2-binary`: PostgreSQL ड्राइवर्स।
   - `pgvector`: SQLAlchemy के लिए Python एक्सटेंशन।
   - *Note: LangChain/LlamaIndex का उपयोग नहीं किया जाएगा। हम इसे कस्टम, क्लीन और लाइटवेट रखेंगे।*

---

## 13. Phase 9.1 Implementation Progress (2026-10-10)

- Added `SQLAlchemy[asyncio]`, `asyncpg`, and `pgvector` to `ai-service/requirements.txt`.
- Added a secret-typed `DATABASE_URL` setting and a placeholder example in `ai-service/.env.example`. Keep the real URL/password in a local ignored env file; do not print or commit it.
- Added lazy async engine/session helpers in `ai-service/app/db.py`. Importing the service does not connect to PostgreSQL. No schema creation or migration runs automatically.
- Added SQLAlchemy `ProjectKnowledge` model with file path, text, JSONB metadata, chunk/line/fingerprint fields, timestamp, and pgvector embedding.
- Embedding dimension is currently 768, based on the planned Gemini embedding configuration; confirm against the selected model in Phase 9.2 before indexing.
- Verification: settings defaults load successfully; existing `tests/test_schemas.py` passes (5 tests). The full suite was attempted but could not complete cleanly in this environment. The checked-in `.venv` points to a missing Python 3.14 installation, and does not contain the newly added `pgvector` package. Do not claim AI-service-to-database connectivity yet.
- The Git status/diff command currently fails with `fatal: this operation must be run in a work tree`, although `git show HEAD:<file>` reads the baseline. Existing edits to `.gitignore`, `frontend/package.json`, and this knowledge file were preserved; the first two were not modified in this work.
- **Update (Late 2026-10-10):**
  - Python Interpreter & Dependencies: Confirmed `Python 3.14.6` is installed and the existing `.venv` works locally but was missing Phase 9 dependencies. Ran `pip install -r requirements.txt` to safely add SQLAlchemy, asyncpg, and pgvector without deleting the environment.
  - Configuration: Safely appended `DATABASE_URL` to `ai-service/.env` by referencing root `.env` secrets without logging credentials. Fixed a regression where `pydantic-settings` rejected extra fields from the root `.env` by adding `"extra": "ignore"` to `model_config` in `config.py`.
  - Database Initialization & Verification: Created a dedicated standalone script `verify_db.py` to establish the DB connection, verify `CREATE EXTENSION IF NOT EXISTS vector`, and explicitly run `Base.metadata.create_all`. 
  - Test Results: `verify_db.py` successfully connected and initialized the schema. Ran the entire test suite `pytest tests/ -v`, and all 140 tests passed without errors.
  - Completed (Phase 9.2): Implemented the `EmbeddingProvider` abstraction with `GeminiEmbeddingProvider`.
  - Next (Phase 9.3): Implement the Chunker & Ingestion Pipeline (`chunker.py`, `service.py`).

---

## 14. Phase 9.2 Implementation Progress — EmbeddingProvider Abstraction (2026-10-10)

### 14.1 Embedding Model Decision
- **Model Chosen**: `gemini-embedding-001` (current standard in `google-genai` SDK; note that legacy `text-embedding-004` reached EOL in Jan 2026).
- **Dimensionality**: Configured to `output_dimensionality=768` (using Matryoshka representation learning supported by Gemini embeddings) to precisely match our pgvector schema `Vector(768)` defined in `project_knowledge.py`.
- **SDK**: Standard `google.genai.Client` with `client.models.embed_content`.

### 14.2 Architecture & Files Created / Modified
- **`ai-service/app/providers/base.py`**:
  - Defined `@dataclass class EmbeddingResponse` containing `embeddings: list[list[float]]`, `model: str`, `provider: str`, `dimension: int`, and optional `usage_metadata: dict[str, int] = field(default_factory=dict)`.
  - Defined `class EmbeddingProvider(ABC)` with `@abstractmethod def embed(self, texts: list[str]) -> EmbeddingResponse:`.
- **`ai-service/app/providers/embedding.py`**:
  - Implemented `GeminiEmbeddingProvider(EmbeddingProvider)`.
  - Batching: Gemini supports up to 100 content items per call (`MAX_BATCH_SIZE = 100`). Input validation rejects empty lists, strings, and batches > 100.
  - Normalization: Parses raw SDK embeddings into `EmbeddingResponse` with float vectors, encapsulating SDK-specific types within the provider layer.
  - Error Handling: Translates `ClientError`, `ServerError`, auth errors (401/403), rate limits (429), timeouts, and generic exceptions into `LLMProviderError` codes (`LLM_AUTH_ERROR`, `LLM_RATE_LIMIT`, `LLM_CLIENT_ERROR`, `LLM_SERVER_ERROR`, `LLM_TIMEOUT`, `EMBEDDING_VALIDATION_ERROR`).
  - Redaction: Sanitizes API keys from exception messages.
- **`ai-service/app/config.py`**:
  - Added `EMBEDDING_MODEL: str = "gemini-embedding-001"` and `EMBEDDING_DIMENSION: int = 768` to `Settings`.
- **`ai-service/.env.example`**:
  - Documented optional overrides `EMBEDDING_MODEL=gemini-embedding-001` and `EMBEDDING_DIMENSION=768`.

### 14.3 Test Verification
- Created `ai-service/tests/test_embedding_provider.py` with 26 comprehensive test cases:
  - Base classes and dataclass contracts.
  - API key validation and whitespace checks.
  - Input validation (empty lists, oversized batches, empty strings, non-string entries).
  - Single and multi-text embedding outputs and dimensionality configurations.
  - Custom model names and normalizations.
  - Edge cases (empty response, missing values).
  - Error translation (auth 401/403, rate limit 429, 5xx server errors, timeouts, generic errors).
  - Secret sanitization / redaction.
  - Max batch boundary check (100 items).
  - Live smoke test (skipped when `GEMINI_API_KEY` is absent).
- **Results**: 25 passed, 1 skipped.
- **Full Regression**: All 165 unit/integration tests passed across the entire `ai-service` test suite (1 skipped live test, 0 failures, 0 regressions).

---

## 15. Phase 9 (9.3–9.7) Implementation Progress — Knowledge Ingestion, Storage, Retrieval, Agent Integration & Incremental Sync (2026-10-27)

### 15.1 Milestone Architecture & Components Implemented

1. **Phase 9.3: Hybrid Chunker (`app/knowledge/chunker.py`)**
   - **Strategy**: Hybrid syntax-aware and line-based windowing chunker (`HybridChunker`).
   - **Syntax Boundaries**: Identifies function/class declarations, markdown headers, and block delimiters (`class `, `def `, `async def `, `function `, `interface `, `export `, `type `, `#`, `##`, etc.).
   - **Parameters**: 60 lines max chunk size, 10 lines overlap (~15%), 2000 character soft cap with emergency breaking.
   - **Deterministic Fingerprinting**: Computes SHA-256 checksums (`content_hash`) per chunk based on normalized relative file path and content.
   - **Language Detection & Exclusions**: Automatically infers language from file extension; respects `ProjectService` safe path traversal and exclusion rules.

2. **Phase 9.4: Vector Storage & DB Ops (`app/knowledge/storage.py`)**
   - **Schema & Indexes**: Interacts with `project_knowledge` pgvector table (`Vector(768)`).
   - **Upsert Pipeline**: `upsert_chunks(session, chunks, embeddings)` implements PostgreSQL `ON CONFLICT (file_path, chunk_index) DO UPDATE` to ensure atomic chunk persistence without duplicate rows.
   - **Stale Chunk Pruning**: `prune_stale_chunks(session, file_path, active_chunk_count)` cleanly deletes trailing chunks if a modified file becomes shorter.
   - **Fingerprint Indexing**: `get_existing_fingerprints(session, project_root)` efficiently loads map of `{file_path: {chunk_index: content_hash}}` for instant differential change detection.
   - **Unique Constraint Verification**: `ensure_unique_constraint(session)` idempotently verifies/creates `uq_project_knowledge_path_index` on `(file_path, chunk_index)`.

3. **Phase 9.5: Semantic Retrieval Engine (`app/knowledge/retrieval.py`)**
   - **Vector Similarity**: Generates query embeddings with `EmbeddingProvider` and issues pgvector cosine distance queries (`ProjectKnowledge.embedding.cosine_distance(query_vector)`).
   - **Similarity Scoring**: Converts cosine distance into normalized cosine similarity: `score = 1.0 - (distance / 2.0)`.
   - **Filtering & Guardrails**: Minimum similarity threshold `DEFAULT_SIMILARITY_THRESHOLD = 0.65`; top-k bounded between `[1, MAX_TOP_K = 20]`. Returns structured `RetrievalResult` objects.
   - **Safe Fallback**: Gracefully returns empty list if no chunks meet threshold or if no documents are indexed.

4. **Phase 9.6: Agent Tool Integration & Admin API (`app/tools/semantic_search_tool.py`, `app/routers/knowledge.py`)**
   - **Agent Tool**: Registered `SemanticSearchTool` under `READ_ONLY` permission in `ToolRegistry` (`execute(params)` accepts `query` and optional `top_k`).
   - **Prompt Guardrails**: Chunk content excerpt truncated to `EXCERPT_CHARS = 600` characters to prevent prompt context bloat.
   - **Async-Sync Bridge**: Tool safely bridges synchronous `execute()` contract with async database queries via dedicated event loop execution (`_run_search`).
   - **Graceful Degradation**: If `DATABASE_URL` or `GEMINI_API_KEY` are unset, `create_default_tool_registry()` gracefully omits `semantic_search` without breaking existing agent tools (`list_files`, `read_file`, `search_code`, `inspect_file`).
   - **Admin API**: `POST /api/knowledge/index` triggers on-demand incremental indexing of `PROJECT_ROOT`, validating configuration (returning HTTP 503 if unconfigured) and returning `IndexResponse`.

5. **Phase 9.7: Incremental Sync Pipeline (`app/knowledge/indexer.py`)**
   - **Change Detection**: Compares disk files against database chunk fingerprints (`get_existing_fingerprints`).
   - **Classification**:
     - *New files*: Chunked, embedded, and inserted.
     - *Unchanged files*: Completely skipped without LLM/embedding API calls.
     - *Modified files*: Re-chunked and re-embedded, upserted, and any trailing stale chunks pruned.
     - *Deleted / Ineligible files*: Deleted from `project_knowledge`.
   - **Robust Error Isolation**: File-level try/except ensures an unreadable or malformed file does not halt the entire indexing run; failures are aggregated in `IndexSummary.errors`.

### 15.2 Test & Build Verification

- **AI Service Pytest Suite**:
  - `test_knowledge_chunker.py`: 40 tests covering chunk windowing, overlap, boundary preservation, fingerprint stability, language detection, and size limits.
  - `test_knowledge_storage.py`: 17 tests covering chunk upserting, constraint handling, stale chunk pruning, and fingerprint lookups.
  - `test_knowledge_retrieval.py`: 12 tests covering semantic search queries, score conversion, threshold filtering, and top-k limits.
  - `test_knowledge_tool.py`: 18 tests covering `SemanticSearchTool` parameters, output formatting, schema compliance, error translation, and registry integration.
  - `test_knowledge_indexer.py`: 10 tests covering incremental indexing workflow, diffing, change detection, and deletion pruning.
  - `test_api.py`: 14 tests including root, health, chat, and `POST /api/knowledge/index` endpoint error states and execution.
  - **Full Pytest Suite**: **267 passed, 2 skipped, 0 failures**.
- **Backend Build**: `npm run build` (`tsc`) compiled cleanly with **0 errors**.
- **Frontend Build**: `npm run build` (`next build`) compiled cleanly with **0 errors**.

---

## 16. Phase 10 Implementation — Long-Term Memory System (2026-10-27)

### 16.1 Architecture & Schema
- **SQLAlchemy Model (`app/models/memory.py`)**:
  - `LongTermMemory` persists engineering lessons, bug fixes, architecture decisions, user preferences, and failed approaches across sessions.
  - Shared Base table with `id`, `category` (one of `bug_fix`, `failed_approach`, `architecture_decision`, `user_preference`, `engineering_lesson`), `scope` (`global` vs `project`), `project_root`, `content`, `summary`, `source`, `verification_status` (`proposed`, `unverified`, `verified`), `confidence`, `file_refs` (JSONB), `created_at`, `updated_at`.
  - **Verification policy**: `proposed` is never auto-promoted to `verified` without evidence (test pass or human review).
- **Service Layer (`app/memory/service.py`)**:
  - `MemoryService`: Provides CRUD operations, duplicate detection (`DuplicateMemoryWarning` when identical content already exists), case-insensitive keyword search, and project-scoped isolation.
  - Scoped deletion ensures project memories can only be deleted when the requesting context supplies the matching `project_root`.
- **REST Endpoints (`app/routers/memory.py`)**:
  - Mounted at `/api/memory/` in `app/main.py`.
  - `POST /api/memory/`: Create memory entry (returns 201 Created or 503 if DATABASE_URL unconfigured).
  - `GET /api/memory/`: Search/list memories with filtering by category, scope, project_root, status, and query.
  - `GET /api/memory/{id}`: Retrieve single memory entry.
  - `PATCH /api/memory/{id}`: Partially update content, summary, source, or verification status.
  - `DELETE /api/memory/{id}`: Delete memory entry (project-scoped guard).

### 16.2 Test Verification
- `test_memory_service.py`: 7 tests covering CRUD, duplicate warnings, scoped isolation, and verification status policies.
- `test_memory_api.py`: 5 tests covering 503 when no DB, input validation errors, create/get, 404 handling, and scoped delete.

---

## 17. Phase 11 Implementation — Controlled Coding Agent (2026-10-27)

### 17.1 Architecture & Safety Guarantees
- **Unified Diff Engine (`app/coding_agent/diff_engine.py`)**:
  - Standard unified diff generation (`difflib.unified_diff`) for file creation, modification, and deletion.
  - `compute_proposal_hash`: Deterministic SHA-256 fingerprint computed across sorted canonical change structures and normalized project root.
- **Git Safety & Boundary Protection (`app/coding_agent/git_safety.py`)**:
  - `validate_safe_path`: Enforces strict confinement within `project_root`, resolves symlinks, blocks path traversal (`../`), and protects sensitive assets (`.git`, `.env`, `.venv`, `node_modules`).
  - `inspect_git_status`: Safe, read-only git queries (`git status --porcelain`, `git rev-parse`) detecting uncommitted, modified, and staged changes.
  - **Safety Invariant**: Destructive git commands (`commit`, `push`, `reset`, `clean`, `checkout`) are strictly forbidden.
- **Proposal Lifecycle Manager (`app/coding_agent/proposal.py`)**:
  - `ProposalManager`: Coordinates lifecycle states `proposed` → `approved` → `applied` / `rejected`.
  - **Zero Filesystem Modification Prior to Approval**: Changes on disk remain untouched until explicit approval with verified `content_hash`.
  - **Atomic Application with Rollback Snapshot**: Captures pre-change content snapshots of all target files; if any write fails mid-apply, all modified or created files are instantly rolled back to their original state.
- **Allowlisted Subprocess Validator (`app/coding_agent/validator.py`)**:
  - Strict executable allowlist (`pytest`, `python -m pytest`, `npm test`, `git status`, `ruff`, etc.).
  - Argument-list execution (`asyncio.create_subprocess_exec`) without `shell=True`.
  - Enforces execution timeouts and output buffer truncation (`MAX_OUTPUT_CHARS = 10_000`).
- **REST Endpoints (`app/routers/coding_agent.py`)**:
  - Mounted at `/api/agent/` in `app/main.py`.
  - `POST /api/agent/proposals`: Create a change proposal with unified diffs and SHA-256 hash.
  - `GET /api/agent/proposals`: List proposals filtered by root or status.
  - `GET /api/agent/proposals/{id}`: Get proposal details.
  - `POST /api/agent/proposals/{id}/approve`: Explicit human approval requiring `content_hash` match (returns 409 Conflict if tampered).
  - `POST /api/agent/proposals/{id}/reject`: Decline proposed change.
  - `POST /api/agent/proposals/{id}/apply`: Apply approved proposal to filesystem with optional validation run.
  - `POST /api/agent/validate`: Execute allowlisted verification checks.
  - `GET /api/agent/git-status`: Read-only git status inspection.

### 17.2 Test Verification
- `test_proposal.py`: 12 tests covering diff generation, deterministic hashing, path safety, approval/rejection lifecycle, invariant check, atomic rollback, and allowlist security.
- `test_coding_agent_api.py`: 5 tests covering API proposal creation, approval/apply flows, 409 tamper rejection, validation allowlist enforcement, and git status.

### 17.3 Full Regression Suite Status
- **AI Service Pytest**: **301 passed, 2 skipped, 0 failures** (including stale state safety check and API validation).
- **Backend Build**: `npm run build` compiled cleanly (**0 errors**).
- **Frontend Build**: `npm run build` compiled cleanly (**0 errors**).

---

## 18. Pre-Phase 12/13 Integration Audit & Safety Hardening (2026-10-28)

### 18.1 Key Audit Findings
1. **Phase 9 (Project Knowledge & RAG)**:
   - Backend `POST /api/knowledge/index` and `SemanticSearchTool` are fully implemented in the AI service and registered in `ToolRegistry` when `DATABASE_URL` and `GEMINI_API_KEY` are configured.
   - Missing configuration safely returns HTTP 503 or omits the tool gracefully.
   - Live PostgreSQL (`companion-postgres` with pgvector) is running and confirmed healthy; database schema and tables (`project_knowledge`, `long_term_memory`) initialized.
   - Unit tests use mock databases; live smoke tests require genuine API keys.
2. **Phase 10 (Long-Term Memory)**:
   - Full CRUD, project isolation, duplicate detection, and verification policies are fully implemented in `app/memory/` and exposed via `/api/memory/` REST endpoints.
   - **Integration Gap Identified**: Memory is currently accessible only via REST API; it is NOT yet wired into `AgentOrchestrator`, `ChatService`, or `PromptBuilder` for automatic conversational recall.
3. **Phase 11 (Controlled Coding Agent)**:
   - Diff generation, anti-tampering SHA-256 canonical hashing, approval/rejection lifecycle, and atomic rollback are fully implemented.
   - **Vulnerability Identified & Remediated**: Target files on disk previously lacked stale-state checks before `apply_proposal()`, which could have allowed unreviewed external modifications to be clobbered.
   - **Remediation**: Implemented `ProposalStaleError` and baseline content comparison in `apply_proposal()`, returning HTTP 409 Conflict if target files were modified on disk after proposal generation.
   - **Integration Gap Identified**: Coding agent workflow is accessible only via `/api/agent/` REST endpoints; neither the frontend UI nor the Express backend proxy has wired this into the user-facing chat.
4. **Frontend & Backend (3-Tier) Integration**:
   - The Express backend and Next.js frontend currently only expose and route `/api/chat` and `/ws`.
   - Knowledge indexing, memory management, and code change review/approval are currently backend-only (AI Service REST endpoints).

### 18.2 Verified Regression Baseline
- `ai-service`: **301 passed, 2 skipped, 0 failures** (`.venv\Scripts\python.exe -m pytest`).
- `backend`: `npm run build` (`tsc`) compiled cleanly (**0 errors**).
- `frontend`: `npm run build` (`next build`) compiled cleanly (**0 errors**).

---

## 19. Integration Bridge Implementation — Browser UI & 3-Tier Integration (2026-10-28)

### 19.1 Architecture & Components Implemented
1. **Memory-to-Conversational Reasoning (`app/tools/memory_tool.py`, `app/routers/chat.py`)**:
   - `SearchMemoryTool` (`PermissionLevel.READ_ONLY`): Registered in `create_default_tool_registry()` when `DATABASE_URL` is configured.
   - Allows the agent to query long-term memory for past bug fixes, architectural decisions, and engineering lessons.
   - **Strict Project Isolation**: Enforces that project-scoped memories are only returned if their `project_root` matches the active project. Global lessons are accessible across all projects. Memories belonging to other projects are filtered out.
   - **Context Prompt Injection**: In `_get_project_context()`, up to 3 verified lessons and architectural decisions are injected directly into the system prompt context as `--- Long-Term Memory (Verified Engineering Lessons) ---`.
   - Never auto-promotes unverified/proposed memories without explicit confirmation.
2. **Express Gateway Proxy Routes (`backend/src/routes/`)**:
   - `backend/src/routes/proxyHelper.ts`: Unified forwarder preserving HTTP method, query strings, request bodies, and status codes (200, 201, 400, 404, 409, 503).
   - Enforces timeout (`config.aiServiceTimeoutMs`) with sanitized 504 and 502 error envelopes.
   - Mounted routes:
     - `/api/knowledge/index` (`POST`)
     - `/api/memory/` (`GET`, `POST`) and `/api/memory/:id` (`GET`, `PATCH`, `DELETE`)
     - `/api/agent/proposals` (`GET`, `POST`), `/api/agent/proposals/:id` (`GET`), `/api/agent/proposals/:id/approve` (`POST`), `/api/agent/proposals/:id/reject` (`POST`), `/api/agent/proposals/:id/apply` (`POST`), `/api/agent/validate` (`POST`), and `/api/agent/git-status` (`GET`).
3. **Next.js Browser UI Integration (`frontend/src/app/`)**:
   - Extended `page.tsx` with top-level sub-navigation tabs:
     - **💬 Companion Chat**: Multi-turn conversational interface with WebSocket channel and debug metadata.
     - **📚 Project Knowledge (`components/KnowledgePanel.tsx`)**: Trigger on-demand incremental indexing, real-time status summary cards (indexed files, chunks stored, skipped files, pruned files, failures), and semantic retrieval guide.
     - **🧠 Long-Term Memory (`components/MemoryPanel.tsx`)**: Filter memories by keyword, category, and verification state. Create new memories with scope/category selection. Delete memories with project isolation verification. Explicit badge system for `[VERIFIED]`, `[UNVERIFIED]`, and `[PROPOSED]`.
     - **⚡ Coding Agent (`components/CodingAgentPanel.tsx`)**: Request atomic code modifications. Inspect Git working-tree status. Review unified diffs with line-level addition/deletion syntax highlighting. Enforce explicit human Approve (verifying content hash) and Reject actions. Safe Apply action with post-apply subprocess validation cards. Stale-state rejection alert banners preventing concurrent data loss.

### 19.2 Test Verification
- **AI Service Pytest**: **309 passed, 2 skipped, 0 failures** (`tests/test_memory_tool.py`: 8 tests covering tool schemas, isolation, formatting, db error fallback, and prompt injection).
- **Backend Node Tests**: **7 passed, 0 failures** (`backend/test/gateway.test.ts` via `npm test` covering routing, proxying, query forwarding, 409 tamper propagation, 502 connection errors, and 504 timeouts).
- **Backend Build**: `npm run build` (`tsc`) compiled cleanly (**0 errors**).
- **Frontend Build**: `npm run build` (`next build`) compiled cleanly (**0 errors**).

---

## 20. Phase 12 Implementation — Git Integration (2026-10-28)

### 20.1 Architecture & Safety Guarantees
- **Git Service Layer (`ai-service/app/git/service.py`)**:
  - Encapsulates subprocess Git queries and mutations without shell execution (`asyncio.create_subprocess_exec`).
  - Strict path traversal validation confining all operations to `project_root`.
  - **Read-Only Inspection**:
    - `git_log`: Formatted commit history with commit hash, author, date, and message.
    - `git_diff`: Diffs for working tree (`working`), staged/index (`staged`), or between arbitrary refs (`refs`).
    - `git_blame`: Line-by-line attribution annotations.
    - `git_branches`: Lists local and remote branches and identifies current active branch.
    - `git_show`: Detailed inspect view for a specific commit hash or ref.
  - **Controlled Mutations (Requiring Explicit Human Approval)**:
    - `git_stage`: Stages specific relative file paths; rejects attempts to stage forbidden paths (`.git`, `.env`).
    - `git_commit`: Creates commit with verified message; enforces anti-tampering verification via `compute_stage_approval_token()` (SHA-256 of staged files + commit message).
    - `git_create_branch`: Creates a new branch and optionally checks it out.
  - **Strict Safety Invariants**:
    - Push operations (`git push`) are NEVER supported or permitted (local-only repository safety).
    - Destructive operations (`git reset --hard`, `git clean -fd`, `git rebase`, `git merge`) are explicitly rejected by safety guards.

- **Agent Tool Integration (`ai-service/app/tools/git_tool.py`)**:
  - `GitInfoTool` registered as `READ_ONLY` in `ToolRegistry` (`create_default_tool_registry()`).
  - Allows `AgentOrchestrator` to inspect git log, diffs, blame, branch structure, and commit details during multi-step reasoning.
  - Truncates verbose outputs to preserve LLM token context budget.

- **FastAPI Router (`ai-service/app/routers/git.py`)**:
  - Mounted at `/api/git` in `app/main.py`.
  - `GET /api/git/log`: Commit history query.
  - `POST /api/git/diff`: Diff viewer.
  - `POST /api/git/blame`: Line attribution viewer.
  - `GET /api/git/branches`: Branch list.
  - `POST /api/git/show`: Commit detail view.
  - `POST /api/git/stage`: Controlled staging.
  - `POST /api/git/commit`: Controlled commit (requires matching `approval_token`, returns 409 Conflict if mismatched).
  - `POST /api/git/branch`: Controlled branch creation.
  - `GET /api/git/stage-token`: Preview approval token before confirming commit.

- **Express Gateway Proxy (`backend/src/routes/git.ts`, `backend/src/app.ts`)**:
  - Proxies all `/api/git/*` requests to the Python AI service via `forwardToAiService`.

- **Next.js UI (`frontend/src/app/components/GitPanel.tsx`, `frontend/src/app/page.tsx`)**:
  - Dedicated "🌿 Git Workspace (Phase 12)" tab in top navigation.
  - Sub-views for Commit History, Working/Staged Diff Viewer, Stage & Commit workflow with token generation and approval confirmation, and Line Blame inspection.

### 20.2 Test & Build Verification
- `test_git_service.py`: 27 passed (read-only queries, mutations, approval tokens, forbidden command guards).
- `test_git_tool.py`: 9 passed (metadata, permissions, command dispatch, error translation).
- `test_git_api.py`: 10 passed (HTTP endpoints, 409 conflict, validation).
- Full AI Service test suite: **355 passed, 2 skipped, 0 failures**.
- Backend Gateway test suite: **9 passed, 0 failures** (`npm test`).
- Backend Build: `npm run build` compiled cleanly (**0 errors**).
- Frontend Build: `npm run build` compiled cleanly (**0 errors**).

---

## 21. Phase 13 Implementation — Windows Desktop Companion (2026-10-28)

### 21.1 Architecture & Components Implemented
- **Desktop Application Scaffold (`desktop/`)**:
  - Electron 33 wrapper transforming the 3-tier web application into a native Windows desktop experience.
  - `desktop/package.json`: Configured with Electron Forge and scripts (`start`, `test`, `package`, `make`).
  - Added root monorepo scripts: `dev:desktop`, `test:desktop`, `install:desktop`.

- **Secure IPC Preload (`desktop/preload.js`)**:
  - Uses `contextBridge.exposeInMainWorld("companionDesktop", ...)` to securely bridge desktop capabilities.
  - Provides: native notifications (`notify`), service health checks (`checkServices`), window minimization (`minimizeToTray`), external link opening (`openExternal`), and deep link event listeners (`onDeepLink`).
  - Node integration disabled and context isolation enabled for security.

- **Process & Service Health Manager (`desktop/process-manager.js`)**:
  - Pings FastAPI AI service (`/api/health/`), Express backend (`/api/health`), and Next.js frontend concurrently.
  - Tracks child processes and guarantees clean SIGTERM shutdown on application exit.

- **Windows System Tray Integration (`desktop/tray.js`)**:
  - Persistent Windows notification area tray icon.
  - Context menu showing live service status (🟢 Backend Online, 🟢 AI Service Online).
  - Single-click and double-click handlers to toggle/restore main window.
  - Intercepts window close events to minimize to system tray rather than killing background sessions.

- **Main Electron Lifecycle (`desktop/main.js`)**:
  - Single-instance lock (`app.requestSingleInstanceLock()`).
  - Deep linking protocol handler (`companion://`).
  - Framed dark window styling (`#09090b`, min 1024x700).
  - Offline / loading fallback page (`desktop/fallback.html`) with automatic polling and retry when services are booting.

- **Windows Packaging Configuration (`desktop/forge.config.js`)**:
  - Electron Forge configuration targeting Windows Squirrel installer (`@electron-forge/maker-squirrel`) and zip archive distribution.

### 21.2 Test & Build Verification
- Syntax validation: `node --check` passed cleanly on all 5 desktop JS modules (`main.js`, `preload.js`, `process-manager.js`, `tray.js`, `forge.config.js`).
- Unit tests: `test/process-manager.test.js` passed **5/5 tests** (`npm run test:desktop`).
- Full monorepo verification:
  - `ai-service`: **355 passed, 2 skipped, 0 failures**
  - `backend`: **9 passed, 0 failures** (`npm test`); build passes (`tsc`)
  - `frontend`: production build passes (`next build` with Turbopack)
  - `desktop`: **5 passed, 0 failures** (`npm test`)

---

## 22. Roadmap Progress Summary (Phases 1–13)

| Phase | Milestone | Status |
|-------|-----------|--------|
| **1–8** | Skeleton, IPC, FastAPI Core, Gemini LLM, Persona, ProjectService, Tools, Orchestrator | ✅ Complete & Verified |
| **9** | Project Knowledge & RAG Foundation (PostgreSQL + pgvector) | ✅ Complete & Verified |
| **10** | Long-Term Memory System (CRUD, Isolation, Verification Policies) | ✅ Complete & Verified |
| **11** | Controlled Coding Agent (Unified Diffs, Content Hash Approval, Atomic Rollback) | ✅ Complete & Verified |
| **Integration Bridge** | Memory-to-Prompt Injection, Express Gateway Proxy, Full Next.js Web UI | ✅ Complete & Verified |
| **12** | Git Integration (First-Class Agent Tool, Safe Stage/Commit, Blame, UI) | ✅ Complete & Verified |
| **13** | Windows Desktop Companion (Electron Shell, System Tray, Process Manager, Notifications) | ✅ Complete & Verified |
| **14** | Screen Context & Permissions (Explicit Consent, Ephemeral Frame, IPC Security, UI Toggle) | ✅ Complete & Verified |
| **15** | Docker / Infrastructure (Multi-Stage Containers, Compose Profiles, PostgreSQL+pgvector) | ✅ Complete & Verified |
| **16–17** | Planned Future Roadmap | 🔲 Planned |

---

## 23. Focused Deep Verification of Phase 12 & Phase 13 (2026-10-28)

### 23.1 Verification Commands Run & Results

1. **AI Service Test Suite**:
   - `.\.venv\Scripts\python.exe -m pytest tests/test_git_*.py -v` (55 tests across `test_git_service.py`, `test_git_tool.py`, `test_git_api.py`, `test_git_real_integration.py`): **55 passed, 0 failures**.
   - `.\.venv\Scripts\python.exe -m pytest -q` (Full AI service suite): **364 passed, 2 skipped, 0 failures**.
2. **Backend Gateway Suite & Build**:
   - `npm test` in `backend/`: **9 passed, 0 failures** (`gateway.test.ts`).
   - `npm run build` in `backend/`: **Compiled with 0 errors** (`tsc`).
3. **Frontend Production Build**:
   - `npm run build` in `frontend/`: **Compiled with 0 errors** (`next build` via Turbopack).
4. **Desktop Tests & Windows Packaging**:
   - `npm test` in `desktop/`: **9 passed, 0 failures** (`process-manager.test.js`, `electron-launch.test.js`).
   - `npm run package` in `desktop/`: Exited with code 0. Generated unpacked Windows binary:
     - Path: `desktop/out/AI Software Engineering Companion-win32-x64/ai-companion.exe` (188,784,640 bytes).
   - `npm run make` in `desktop/`: Exited with code 0. Generated installers:
     - Squirrel Setup: `desktop/out/make/squirrel.windows/x64/AI Software Engineering Companion-0.1.0 Setup.exe` (112,480,256 bytes) and `ai_companion-0.1.0-full.nupkg` (111,693,999 bytes).
     - Standalone Zip: `desktop/out/make/zip/win32/x64/AI Software Engineering Companion-win32-x64-0.1.0.zip` (115,030,827 bytes).

### 23.2 Confirmed Working Behavior vs Unverified Behavior

- **Confirmed Working (Verified via automated execution against real Git & live OS processes)**:
  - Read-only Git queries (`log`, `diff`, `blame`, `branches`, `show`) return authentic commit logs, unified diffs, and line attribution on temporary test repositories.
  - Project-root confinement safely blocks path traversals (`../../`) in `git_stage` and `git_blame`.
  - Sensitive files (`.env`, `.git/HEAD`) are filtered and blocked from being staged.
  - Commit approval token computation is deterministic (`compute_stage_approval_token`) and strictly verified; token mismatches or post-approval message changes return HTTP 409 Conflict / `GitApprovalError`.
  - Destructive Git operations (`push`, `reset`, `clean`, `rebase`, `merge`) are strictly rejected with `GitServiceError`.
  - FastAPI schemas, Express gateway proxies, and React `GitPanel` components agree on endpoints and data contracts.
  - Electron security settings: `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, safe `setWindowOpenHandler` (`shell.openExternal`).
  - Electron process lifecycle: spawned process initializes without runtime crash and cleanly handles termination signals (`desktop/test/electron-launch.test.js`).
  - Packaging pipeline successfully generates valid Windows x64 executables, zip archives, and Squirrel `Setup.exe`.

- **Unverified / Environmental Limitations**:
  - Code signing certificate (Authenticode) is not configured in `forge.config.js`; installing via `Setup.exe` on another Windows machine will display the standard Windows SmartScreen "Unknown Publisher" prompt.
  - Physical graphical window display interaction was verified via headless child process spawn, health polling, and IPC event testing rather than visual human observation.

### 23.3 Code Changes Made in this Run
- Added `ai-service/tests/test_git_real_integration.py` (9 live integration tests against genuine git repositories).
- Added `desktop/test/electron-launch.test.js` (live Electron binary verification and lifecycle checks).
- Installed `desktop/node_modules` dependencies (`electron`, `@electron-forge/*`).

---

## 24. Phase 14 Implementation — Screen Context & Permissions (2026-10-28)

### 24.1 Architecture & Safety Guarantees
- **Screen Permission Manager (`desktop/screen-permissions.js`)**:
  - Screen capture is strictly disabled by default (`granted = false`).
  - `grantPermission()`: Sets `granted = true`, logs ISO timestamp.
  - `revokePermission()`: Immediately resets `granted = false`, increments `revocationCount`.
  - Absolute invariant: No background or persistent screen recording is permitted; capture is allowed ONLY when explicitly authorized.
- **Screen Capturer (`desktop/screen-capturer.js`)**:
  - Implements dependency injection for `capturerApi` via constructor for reliable non-Electron testability.
  - Before querying sources or capturing, verifies `permissions.isPermissionGranted()`; throws `SCREEN_PERMISSION_DENIED` if false.
  - Throws `DESKTOP_CAPTURER_UNAVAILABLE` when running outside Electron or if the native desktopCapturer API is missing.
  - Throws `NO_SCREEN_SOURCES` if source list is empty.
  - Downscales captured frames to standard 720p JPEG (quality 75) to minimize memory and token consumption.
  - Ephemeral guarantee: Captured images are single on-demand frames, never persisted to long-term memory or file storage.
- **Secure Electron IPC & Preload (`desktop/preload.js`, `desktop/main.js`)**:
  - Exposes `companionDesktop.screenContext` methods via `contextBridge` (`getPermission`, `grantPermission`, `revokePermission`, `getSources`, `captureContext`).
  - Context isolation enabled (`contextIsolation: true`), node integration disabled (`nodeIntegration: false`), sandbox enabled (`sandbox: true`).
- **Backend & AI Service Transport (`backend/src/routes/chat.ts`, `ai-service/app/schemas/chat.py`)**:
  - Express chat route forwards `screen_context` (or `screenContext`) safely to FastAPI.
  - Pydantic schema `ScreenContextPayload` models `image_base64`, `mime_type`, `window_title`, `display_name`, `user_granted_permission`, `captured_at`.
  - `PromptBuilder.assemble_messages()`: Injects screen metadata only if `user_granted_permission` is True, with explicit instruction: *"Note: Screen context is ephemeral for the current turn. Do not persist captured screen data to long-term memory."*
  - `ChatService`: Records `screen_context_attached` and `screen_window_title` in response metadata for auditing.
- **Frontend Chat UI Integration (`frontend/src/app/page.tsx`)**:
  - Visible Screen Context status bar in chat footer.
  - Permission toggle button ("Grant Permission" / "Revoke Permission").
  - Explicit per-message opt-in checkbox ("Attach screen frame to send").
  - On send: Captures a single frame on demand and attaches to the payload, immediately resetting the checkbox to prevent unintentional subsequent captures.

### 24.2 Verification & Test Results
- `desktop/test/screen-context.test.js`: **10 passed, 0 failures** (default disabled, explicit grant, revocation count, capturer denial, mocked capture, constructor injection, unavailable capturer error, source listing, empty sources error, multiple grant/revoke cycles).
- Full Desktop Suite: **20 passed, 0 failures** (`npm run test:desktop`).
- Backend Suite: **10 passed, 0 failures** (`gateway.test.ts` including `POST /api/chat` screen_context forwarding).
- AI Service Suite: `test_prompt.py` (permitted & denied screen injection) + `test_api.py` (chat endpoint with screen context permitted & denied) passed. Full suite: **368 passed, 2 skipped, 0 failures**.
- Frontend Build: Compiled cleanly with **0 errors** (`next build` with Turbopack).

---

## 25. Phase 15 Implementation — Docker & Infrastructure (2026-10-28)

### 25.1 Architecture & Components Implemented
- **Docker Environment Verification**:
  - Docker version 29.8.2, Docker Compose v5.5.1 verified active.
  - Live PostgreSQL 17 + pgvector container `companion-postgres` confirmed running and healthy on `127.0.0.1:5432->5432/tcp` with persistent volume `postgres_data`.
- **Multi-Stage Service Dockerfiles**:
  - `ai-service/Dockerfile`: `python:3.12-slim`, non-root user `appuser`, curl healthcheck on `/api/health/`, uvicorn entrypoint on `0.0.0.0:8000`.
  - `backend/Dockerfile`: Multi-stage `node:22-alpine` builder (`tsc`) + minimal runner (`node dist/server.js`), non-root `node` user, healthcheck on `/api/health`.
  - `frontend/Dockerfile`: Multi-stage `node:22-alpine` for Next.js, non-root `node` user, healthcheck on `/api/health`.
  - Dedicated `.dockerignore` files for root, `ai-service`, `backend`, and `frontend` preventing `.git`, `.venv`, `node_modules`, `.next`, and `.env` leakage into images.
- **Docker Compose Orchestration (`docker-compose.yml`)**:
  - Preserved existing `db` service (`pgvector/pgvector:pg17`) and `postgres_data` volume without data loss or re-initialization.
  - Added `ai-service`, `backend`, and `frontend` services under profile `["full"]` with inter-service networking, environment variables, healthchecks, and dependency ordering (`depends_on`).
  - Preserved hybrid development workflow: `docker compose up -d` or `docker compose up -d db` starts only the database for local development. `docker compose --profile full up -d` starts the complete containerized stack.
- **Monorepo Scripts (`package.json`)**:
  - `npm run docker:db`: Start database service.
  - `npm run docker:full`: Start full containerized stack.
  - `npm run docker:down`: Stop containerized services.
  - `npm run docker:config`: Validate full compose configuration.

### 25.2 Verification Results
- `docker compose config`: Exited with code 0; validates standalone database service.
- `docker compose --profile full config`: Exited with code 0; validates all 4 services, ports, health checks, environment parameters, and network topologies.
- Full regression baseline verified:
  - `ai-service`: **368 passed, 2 skipped, 0 failures**
  - `desktop`: **20 passed, 0 failures**
  - `backend`: **10 passed, 0 failures** (`npm test`), build compiled cleanly (`tsc`)
  - `frontend`: production build compiled cleanly (**0 errors**, `next build`)

---

## 26. Phase 16: Evaluation & Observability

### 26.1 Architectural Implementation
- **Telemetry Ring Buffer (`ai-service/app/services/telemetry.py`)**:
  - Implemented thread-safe in-memory ring buffer using Python `collections.deque` with strict bounds (`max_turns=100`, `max_traces=200`).
  - Uses `threading.Lock()` to prevent race conditions during concurrent chat and tool executions.
  - Automatic secret sanitization: checks parameter names against sensitive substrings (`api_key`, `token`, `password`, `secret`, `authorization`, `auth`, `cookie`) and redacts values to `[REDACTED]`. Truncates long base64 strings (`image_base64`) to `[BASE64_DATA: len=N]`.
  - Distinguishes actual measurements (`total_duration_ms`, `llm_duration_ms`, `tool_duration_ms`) from token approximations: tokens are estimated using character heuristics (`~4 chars/token`) and explicitly tagged with `is_token_count_estimated = True` to prevent misleading metrics.
- **Agent Orchestrator Instrumentation (`ai-service/app/services/agent_orchestrator.py`)**:
  - Instrumented `_execute_tool` to measure real execution duration (`time.perf_counter()`), capture step index, and record tool execution traces in the telemetry manager.
- **Chat Service Instrumentation (`ai-service/app/services/chat_service.py`)**:
  - Instrumented `process_message` to record end-to-end turn duration, prompt length, response length, model identifier, and execution status for both successful and error responses.
- **FastAPI Endpoints (`ai-service/app/routers/observability.py`)**:
  - Mounted at `/api/observability/metrics`: returns service status, uptime, recent averages, token estimates, and tool distribution breakdown.
  - Mounted at `/api/observability/traces`: returns bounded audit log of tool execution traces with optional query filtering (`limit`, `outcome`, `tool_name`).
- **Express API Gateway Proxy (`backend/src/routes/observability.ts` & `backend/src/app.ts`)**:
  - Mounted proxy router under `/api/observability` forwarding `GET /metrics` and `GET /traces` to AI service via `forwardToAiService`.
  - Added unit tests in `backend/test/gateway.test.ts` (12 passing tests).
- **Frontend Observability Workspace Panel (`frontend/src/app/components/ObservabilityPanel.tsx`)**:
  - Added 6th workspace tab: `ObservabilityPanel` displaying:
    - Live health status cards for all 4 services (Backend, AI Service, PostgreSQL DB, WebSocket Gateway) with latency indicators and auto-refresh.
    - Turn summary metrics: total turns, success rate %, total tool calls, average turn latency, average LLM latency.
    - Transparent token estimation cards with clear heuristic disclosures.
    - Tool invocation breakdown bar chart.
    - Interactive audit trace table with success/failure outcome filtering and expandable JSON argument inspection.
- **Evaluation Benchmark Suite (`ai-service/tests/test_evaluation.py`)**:
  - 12 comprehensive, deterministic evaluation tests:
    - `test_eval_tool_selection_read_file`: Validates tool selection JSON parsing for file reading.
    - `test_eval_tool_selection_search_code`: Validates tool selection parsing for code queries.
    - `test_eval_tool_selection_git_info`: Validates tool selection parsing for git inspection.
    - `test_eval_tool_selection_final_answer`: Validates clean termination upon final answer formulation.
    - `test_eval_unregistered_tool_rejection`: Validates safe rejection when model requests non-existent tools.
    - `test_eval_permission_escalation_denied`: Asserts execution denial when tool permission exceeds caller authorization.
    - `test_eval_prompt_injection_safety`: Ensures adversarial instructions inside files cannot escalate permissions.
    - `test_eval_screen_context_trust_boundary`: Confirms unverified desktop permissions block screen capture.
    - `test_eval_argument_redaction`: Verifies secrets are sanitized from traces before storage.
    - `test_eval_token_estimate_transparency`: Verifies tokens are explicitly flagged as estimates.
    - `test_eval_telemetry_aggregation`: Validates metric aggregations across multiple synthetic turns.
    - `test_eval_trace_bounded_history`: Proves ring buffer strictly respects max bounds without memory leakage.

---

## 27. Phase 17: Polish, Documentation & Full-Stack Deployment Verification

### 27.1 Polish & UI Refinements
- Added `Ctrl+Enter` shortcut to chat textarea for rapid message submission (`frontend/src/app/page.tsx`).
- Polished workspace layout, standardized tab navigation, empty states, loading spinners, and error alerts across all 6 panels (`chat`, `knowledge`, `memory`, `agent`, `git`, `observability`).
- Ensured graceful error degradation when upstream services are restarting or offline.

### 27.2 Stack Verification Script (`scripts/verify_stack.py`)
- Created automated full-stack verification script in `scripts/verify_stack.py`:
  - **Tool Registrations**: Validates 4 core tools (`read_file`, `list_files`, `search_code`, `inspect_file`) and 3 optional tools (`git_info`, `semantic_search`, `search_memory`), checking names, descriptions, input schemas, and permission levels.
  - **Database & pgvector Connectivity**: Connects to PostgreSQL using configured `DATABASE_URL`, verifies extension `vector` is active, and verifies tables `project_knowledge` and `long_term_memory` exist.
  - **Docker Compose Infrastructure**: Validates `docker compose config` (base profile) and `docker compose --profile full config` (full profile) syntax and environment interpolation. Probes status of container `companion-postgres`.
  - **Telemetry Subsystem**: Validates `TelemetryService` turn/tool recording, metrics computation, and secret sanitization.
  - **Health Endpoint Probing**: Probes AI service (`:8000/api/health/`), Backend gateway (`:3001/api/health`), and Frontend (`:3000/api/health`).
  - **Exit Codes**: Returns 0 on complete pass, 1 on required failure, 2 on unreachable live endpoints (when `--require-live` passed).
- Added root npm orchestrator script: `npm run verify:stack`.

### 27.3 Documentation Updates
- Updated `README.md`:
  - Complete 17-phase status table with all phases marked `✅ Complete & Verified`.
  - Up-to-date architecture diagram including Electron Desktop, Observability, and Docker infrastructure.
  - Full quick-start setup guide, Docker commands, stack verification instructions, test commands, and troubleshooting guide.
- Updated `docs/architecture.md`:
  - Extended architecture documentation to cover all 17 phases in depth (Phases 7–17 fully detailed).

### 27.4 Final Verification Results
- **Full AI Service Pytest Suite**:
  - `ai-service/.venv/Scripts/python.exe -m pytest -q`
  - **382 passed, 2 skipped, 0 failures** in 19.65s (100% passing).
- **Backend Tests & Compilation**:
  - `npm test` in `backend/`: **12 passed, 0 failures** in 348ms (100% passing).
  - `npm run build` in `backend/`: `tsc` compiled cleanly with **0 errors**.
- **Desktop Companion Test Suite**:
  - `npm test` in `desktop/`: **20 passed, 0 failures** in 3.11s (100% passing).
- **Frontend Production Build**:
  - `npm run build` in `frontend/`: Next.js 16.3.5 Turbopack production build succeeded with **0 errors**.
- **Stack Verification**:
  - `npm run verify:stack`: **9 passed, 0 warnings, 0 failed** (Exit Code 0).
- **Docker Compose Config**:
  - `docker compose config`: Exited with code 0.
  - `docker compose --profile full config`: Exited with code 0.








