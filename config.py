"""
Configuration management for Dementia Chatbot
"""
import os
from pathlib import Path
from cryptography.fernet import Fernet
import streamlit as st
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
AUDIO_DIR = BASE_DIR / "audio"
MEMORY_DIR = BASE_DIR / "memory"

# Load environment variables from .env in project root
load_dotenv(BASE_DIR / ".env")

# Create directories if they don't exist
for directory in [DATA_DIR, MODELS_DIR, AUDIO_DIR, MEMORY_DIR]:
    directory.mkdir(exist_ok=True)

# Database configuration
DATABASE_PATH = DATA_DIR / "memories.db"
FAISS_INDEX_PATH = DATA_DIR / "faiss_index"
CHROMA_DB_PATH = DATA_DIR / "chroma_db"

# Security configuration
SECRET_KEY_FILE = DATA_DIR / "secret.key"

# Default user credentials (for MVP)
DEFAULT_USERNAME = "user"
DEFAULT_PASSWORD = "user"
CAREGIVER_USERNAME = "caregiver"
CAREGIVER_PASSWORD = "caregiver123"

# Language settings
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi", 
    "ta": "Tamil",
    "tel": "Telugu",
    "es": "Spanish",
    "fr": "French",
    "de": "German"
}

DEFAULT_LANGUAGE = "en"

# Model configuration
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
GEMINI_MODEL = "gemini-2.5-flash"
_gemini_raw = os.getenv("GEMINI_API_KEY", "") or ""
GEMINI_API_KEY = _gemini_raw.strip().strip('"').strip("'")

# Audio configuration
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHUNK_SIZE = 1024
MAX_AUDIO_DURATION = 60  # seconds

# Memory configuration
MAX_MEMORY_CHUNKS = 1000
SIMILARITY_THRESHOLD = 0.7
TOP_K_RESULTS = 5

# Feature flags and local-first runtime options
FEATURE_FACE_AUTH = os.getenv("FEATURE_FACE_AUTH", "1") == "1"
FEATURE_ALERTS = os.getenv("FEATURE_ALERTS", "1") == "1"
FEATURE_DECAY_RANK = os.getenv("FEATURE_DECAY_RANK", "1") == "1"
FEATURE_ADAPTIVE_MODE = os.getenv("FEATURE_ADAPTIVE_MODE", "1") == "1"
PRIVATE_MODE = os.getenv("PRIVATE_MODE", "local")

# Retrieval tuning
DECAY_HALF_LIFE_DAYS = float(os.getenv("DECAY_HALF_LIFE_DAYS", "14"))
DECAY_WEIGHT = float(os.getenv("DECAY_WEIGHT", "0.4"))
TRUST_WEIGHT = float(os.getenv("TRUST_WEIGHT", "0.2"))
REINFORCEMENT_WEIGHT = float(os.getenv("REINFORCEMENT_WEIGHT", "0.15"))

def get_or_create_secret_key():
    """Get or create encryption key"""
    if SECRET_KEY_FILE.exists():
        with open(SECRET_KEY_FILE, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(SECRET_KEY_FILE, 'wb') as f:
            f.write(key)
        return key

def get_fernet_cipher():
    """Get Fernet cipher for encryption/decryption"""
    key = get_or_create_secret_key()
    return Fernet(key)

# Initialize encryption
FERNET_CIPHER = get_fernet_cipher()

# Streamlit session state keys
class SessionKeys:
    USER_LOGGED_IN = "user_logged_in"
    USERNAME = "username"
    USER_ROLE = "user_role"  # "user" or "caregiver"
    SELECTED_LANGUAGE = "selected_language"
    MEMORY_APPROVED = "memory_approved"
    AUDIO_RECORDED = "audio_recorded"
    USER_ID = "user_id"
    COGNITIVE_MODE = "cognitive_mode"
