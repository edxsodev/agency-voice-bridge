"""
Configuration for Agency Voice Bridge.
Loads environment variables and endpoint bindings.
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

# Default Fallback Telephony / DID Settings
DEFAULT_DID_POOL = [
    {"did": "+1-512-476-5348", "provider": "virtual", "assigned": False},
    {"did": "+1-512-910-5294", "provider": "virtual", "assigned": False},
    {"did": "+1-512-948-3366", "provider": "virtual", "assigned": False},
    {"did": "+1-817-696-9208", "provider": "virtual", "assigned": False},
    {"did": "+1-817-523-9113", "provider": "virtual", "assigned": False},
]
