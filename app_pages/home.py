"""
Home page for Dementia Chatbot
Handles login and main dashboard
"""
import streamlit as st
from config import (
    SessionKeys, DEFAULT_USERNAME, DEFAULT_PASSWORD, 
    CAREGIVER_USERNAME, CAREGIVER_PASSWORD
)
from app_init import ensure_app_initialized


def _short_text(text: str, limit: int = 120) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def render_login_page():
    """Render the login page"""
    st.markdown("""
    <div class="main-header" style="text-align:center;">
        <h1>🧠 Dementia Chatbot</h1>
        <p style="font-size:18px;">Personal Memory Assistant with Multilingual Voice Support</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Login controls (non-form to avoid form submit edge cases)
    st.subheader("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        if authenticate_user(username, password):
            st.session_state[SessionKeys.USER_LOGGED_IN] = True
            st.session_state[SessionKeys.USERNAME] = username
            st.session_state[SessionKeys.USER_ROLE] = "caregiver" if username == CAREGIVER_USERNAME else "user"
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid username or password")
    
    # Features overview
    st.markdown("---")
    st.markdown("### 🌟 Key Features")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **🎤 Voice Input**
        - Record voice notes  
        - Ask questions verbally  
        - Multiple language support
        """)
    
    with col2:
        st.markdown("""
        **🧠 Memory Management**
        - Store personal information  
        - Retrieve relevant memories  
        - AI-powered assistance
        """)
    
    with col3:
        st.markdown("""
        **🔒 Privacy First**
        - All data stored locally  
        - Encrypted memory storage  
        - No cloud dependencies
        """)

    # Application help section (moved to bottom)
    st.markdown("---")
    st.markdown("""
    ## 💡 About the Application
    
    This application helps you recall important information like:
    - 💊 Medication schedules  
    - 📅 Appointments and meetings  
    - 👥 Family and friend details  
    - 📝 Important reminders  
    
    You can interact using **voice or text** in **multiple languages** to make your experience more natural and accessible.
    """)


def render_home_page():
    """Render the main home page after login"""
    components = st.session_state.get('components', {})
    
    if not components:
        st.error("System components not initialized")
        return
    
    memory_system = components['memory_system']
    db = components['db']
    
    # Get user info
    username = st.session_state.get(SessionKeys.USERNAME, "")
    user_role = st.session_state.get(SessionKeys.USER_ROLE, "user")
    language = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, "en")
    
    # Welcome message
    st.markdown(f"""
    ### 👋 Welcome back, {username}!
    
    {get_welcome_message(user_role, language)}
    """)
    
    
    # Recent memories
    st.markdown("---")
    st.markdown("### 📝 Recent Memories")
    
    try:
        recent_memories = db.get_all_memories(language=language)
        
        if recent_memories:
            col_total, col_lang = st.columns(2)
            with col_total:
                st.metric("Total memories", len(recent_memories))
            with col_lang:
                st.metric("Current language", language.upper())

            # Show last 5 memories as compact cards
            for idx, memory in enumerate(recent_memories[:5], start=1):
                with st.container():
                    st.markdown(f"**{idx}. {_short_text(memory['text'], 110)}**")
                    st.caption(f"Added: {memory['created_at']} • Source: {memory['source']}")
                    if len((memory.get("text") or "")) > 110:
                        with st.expander("View full memory"):
                            st.write(memory["text"])
                    if memory.get("tags"):
                        st.caption("Tags: " + ", ".join(memory["tags"][:4]))
                    st.markdown("")
        else:
            st.info("No memories yet. Start by adding some memories in the 'Add Memory' section!")
    
    except Exception as e:
        st.error(f"Error loading recent memories: {e}")
    
    # Quick actions
    st.markdown("---")
    st.markdown("### ⚡ Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🧩 Add New Memory", use_container_width=True, key="home_add_memory"):
            st.session_state['nav_page'] = 'add_memory'
            st.rerun()
    
    with col2:
        if st.button("🔍 Ask Assistant", use_container_width=True, key="home_ask_assistant"):
            st.session_state['nav_page'] = 'ask_assistant'
            st.rerun()
    
    with col3:
        if st.button("⚙️ Settings", use_container_width=True, key="home_settings"):
            st.session_state['nav_page'] = 'settings'
            st.rerun()


def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user credentials"""
    return (
        (username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD) or
        (username == CAREGIVER_USERNAME and password == CAREGIVER_PASSWORD)
    )


def get_welcome_message(user_role: str, language: str) -> str:
    """Get localized welcome message"""
    messages = {
        'en': {
            'user': "Your personal memory assistant is ready to help you recall important information.",
            'caregiver': "Caregiver console is ready. You can monitor and manage memories here."
        },
        'hi': {
            'user': "आपका व्यक्तिगत स्मृति सहायक महत्वपूर्ण जानकारी याद करने में आपकी मदद के लिए तैयार है।",
            'caregiver': "अभिभावक कंसोल तैयार है। आप यहाँ यादों की निगरानी और प्रबंधन कर सकते हैं।"
        },
        'ta': {
            'user': "உங்கள் தனிப்பட்ட நினைவக உதவியாளர் முக்கியமான தகவல்களை நினைவுகூர உதவ தயாராக உள்ளார்.",
            'caregiver': "பராமரிப்பாளர் கன்சோல் தயாராக உள்ளது. நீங்கள் இங்கே நினைவுகளை கண்காணித்து நிர்வகிக்கலாம்."
        }
    }
    
    return messages.get(language, messages['en']).get(user_role, messages['en']['user'])
