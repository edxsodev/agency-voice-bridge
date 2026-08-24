# 🎙️ VoiceBot-APIInterface (Agency Voice Bridge)

An autonomous, bi-directional Voice AI bridge connecting **Agency Website Generators** & **Brand Persona Engines** with real-time **Telephony (SIP/PSTN)** and **Browser-based WebRTC/Audio VoiceBots**.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Code Artifacts & File Breakdown](#-code-artifacts--file-breakdown)
- [API Reference](#-api-reference)
  - [1. Provision Voice Agent](#1-provision-voice-agent)
  - [2. Embeddable Web Call Widget](#2-embeddable-web-call-widget)
  - [3. Real-Time Voice WebSocket](#3-real-time-voice-websocket)
  - [4. Telephony Inbound Gateway](#4-telephony-inbound-gateway)
  - [5. Post-Call Lead Extraction](#5-post-call-lead-extraction)
- [Installation & Local Setup](#-installation--local-setup)
- [Testing & Simulation](#-testing--simulation)
- [Environment Variables](#-environment-variables)

---

## 🌟 Overview

When an automated agency builder (like Sankalp's `agency-website-maker`) generates a brand website with a 17-section KYC Brand Persona, this service:
1. **Provisions a Voice Bot**: Automatically creates the workflow blueprint and assigns a real or virtual Phone Number (DID).
2. **Handles Live Voice Calls**: Runs low-latency bi-directional voice conversations over WebSockets (Web Speech / Gemini Live / Groq LLM / Telephony PCM).
3. **Embeds Web Calling**: Provides a 1-line `<script>` widget that injects a floating *"📞 Talk to AI Receptionist"* button onto any website.
4. **Extracts & Dispatches Leads**: On call disconnect, an LLM parses the transcript and automatically saves caller details (`name`, `phone`, `email`, `requirements`) into the agency's CRM database.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────┐
│             AGENCY WEBSITE MAKER (Port 8000)           │
│  • Generates 17-Section Brand Persona & HTML Site      │
│  • Endpoints: GET /voice-agent/{id}, POST /leads       │
└──────────────────────────┬─────────────────────────────┘
                           │
             (1) POST /api/v1/voice-agents/provision
             (Returns DID + Embed Widget)
                           ▼
┌────────────────────────────────────────────────────────┐
│             VOICEBOT API INTERFACE (Port 8100)         │
│  • FastAPI Server + WebSocket Engine                   │
│  • Piper Engine Client (Auto-Company & Blueprint)      │
│  • Virtual DID Pool Fallback                           │
│  • Inbound Telephony SIP/PSTN Gateway                  │
└──────────────┬───────────────────────────┬─────────────┘
               │                           │
  (2) Inbound Call (Web / Phone)           │ (3) Call Hangup
               ▼                           ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│       LIVE VOICE ENGINE      │ │      LEAD EXTRACTOR (LLM)    │
│ • Web Speech / Gemini Live   │ │ • Parses call transcript     │
│ • Groq LLaMA-3.3-70B Realtime│ │ • Extracts Name, Phone, Needs│
│ • Low Latency Turn Stream    │ │ • POST /leads -> Supabase    │
└──────────────────────────────┘ └──────────────────────────────┘
```

---

## 📁 Code Artifacts & File Breakdown

| File | Type | Description & Purpose |
| :--- | :--- | :--- |
| [`server.py`](./server.py) | **Core API** | Main FastAPI application. Exposes provisioning API, auto-rotating DID pool (`/api/v1/dids/rotate`), serves widget script, hosts live voice WebSocket streams, and handles inbound telephony webhooks. |
| [`piper_client.py`](./piper_client.py) | **Engine Client** | Connector to Piper Engine (`http://127.0.0.1:3101` / `workflow.conversely.in`). Handles automated company creation, visual workflow node graph generation (`flowPayload`), and DID pool reservation. |
| [`widget.js`](./widget.js) | **Frontend Widget** | Standalone JavaScript widget. Injects a floating click-to-call modal on generated agency websites, manages browser mic streaming and voice synthesis. |
| [`lead_extractor.py`](./lead_extractor.py) | **AI Agent** | Post-call LLM agent. Extracts structured caller requirements (`name`, `phone`, `budget`, `timeline`) from raw transcripts and pushes them to `POST /leads`. |
| [`agency-provision-router.js`](./agency-provision-router.js) | **Piper Plugin** | Native Express.js drop-in router for `piper-engine` to enable native database blueprint insertion & DID assignment. |
| [`config.py`](./config.py) | **Config** | Centralized configuration loader with active 5-DID real telephony pool (iCallMate). |
| [`test_piper_client.py`](./test_piper_client.py) | **Unit Tests** | Python unit tests verifying workflow ID collision-resistance, brand prompt inclusion, and provisioning idempotency. |
| [`test_web_client.html`](./test_web_client.html) | **Browser UI** | Standalone web test bench to simulate voice calls with Texas agency personas using your browser mic. |
| [`simulate_call.py`](./simulate_call.py) | **CLI Test** | Automated multi-turn conversational simulator that runs scripted calls against the bridge and verifies lead capture. |

---

## 📞 Active Rotating DID Pool (iCallMate)

| DID Number | Raw DID | Display Format | Camp ID | Lead ID | Provider |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`08037259676`** | `8037259676` | `+91 8037259676` | `64` | `1079` | `icallmate` |
| **`08037259675`** | `8037259675` | `+91 8037259675` | `63` | `1078` | `icallmate` |
| **`08037259674`** | `8037259674` | `+91 8037259674` | `62` | `1077` | `icallmate` |
| **`08037259673`** | `8037259673` | `+91 8037259673` | `61` | `1076` | `icallmate` |
| **`08037259672`** | `8037259672` | `+91 8037259672` | `65` | `1083` | `icallmate` |

- **Get Full Pool**: `GET /api/v1/dids/pool`
- **Rotate to Next DID**: `GET /api/v1/dids/rotate`

---

## 🔌 API Reference

### 1. Provision Voice Agent
Automatically registers a brand persona, creates a workflow blueprint, and assigns a DID number.

- **Endpoint**: `POST /api/v1/voice-agents/provision`
- **Headers**: `Content-Type: application/json`

#### Request Payload
```json
{
  "agency_id": "1",
  "agency_name": "Realty Texas",
  "website": "https://realtytexas.com",
  "call_bot_prompt": "You are Riley, the professional AI receptionist for Realty Texas. You help clients with property buying, selling, and leasing in Austin and Round Rock.",
  "callback_url": "https://sankalp-app.com/api/leads",
  "first_turn_message": "Hello! Thank you for calling Realty Texas. How may I help you today?",
  "voice_model": "gemini_live",
  "voice_name": "Aoede"
}
```

#### Response (200 OK)
```json
{
  "status": "active",
  "agency_id": "1",
  "agency_name": "Realty Texas",
  "company_id": "00000000-0000-0000-0000-000000000001",
  "workflow_id": "AGENCY_1",
  "blueprint_id": "00000000-0000-0000-0000-000000000002",
  "did_number": "+1-512-476-5348"
}
```

---

### 2. Embeddable Web Call Widget
To enable click-to-call on any auto-generated website, embed this script before `</body>`:

```html
<script src="http://127.0.0.1:8100/widget.js" data-agency-id="1"></script>
```

- Injects a floating button: *"📞 Talk to AI Receptionist"*.
- Opens a voice dialog and connects to the agency's live persona.
- Dispatches leads to the agency's `/leads` table upon hangup.

---

### 3. Real-Time Voice WebSocket
Streaming bi-directional speech connection for web clients and telephony gateways.

- **Endpoint**: `WS /ws/call/{agency_id}`

#### Client Messages
```json
{ "type": "user_speech", "text": "Hi, I am looking for a 3-bedroom home in Round Rock." }
{ "type": "end_call" }
```

#### Server Messages
```json
{ "type": "bot_speech", "text": "Great! We have several listings in Round Rock. What is your budget?" }
{ "type": "call_ended", "lead_saved": { "status": "success", "id": "641bb563-..." } }
```

---

### 4. Telephony Inbound Gateway
Receives webhook events from PSTN/SIP carriers (Exotel, iCallMate, Twilio) and returns streaming instructions.

- **Endpoint**: `POST /api/telephony/inbound`
- **Payload**: `{ "called_number": "+15124765348", "caller": "+15125550199" }`
- **Response**: `{ "status": "connect", "stream_url": "ws://127.0.0.1:8100/ws/call/1" }`

---

### 5. Post-Call Lead Extraction
Triggered automatically when a call ends. Parses transcript into structured lead JSON and POSTs to CRM:

- **Target Endpoint**: `POST /leads`
- **Payload**:
```json
{
  "agency_id": "bd2e31e6-7363-4617-87a6-3466fd606737",
  "name": "Alex Walker",
  "phone": "512-555-0199",
  "email": "Not Provided",
  "message": "Looking for a 3-bedroom single family home in Round Rock under $450,000. Callback scheduled for tomorrow at 2 PM.",
  "source": "voice_bot"
}
```

---

## 🚀 Installation & Local Setup

### Prerequisites
- Python 3.10+
- Groq API Key (for LLM turn generation & lead parsing)

### 1. Clone & Navigate
```bash
git clone https://github.com/muconnect/VoiceBot-APIInterface.git
cd VoiceBot-APIInterface
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment (`.env`)
```env
BRIDGE_PORT=8100
BRIDGE_HOST=0.0.0.0
AGENCY_API_URL=http://127.0.0.1:8000
PUBLIC_BASE_URL=http://127.0.0.1:8100
GROQ_API_KEY=your_groq_api_key_here
PIPER_API_URL=http://127.0.0.1:3101
PIPER_ADMIN_EMAIL=admin@piper.internal
```

### 5. Start Server
```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8100 --reload
```
API Documentation will be available at `http://127.0.0.1:8100/docs`.

---

## 🧪 Testing & Simulation

### Run Unit Tests
```bash
python -m unittest test_piper_client.py
```

### Run Scripted Call Simulation (CLI)
```bash
python simulate_call.py
```

### Test in Browser
Open `http://127.0.0.1:8100/` in your browser to test interactive voice conversations with any of the 5 seeded Texas real estate agencies using your microphone.

---

## ⚙️ Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `BRIDGE_PORT` | `8100` | Port for the FastAPI bridge server. |
| `BRIDGE_HOST` | `0.0.0.0` | Host binding interface. |
| `AGENCY_API_URL` | `http://127.0.0.1:8000` | URL of the Agency Website Maker backend. |
| `PUBLIC_BASE_URL` | `http://127.0.0.1:8100` | Public base URL used for widget scripts and WebSocket URLs. |
| `GROQ_API_KEY` | `""` | API key for Groq LLaMA-3.3-70B real-time inference. |
| `PIPER_API_URL` | `http://127.0.0.1:3101` | Piper Engine backend URL for native blueprint/DID provisioning. |
| `PIPER_ADMIN_EMAIL` | `admin@piper.internal` | Identity header used for Piper Engine admin operations. |
