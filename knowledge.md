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
| **Phase 7** | `3c7bfa6` | **Read-Only Tool System**: `ToolRegistry`, `PermissionLevel`, और 4 रीड-ओनली टूल्स (`list_files`, `read_file`, `search_code`, `inspect_file`) का सुरक्षित एग्जीक्यूशन फ्रेमवर्क। |
| **Phase 8** | Pending commit | **Agent Orchestration**: `AgentOrchestrator` जो LLM और ToolRegistry के बीच बाउंडेड लूप (अधिकतम 3 स्टेप्स), सुरक्षित JSON डिसीजन पार्सिंग, और ChatService इंटीग्रेशन प्रदान करता है। |

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
    │   │   ├── base.py           <-- LLMProvider एब्सट्रैक्ट क्लास
    │   │   └── gemini.py         <-- Google Gemini SDK प्रोवाइडर
    │   ├── services/
    │   │   ├── chat_service.py   <-- कोर चैट सर्विस
    │   │   ├── conversation.py   <-- इन-मेमोरी सेशन व हिस्ट्री मैनेजर
    │   │   ├── prompt.py         <-- प्रॉम्प्ट बिल्डर व कॉन्टेक्स्ट कंपोज़र
    │   │   └── project_service.py<-- सेफ रीड-ओनली फ़ाइल व स्ट्रक्चर स्कैनर
    │   └── routers/chat.py       <-- /api/chat/ एंडपॉइंट
    ├── tests/                    <-- 80 कम्प्लीट यूनिट/इंटीग्रेशन टेस्ट्स
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

## 8. सामान्य समस्याएं और समाधान (Common Gotchas & Troubleshooting)

1. **`LLM_SERVER_ERROR` या 500 एरर आना:**
   - **कारण:** `.env` में `GEMINI_MODEL=gemini-3.8-flash` लिखा होना।
   - **समाधान:** इसे बदलकर `GEMINI_MODEL=gemini-2.0-flash` करें और uvicorn सर्वर को रीस्टार्ट करें।
2. **PowerShell में Python पाथ:**
   - Windows पर सीधे `python` चलाने के बजाय हमेशा वर्चुअल एनवायरनमेंट वाला एग्जीक्यूटबल उपयोग करें: `.\.venv\Scripts\python.exe`.
3. **API Key की सुरक्षा:**
   - अपनी असली API Key को कभी भी Git में कमिट न करें। असली की हमेशा केवल लोकल `.env` में रखें, जो `.gitignore` में सुरक्षित है।
