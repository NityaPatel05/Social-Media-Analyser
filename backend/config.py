"""Application configuration loaded from environment variables."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Resolve the project root (parent of the backend folder)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from the project root instead of just the current working directory
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)

# API Keys
_gemini_keys_str = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = [k.strip(' "\'') for k in _gemini_keys_str.split(",") if k.strip(' "\'')]

_exhausted_keys = {}
_key_usages = {}
MAX_CALLS_PER_KEY = 15

def get_gemini_api_key() -> str:
    import time
    import random
    now = time.time()
    valid_keys = [k for k in GEMINI_API_KEYS if (k not in _exhausted_keys or now > _exhausted_keys[k]) and _key_usages.get(k, 0) < MAX_CALLS_PER_KEY]
    if not valid_keys:
        return ""
    return random.choice(valid_keys)

def mark_gemini_key_exhausted(key: str):
    import time
    logger.warning("Gemini key exhausted. Marking for 24h.")
    _exhausted_keys[key] = time.time() + 86400

def increment_gemini_key_usage(key: str):
    _key_usages[key] = _key_usages.get(key, 0) + 1

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
