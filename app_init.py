"""
Shared initialization utilities for Streamlit pages.
Ensures session state and core components are available whether
pages are rendered via the custom router or opened directly
as Streamlit multipage scripts.
"""
import streamlit as st
from pathlib import Path
import sys

# Make sure project root is on sys.path (for direct page execution)
ROOT_DIR = Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config import (
    SessionKeys, DEFAULT_LANGUAGE,
    DEFAULT_USERNAME, DEFAULT_PASSWORD, CAREGIVER_USERNAME, CAREGIVER_PASSWORD
)


@st.cache_resource
def initialize_components():
    """Create and cache core components used across pages."""
    # Import heavy modules lazily to avoid blocking initial page load
    from database import MemoryDatabase
    from memory_system import MemorySystem
    from audio_processor import AudioProcessor, EntityExtractor
    from llm_integration import LLMIntegration

    db = MemoryDatabase()
    from auth_service import AuthService
    auth_service = AuthService(db)
    for uname, pwd, role, full_name in [
        (DEFAULT_USERNAME, DEFAULT_PASSWORD, "user", "Default User"),
        (CAREGIVER_USERNAME, CAREGIVER_PASSWORD, "caregiver", "Default Caregiver"),
    ]:
        if not db.get_user_by_username(uname):
            db.create_user(uname, auth_service.hash_password(pwd), role, full_name)
    memory_system = MemorySystem()
    audio_processor = AudioProcessor()
    entity_extractor = EntityExtractor()
    llm_integration = LLMIntegration(memory_system)

    return {
        "db": db,
        "memory_system": memory_system,
        "audio_processor": audio_processor,
        "entity_extractor": entity_extractor,
        "llm_integration": llm_integration,
    }


def initialize_session_state():
    """Initialize default session state keys if missing."""
    if SessionKeys.USER_LOGGED_IN not in st.session_state:
        st.session_state[SessionKeys.USER_LOGGED_IN] = False

    if SessionKeys.USERNAME not in st.session_state:
        st.session_state[SessionKeys.USERNAME] = ""

    if SessionKeys.USER_ROLE not in st.session_state:
        st.session_state[SessionKeys.USER_ROLE] = "user"

    if SessionKeys.SELECTED_LANGUAGE not in st.session_state:
        st.session_state[SessionKeys.SELECTED_LANGUAGE] = DEFAULT_LANGUAGE


def ensure_app_initialized():
    """Ensure session state and components are ready for any page."""
    initialize_session_state()

    if "components" not in st.session_state:
        components = initialize_components()
        st.session_state["components"] = components


