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

