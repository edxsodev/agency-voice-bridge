"""
Agency Voice Bridge Server.
Connects browser/telephony callers to Sankalp's Brand Personas and pushes leads to /leads.
"""
import os
import json
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from lead_extractor import extract_and_push_lead

app = FastAPI(title="Agency Voice Bridge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
AGENCY_API_URL = os.environ.get("AGENCY_API_URL", "http://127.0.0.1:8000")


def _call_groq(messages: list[dict]) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 150,
    }
    res = requests.post(url, json=payload, headers=headers, timeout=10)
    data = res.json()
    return data["choices"][0]["message"]["content"].strip()


@app.get("/health")
def health():
    return {"status": "ok", "service": "agency-voice-bridge"}


@app.get("/api/agencies")
def get_agencies():
    try:
        res = requests.get(f"{AGENCY_API_URL}/voice-agent", timeout=5)
        return res.json()
    except Exception as e:
        return {"error": str(e)}


@app.websocket("/ws/call/{agency_number}")
async def voice_call_ws(websocket: WebSocket, agency_number: int):
    await websocket.accept()

    try:
        res = requests.get(f"{AGENCY_API_URL}/voice-agent/{agency_number}", timeout=5)
        agency_data = res.json()
    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"Failed to load agency persona: {e}"})
        await websocket.close()
        return

    agency_name = agency_data.get("agency_name", "Real Estate Agency")
    system_prompt = agency_data.get("call_bot_prompt")
    agency_id = agency_data.get("id") or str(agency_number)

    if not agency_data.get("id"):
        try:
            ag_list = requests.get(f"{AGENCY_API_URL}/voice-agent", timeout=5).json()
            for ag in ag_list:
                if ag.get("agency_number") == agency_number:
                    agency_id = ag.get("id", agency_id)
        except Exception:
            pass

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
        print(f"[bridge_ws] Error: {e}")
    finally:
        lead_result = extract_and_push_lead(agency_id, transcript)
        try:
            await websocket.send_json({
                "type": "call_ended",
                "lead_saved": lead_result,
            })
        except Exception:
            pass


@app.get("/", response_class=HTMLResponse)
def serve_test_ui():
    html_file = os.path.join(os.path.dirname(__file__), "test_web_client.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Agency Voice Bridge Running</h1>"
