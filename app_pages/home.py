"""
Home page for Dementia Chatbot
Handles login and main dashboard
"""
import streamlit as st
from datetime import datetime, timedelta
from config import SessionKeys, FEATURE_FACE_AUTH
from app_init import ensure_app_initialized
from auth_service import AuthService
from face_auth import FaceAuthService


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
    
    ensure_app_initialized()
    db = st.session_state["components"]["db"]
    auth = AuthService(db)
    face_auth = FaceAuthService(db)

    tab_login, tab_register = st.tabs(["🔐 Login", "📝 Register"])
    with tab_login:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        face_file = None
        if FEATURE_FACE_AUTH and face_auth.available:
            face_file = st.file_uploader("Optional face image for 2FA", type=["jpg", "jpeg", "png"], key="login_face")
        if st.button("Login", type="primary", key="login_btn"):
            ok, user, message = auth.authenticate(username, password)
            if not ok:
                st.error(message)
            else:
                if FEATURE_FACE_AUTH and face_auth.available and db.get_face_embedding(user["id"]):
                    if not face_file:
                        st.error("Face authentication required. Upload enrolled face image.")
                        return
                    face_ok, score = face_auth.verify(user["id"], face_file.read())
                    if not face_ok:
                        st.error(f"Face verification failed (score: {score:.2f}).")
                        return
                st.session_state[SessionKeys.USER_LOGGED_IN] = True
                st.session_state[SessionKeys.USERNAME] = user["username"]
                st.session_state[SessionKeys.USER_ROLE] = user["role"]
                st.session_state[SessionKeys.USER_ID] = user["id"]
                st.success("Login successful!")
                st.rerun()

    with tab_register:
        role = st.selectbox("Role", ["user", "caregiver"], key="reg_role")
        full_name = st.text_input("Full name", key="reg_full_name")
        new_username = st.text_input("New username", key="reg_username")
        new_password = st.text_input("New password (min 6 chars)", type="password", key="reg_password")
        trusted_name = st.text_input("Trusted person name", key="trusted_name")
        trusted_relation = st.text_input("Relation", value="family", key="trusted_relation")
        trusted_contact = st.text_input("Trusted person contact (phone/email)", key="trusted_contact")
        face_enroll = None
        if FEATURE_FACE_AUTH and face_auth.available:
            face_enroll = st.file_uploader("Face enrollment image (optional)", type=["jpg", "jpeg", "png"], key="face_enroll")
        if st.button("Create Account", key="create_account_btn"):
            if not new_username or not new_password or not trusted_name or not trusted_contact:
                st.error("Please fill all required registration fields.")
            else:
                success, msg = auth.register_user(
                    username=new_username,
                    password=new_password,
                    role=role,
                    full_name=full_name or new_username,
                    trusted_name=trusted_name,
                    trusted_contact=trusted_contact,
                    trusted_relation=trusted_relation,
                )
                if not success:
                    st.error(msg)
                else:
                    user = db.get_user_by_username(new_username)
                    if user and face_enroll and FEATURE_FACE_AUTH and face_auth.available:
                        if face_auth.enroll(user["id"], face_enroll.read()):
                            st.success("Face enrolled successfully.")
                    st.success("Registration complete. You can now login.")
    
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

    user_id = st.session_state.get(SessionKeys.USER_ID)
    if user_id:
        render_day_start_summary(db, user_id, language)
        maybe_create_inactivity_alert(db, user_id)
    
    
    # Recent memories
    st.markdown("---")
    st.markdown("### 📝 Recent Memories")
    
    try:
        recent_memories = (
            db.get_all_memories(language=language, user_id=user_id)
            if user_id
            else []
        )
        
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
    """Legacy helper retained for compatibility."""
    return bool(username and password)


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


def render_day_start_summary(db, user_id: str, language: str):
    today_key = f"day_summary_seen_{datetime.now().date().isoformat()}_{user_id}"
    if st.session_state.get(today_key):
        return
    memories = db.get_all_memories(user_id=user_id)[:8]
    if not memories:
        return
    recent = [m["text"] for m in memories[:3]]
    msg = "Good morning. Yesterday recap and today's reminders:\n- " + "\n- ".join(recent)
    st.info(msg)
    st.session_state[today_key] = True


def maybe_create_inactivity_alert(db, user_id: str):
    last_activity = db.get_last_activity(user_id)
    if not last_activity:
        return
    try:
        dt = datetime.fromisoformat(str(last_activity).replace(" ", "T"))
    except Exception:
        return
    if datetime.now() - dt > timedelta(days=1):
        db.create_alert(
            user_id=user_id,
            alert_type="inactivity",
            severity=2,
            message="No activity detected for more than 1 day. Please check on patient.",
        )
