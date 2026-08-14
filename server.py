"""
Agency Voice Bridge — Production API Server.
Endpoints:
- POST /api/v1/voice-agents/provision (Auto-provisions DID & Web Widget for new websites)
- GET  /widget.js (Embeddable voice widget script)
- WS   /ws/call/{agency_id} (Live audio/telephony voice stream)
- POST /api/telephony/inbound (Telephony SIP/PSTN inbound gateway)
- POST /api/webhooks/call-result (Post-call lead extraction & sync)
"""
import os
import json
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import Optional

from config import (
    BRIDGE_PORT,
    AGENCY_API_URL,
    PUBLIC_BASE_URL,
    GROQ_API_KEY,
    DEFAULT_DID_POOL,
    PIPER_API_URL,
    PIPER_ADMIN_EMAIL,
    PIPER_TIMEOUT_SECONDS,
)
from lead_extractor import extract_and_push_lead
from piper_client import PiperClient, PiperError

app = FastAPI(title="Agency Voice Bridge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic Schemas ----------

class ProvisionVoiceAgentRequest(BaseModel):
    agency_id: str
    agency_name: str
    website: Optional[str] = None
    call_bot_prompt: Optional[str] = None
    callback_url: Optional[str] = None
    callback_bearer_token: Optional[str] = None
    first_turn_message: Optional[str] = None
    voice_model: str = "gemini_live"
    voice_name: str = "Aoede"


class ProvisionVoiceAgentResponse(BaseModel):
    status: str
    agency_id: str
    agency_name: str
    company_id: str
    workflow_id: str
    blueprint_id: str
    did_number: str


# ---------- Groq LLM Helper ----------

def _call_groq(messages: list[dict], max_tokens: int = 150) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    res = requests.post(url, json=payload, headers=headers, timeout=10)
    data = res.json()
    return data["choices"][0]["message"]["content"].strip()


# ---------- 1. Health Check ----------

@app.get("/health")
def health():
    return {"status": "ok", "service": "agency-voice-bridge", "port": BRIDGE_PORT}


# ---------- 2. Provisioning Endpoint ----------

@app.post("/api/v1/voice-agents/provision", response_model=ProvisionVoiceAgentResponse)
def provision_voice_agent(req: ProvisionVoiceAgentRequest):
    """
    Called by Sankalp's website generator after brand persona generation.
    Uses existing Piper APIs to create/update workflow and assign a DID.
    """
    if not PIPER_ADMIN_EMAIL:
        raise HTTPException(status_code=503, detail="Piper admin identity is not configured")

    agency_id = req.agency_id.strip()
    agency_name = req.agency_name.strip()
    prompt = (req.call_bot_prompt or "").strip()
    if not agency_id or len(agency_id) > 128:
        raise HTTPException(status_code=400, detail="agency_id must be 1-128 characters")
    if not agency_name or len(agency_name) > 200:
        raise HTTPException(status_code=400, detail="agency_name must be 1-200 characters")
    if len(prompt) < 20 or len(prompt) > 100000:
        raise HTTPException(status_code=400, detail="call_bot_prompt must be 20-100000 characters")
    if req.callback_url and not req.callback_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="callback_url must use https")

    first_turn_message = (req.first_turn_message or "").strip()
    if not first_turn_message:
        first_turn_message = f"Hello! Thank you for calling {agency_name}. How may I help you today?"

    client = PiperClient(PIPER_API_URL, PIPER_ADMIN_EMAIL, PIPER_TIMEOUT_SECONDS)
    try:
        return client.provision(
            agency_id=agency_id,
            agency_name=agency_name,
            prompt=prompt,
            callback_url=req.callback_url,
            callback_bearer_token=req.callback_bearer_token,
            first_turn_message=first_turn_message,
            voice_model=req.voice_model,
            voice_name=req.voice_name,
        )
    except PiperError as exc:
        if exc.status_code == 404 and "no available did" in str(exc).lower():
            raise HTTPException(status_code=409, detail="No free DID available") from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------- 3. Serve Embeddable Widget Script ----------

@app.get("/widget.js")
def serve_widget():
    widget_path = os.path.join(os.path.dirname(__file__), "widget.js")
    if os.path.exists(widget_path):
        with open(widget_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="widget.js not found")


# ---------- 4. Live Voice Streaming WebSocket ----------

@app.websocket("/ws/call/{agency_identifier}")
async def voice_call_ws(websocket: WebSocket, agency_identifier: str):
    await websocket.accept()

    try:
        res = requests.get(f"{AGENCY_API_URL}/voice-agent/{agency_identifier}", timeout=5)
        agency_data = res.json()
    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"Failed to load agency persona: {e}"})
        await websocket.close()
        return

    agency_name = agency_data.get("agency_name", "Real Estate Agency")
    system_prompt = agency_data.get("call_bot_prompt")
    agency_id = agency_data.get("id") or str(agency_identifier)

    messages = [{"role": "system", "content": system_prompt}]
    transcript = []

    greeting = f"Hello! Thank you for calling {agency_name}. My name is Riley, how can I help you today?"
    messages.append({"role": "assistant", "content": greeting})
    transcript.append({"role": "assistant", "text": greeting})

    await websocket.send_json({
        "type": "bot_speech",
        "text": greeting,
        "agency_name": agency_name,
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "user_speech":
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue

                messages.append({"role": "user", "content": user_text})
                transcript.append({"role": "user", "text": user_text})

                bot_reply = _call_groq(messages)

                messages.append({"role": "assistant", "content": bot_reply})
                transcript.append({"role": "assistant", "text": bot_reply})

                await websocket.send_json({
                    "type": "bot_speech",
                    "text": bot_reply,
                })

            elif msg_type == "end_call":
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[voice_ws] Error: {e}")
    finally:
        lead_result = extract_and_push_lead(agency_id, transcript)
        try:
            await websocket.send_json({
                "type": "call_ended",
                "lead_saved": lead_result,
            })
        except Exception:
            pass


# ---------- 5. Inbound Telephony Gateway ----------

@app.post("/api/telephony/inbound")
def telephony_inbound(payload: dict):
    return {
        "status": "connect",
        "stream_url": f"ws://{PUBLIC_BASE_URL.replace('http://', '').replace('https://', '')}/ws/call/1",
    }


# ---------- 6. Test Dashboard UI ----------

@app.get("/", response_class=HTMLResponse)
def serve_test_ui():
    html_file = os.path.join(os.path.dirname(__file__), "test_web_client.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Agency Voice Bridge Running</h1>"
