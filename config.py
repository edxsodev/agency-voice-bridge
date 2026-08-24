"""
Configuration for Agency Voice Bridge.
Loads environment variables, active DID inventory pool, and endpoint bindings.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Service Ports & URLs
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", 8100))
BRIDGE_HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
AGENCY_API_URL = os.environ.get("AGENCY_API_URL", "http://127.0.0.1:8000")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", f"http://127.0.0.1:{BRIDGE_PORT}")

# Piper provisioning API (private/internal only)
PIPER_API_URL = os.environ.get("PIPER_API_URL", "http://127.0.0.1:3101")
PIPER_ADMIN_EMAIL = os.environ.get("PIPER_ADMIN_EMAIL", "")
PIPER_TIMEOUT_SECONDS = float(os.environ.get("PIPER_TIMEOUT_SECONDS", "15"))

# AI Engine Keys (read from environment / .env)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")

# Active Real Telephony DID Pool with Campaign & Lead Mapping (iCallMate)
DEFAULT_DID_POOL = [
    {"did": "08037259676", "raw_did": "8037259676", "display_phone": "+91 8037259676", "camp_id": 64, "lead_id": 1079, "provider": "icallmate"},
    {"did": "08037259675", "raw_did": "8037259675", "display_phone": "+91 8037259675", "camp_id": 63, "lead_id": 1078, "provider": "icallmate"},
    {"did": "08037259674", "raw_did": "8037259674", "display_phone": "+91 8037259674", "camp_id": 62, "lead_id": 1077, "provider": "icallmate"},
    {"did": "08037259673", "raw_did": "8037259673", "display_phone": "+91 8037259673", "camp_id": 61, "lead_id": 1076, "provider": "icallmate"},
    {"did": "08037259672", "raw_did": "8037259672", "display_phone": "+91 8037259672", "camp_id": 65, "lead_id": 1083, "provider": "icallmate"},
]
