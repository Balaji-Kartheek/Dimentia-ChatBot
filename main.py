"""
Dementia Chatbot - Main Streamlit Application
Personal Memory Assistant with Multilingual Voice LLM
"""
import streamlit as st
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from config import SessionKeys, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from app_init import ensure_app_initialized
from i18n import t

# Page imports
from app_pages import home, add_memory, ask_assistant, settings, caregiver_console
try:
    from app_pages import support
except Exception:
    support = None

# Configure Streamlit page
st.set_page_config(
    page_title="Dementia Chatbot",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    
    .memory-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 1rem 0;
    }
    
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    
    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }
    
    .info-message {
        background: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #bee5eb;
    }
</style>
""", unsafe_allow_html=True)

# Components are initialized via app_init.ensure_app_initialized() when needed

def initialize_session_state():
    """Initialize session state variables"""
    if SessionKeys.USER_LOGGED_IN not in st.session_state:
        st.session_state[SessionKeys.USER_LOGGED_IN] = False
    
    if SessionKeys.USERNAME not in st.session_state:
        st.session_state[SessionKeys.USERNAME] = ""
    
    if SessionKeys.USER_ROLE not in st.session_state:
        st.session_state[SessionKeys.USER_ROLE] = "user"
    if SessionKeys.USER_ID not in st.session_state:
        st.session_state[SessionKeys.USER_ID] = ""
    
    if SessionKeys.SELECTED_LANGUAGE not in st.session_state:
        st.session_state[SessionKeys.SELECTED_LANGUAGE] = DEFAULT_LANGUAGE
    # Track current navigation page post-login
    if 'nav_page' not in st.session_state:
        st.session_state['nav_page'] = 'home'

def render_sidebar():
    """Render the sidebar navigation"""
    lang = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    with st.sidebar:
        st.markdown(f"## {t(lang, 'main.sidebar_title')}")
        st.markdown("---")

        if st.session_state.get(SessionKeys.USER_LOGGED_IN, False):
            # Navigation menu (top under title)
            pages = {}
            # Build pages based on available modules
            try:
                import importlib
                home = importlib.import_module('app_pages.home')
            except Exception:
                home = None
            try:
                add_memory = importlib.import_module('app_pages.add_memory')
            except Exception:
                add_memory = None
            try:
                ask_assistant = importlib.import_module('app_pages.ask_assistant')
            except Exception:
                ask_assistant = None
            try:
                settings = importlib.import_module('app_pages.settings')
            except Exception:
                settings = None
            try:
                caregiver_console = importlib.import_module('app_pages.caregiver_console')
            except Exception:
                caregiver_console = None
            try:
                support = importlib.import_module('app_pages.support')
            except Exception:
                support = None

            if home:
                pages[t(lang, "nav.home")] = "home"
            if add_memory:
                pages[t(lang, "nav.add_memory")] = "add_memory"
            if ask_assistant:
                pages[t(lang, "nav.ask_assistant")] = "ask_assistant"
            if support:
                pages[t(lang, "nav.support")] = "support"
            if settings:
                pages[t(lang, "nav.settings")] = "settings"
            if st.session_state.get(SessionKeys.USER_ROLE) == "caregiver" and caregiver_console:
                pages[t(lang, "nav.caregiver")] = "caregiver_console"

            # Persist current selection
            current_page_value = st.session_state.get('nav_page', 'home')
            page_keys = list(pages.keys())
            page_values = list(pages.values())
            try:
                default_index = page_values.index(current_page_value)
            except ValueError:
                default_index = 0

            # Reset stale widget state from older sidebar implementations
            if "nav_radio" in st.session_state:
                del st.session_state["nav_radio"]
            if "nav_select" in st.session_state and st.session_state["nav_select"] not in page_keys:
                del st.session_state["nav_select"]

            # Use selectbox for robust state handling across reruns/upgrades
            selected_label = st.selectbox(t(lang, "main.navigate"), page_keys, index=default_index, key="nav_select")
            selected_value = pages[selected_label]
            
            # Only update nav_page if it actually changed
            if selected_value != current_page_value:
                st.session_state['nav_page'] = selected_value
                st.rerun()

            # Language selection moved to Support page

            # Welcome and Role (at the bottom)
            st.markdown("---")
            st.markdown(f"**{t(lang, 'main.welcome_user', name=st.session_state[SessionKeys.USERNAME])}**")
            st.caption(t(lang, "main.role", role=st.session_state[SessionKeys.USER_ROLE].title()))

            # Logout button (keep at very bottom)
            if st.button(t(lang, "main.logout"), type="secondary"):
                for key in [SessionKeys.USER_LOGGED_IN, SessionKeys.USERNAME, SessionKeys.USER_ROLE, SessionKeys.USER_ID]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

            return selected_value
        else:
            st.markdown(t(lang, "main.login_prompt"))
            # Language selection moved to Support page
            return "login"

def main():
    """Main application function"""
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar and get selected page
    selected_page = render_sidebar()
    
    # Initialize components lazily after login only
    if selected_page != "login" and 'components' not in st.session_state:
        ensure_app_initialized()
    
    # Render main header
    if st.session_state.get(SessionKeys.USER_LOGGED_IN, False):
        lg = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
        title_html = t(lg, "main.header_title")
        sub_html = t(lg, "main.header_subtitle")
        st.markdown(f"""
        <div class="main-header">
            <h1>{title_html}</h1>
            <p>{sub_html}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Route to appropriate page
    try:
        if selected_page == "login":
            home.render_login_page()
        elif selected_page == "home":
            home.render_home_page()
        elif selected_page == "add_memory":
            add_memory.render_add_memory_page()
        elif selected_page == "ask_assistant":
            ask_assistant.render_ask_assistant_page()
        elif selected_page == "support":
            support.render_support_page()
        elif selected_page == "settings":
            settings.render_settings_page()
        elif selected_page == "caregiver_console":
            caregiver_console.render_caregiver_console()
        else:
            lg = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
            st.error(t(lg, "common.page_not_found"))
    except Exception as e:
        lg = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
        st.error(t(lg, "common.error_page", err=e))
        st.exception(e)

if __name__ == "__main__":
    main()
