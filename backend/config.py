# config.py
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import time 

logger = logging.getLogger(__name__)

# Resolve project root (assuming config.py is inside backend/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env ONCE at import time (this is the most reliable way)
load_dotenv(BASE_DIR / ".env", override=True)

# Also try current directory as fallback
load_dotenv(override=True)

# ------------------- Gemini Keys Management -------------------
_exhausted_keys = {}
_key_usages = {}
MAX_CALLS_PER_KEY = 15

def get_gemini_api_key() -> str:
    """Return next available Gemini API key"""
    gemini_keys_str = os.getenv("GEMINI_API_KEY", "").strip()
    
    if not gemini_keys_str:
        logger.error("GEMINI_API_KEY environment variable is empty or not set!")
        return ""

    # Support comma-separated keys
    current_keys = [k.strip(' "\'') for k in gemini_keys_str.split(",") if k.strip(' "\'')]
    
    if not current_keys:
        logger.error("No valid Gemini API keys found after parsing")
        return ""

    now = time.time()
    valid_keys = [
        k for k in current_keys 
        if k not in _exhausted_keys or now > _exhausted_keys[k]
    ]

    if not valid_keys:
        logger.warning("All Gemini keys are marked exhausted. Returning first key anyway.")
        return current_keys[0]   # Force try at least one key

    # Simple round-robin like behavior (you can improve this later)
    return valid_keys[0]


def mark_gemini_key_exhausted(key: str):
    import time
    logger.warning(f"Marking Gemini key as exhausted for 60 seconds: {key[:8]}...")
    _exhausted_keys[key] = time.time() + 60   # 60 seconds instead of 24h for testing


def increment_gemini_key_usage(key: str):
    _key_usages[key] = _key_usages.get(key, 0) + 1
    # Optional: log usage
    # logger.info(f"Key usage: {key[:8]}... -> {_key_usages[key]}")

# Paths (Use absolute paths based on root directory for local runs, override with env in Docker)
DATA_PATH = os.getenv("DATA_PATH", str(BASE_DIR / "data" / "data.jsonl"))
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(BASE_DIR / "data" / "chromadb"))
EMBEDDINGS_CACHE_PATH = os.getenv("EMBEDDINGS_CACHE_PATH", str(BASE_DIR / "data" / "embeddings_cache"))

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# App settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

logger.info("Configuration loaded from environment")
