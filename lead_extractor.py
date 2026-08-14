"""
Lead Extractor for Agency Voice Bridge.
Extracts caller details from conversation transcript and pushes to Sankalp's /leads API.
"""
import json
import os
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
AGENCY_API_URL = os.environ.get("AGENCY_API_URL", "http://127.0.0.1:8000")

SYSTEM_EXTRACTOR_PROMPT = """You are a real estate lead extraction parser.
Given a conversation transcript between an AI receptionist and a caller, extract the lead details in JSON format:
{
  "name": "Caller name (or 'Prospective Buyer/Seller' if unknown)",
  "phone": "Caller phone number (or 'Not Provided')",
  "email": "caller@example.com",
  "message": "Concise summary of their property inquiry, location preference, budget, and timeline"
}
Respond with ONLY valid JSON."""


def extract_and_push_lead(agency_id: str, transcript: list[dict]) -> dict:
    """Parses conversation transcript into structured lead and POSTs to /leads."""
    if not transcript:
        return {"status": "empty_transcript"}

    formatted_chat = "\n".join([f"{t.get('role', 'user')}: {t.get('text', '')}" for t in transcript])

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": SYSTEM_EXTRACTOR_PROMPT},
                {"role": "user", "content": f"Transcript:\n{formatted_chat}"},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        parsed = json.loads(res.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[lead_extractor] Groq parse error: {e}")
        parsed = {
            "name": "Inbound Caller",
            "phone": "Unknown",
            "email": "inbound@voicelead.com",
            "message": f"Raw call summary: {formatted_chat[:300]}",
        }

    lead_payload = {
        "agency_id": agency_id,
        "name": parsed.get("name") or "Inbound Caller",
        "email": parsed.get("email") or "caller@lead.com",
        "phone": parsed.get("phone") or "Not provided",
        "message": parsed.get("message") or "Voice call completed.",
        "source": "voice_bot",
    }

    try:
        resp = requests.post(f"{AGENCY_API_URL}/leads", json=lead_payload, timeout=5)
        return resp.json() if resp.status_code == 200 else {"status": "failed", "code": resp.status_code}
    except Exception as e:
        print(f"[lead_extractor] Failed to POST /leads: {e}")
        return {"status": "error", "error": str(e)}
