"""
Home page for Dementia Chatbot
Handles login and main dashboard
"""
import hashlib
import os
import streamlit as st
from datetime import datetime, timedelta
from config import SessionKeys, FEATURE_FACE_AUTH, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from i18n import t, welcome_body
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
    if SessionKeys.SELECTED_LANGUAGE not in st.session_state:
        st.session_state[SessionKeys.SELECTED_LANGUAGE] = DEFAULT_LANGUAGE
    opts = list(SUPPORTED_LANGUAGES.keys())
    cur = st.session_state[SessionKeys.SELECTED_LANGUAGE]
    ix = opts.index(cur) if cur in opts else 0
    ui = st.selectbox(
        t(cur, "login.lang_label"),
        options=opts,
        index=ix,
        format_func=lambda c: SUPPORTED_LANGUAGES[c],
        key="login_interface_language",
    )
    if ui != st.session_state[SessionKeys.SELECTED_LANGUAGE]:
        st.session_state[SessionKeys.SELECTED_LANGUAGE] = ui
        st.rerun()
    ui = st.session_state[SessionKeys.SELECTED_LANGUAGE]

    title = t(ui, "login.title")
    sub = t(ui, "login.subtitle")
    st.markdown(
        f"""<div class="main-header" style="text-align:center;"><h1>{title}</h1><p style="font-size:18px;">{sub}</p></div>""",
        unsafe_allow_html=True,
    )

    ensure_app_initialized()
    db = st.session_state["components"]["db"]
    auth = AuthService(db)
    face_auth = FaceAuthService(db)

    tab_login, tab_register = st.tabs([t(ui, "login.tab_login"), t(ui, "login.tab_register")])
    with tab_login:
        username = st.text_input(t(ui, "login.username"), key="login_username")
        password = st.text_input(t(ui, "login.password"), type="password", key="login_password")
        face_file = None
        if FEATURE_FACE_AUTH and face_auth.available:
            face_file = st.file_uploader(t(ui, "login.face_optional"), type=["jpg", "jpeg", "png"], key="login_face")
        if st.button(t(ui, "login.btn"), type="primary", key="login_btn"):
            ok, user, message = auth.authenticate(username, password)
            if not ok:
                st.error(message)
            else:
                if FEATURE_FACE_AUTH and face_auth.available and db.get_face_embedding(user["id"]):
                    if not face_file:
                        st.error(t(ui, "login.face_required"))
                        return
                    face_ok, score = face_auth.verify(user["id"], face_file.read())
                    if not face_ok:
                        st.error(t(ui, "login.face_failed", score=score))
                        return
                st.session_state[SessionKeys.USER_LOGGED_IN] = True
                st.session_state[SessionKeys.USERNAME] = user["username"]
                st.session_state[SessionKeys.USER_ROLE] = user["role"]
                st.session_state[SessionKeys.USER_ID] = user["id"]
                st.success(t(ui, "login.success"))
                st.rerun()

    with tab_register:
        role = st.selectbox(t(ui, "register.role"), ["user", "caregiver"], key="reg_role")
        full_name = st.text_input(t(ui, "register.full_name"), key="reg_full_name")
        new_username = st.text_input(t(ui, "register.new_username"), key="reg_username")
        new_password = st.text_input(t(ui, "register.new_password"), type="password", key="reg_password")
        trusted_name = st.text_input(t(ui, "register.trusted_name"), key="trusted_name")
        trusted_relation = st.text_input(t(ui, "register.relation"), value="family", key="trusted_relation")
        trusted_contact = st.text_input(t(ui, "register.trusted_contact"), key="trusted_contact")
        face_enroll = None
        if FEATURE_FACE_AUTH and face_auth.available:
            face_enroll = st.file_uploader(t(ui, "register.face_enroll"), type=["jpg", "jpeg", "png"], key="face_enroll")
        if st.button(t(ui, "register.create"), key="create_account_btn"):
            if not new_username or not new_password or not trusted_name or not trusted_contact:
                st.error(t(ui, "register.fill_all"))
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
                            st.success(t(ui, "register.face_ok"))
                    st.success(t(ui, "register.done"))
    
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
        language = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
        st.error(t(language, "common.system_not_init"))
        return
    
    memory_system = components['memory_system']
    db = components['db']
    
    # Get user info
    username = st.session_state.get(SessionKeys.USERNAME, "")
    user_role = st.session_state.get(SessionKeys.USER_ROLE, "user")
    language = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    
    st.markdown(
        f"""### {t(language, "home.welcome", name=username)}

{welcome_body(user_role, language)}
"""
    )

    user_id = st.session_state.get(SessionKeys.USER_ID)
    if user_id:
        render_day_start_summary(components, db, user_id, language, username)
        maybe_create_inactivity_alert(db, user_id)
    
    
    # Recent memories for the selected interface language only (stored per-language)
    st.markdown("---")
    st.markdown(t(language, "home.recent_memories"))
    
    try:
        recent_memories = (
            db.get_all_memories(language=language, user_id=user_id) if user_id else []
        )

        if recent_memories:
            col_total, col_lang = st.columns(2)
            with col_total:
                st.metric(t(language, "home.metric_total"), len(recent_memories))
            with col_lang:
                st.metric(
                    t(language, "home.metric_ui_lang"),
                    SUPPORTED_LANGUAGES.get(language, language),
                )
            st.caption(
                t(
                    language,
                    "home.memory_scope_hint",
                    lang=SUPPORTED_LANGUAGES.get(language, language),
                )
            )

            for idx, memory in enumerate(recent_memories[:5], start=1):
                with st.container():
                    st.markdown(f"**{idx}. {_short_text(memory['text'], 110)}**")
                    st.caption(
                        f"{t(language, 'home.added')}: {memory['created_at']} • "
                        f"{t(language, 'home.source')}: {memory['source']}"
                    )
                    if len((memory.get("text") or "")) > 110:
                        with st.expander(t(language, "home.view_full")):
                            st.write(memory["text"])
                    if memory.get("tags"):
                        st.caption(t(language, "home.tags") + ": " + ", ".join(memory["tags"][:4]))
                    st.markdown("")
        else:
            st.info(
                t(
                    language,
                    "home.empty_for_language",
                    lang=SUPPORTED_LANGUAGES.get(language, language),
                )
            )
    
    except Exception as e:
        st.error(t(language, "home.error_memories", err=e))
    
    st.markdown("---")
    st.markdown(t(language, "home.quick_actions"))
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button(t(language, "home.btn_add"), use_container_width=True, key="home_add_memory"):
            st.session_state['nav_page'] = 'add_memory'
            st.rerun()
    
    with col2:
        if st.button(t(language, "home.btn_ask"), use_container_width=True, key="home_ask_assistant"):
            st.session_state['nav_page'] = 'ask_assistant'
            st.rerun()
    
    with col3:
        if st.button(t(language, "home.btn_settings"), use_container_width=True, key="home_settings"):
            st.session_state['nav_page'] = 'settings'
            st.rerun()


def authenticate_user(username: str, password: str) -> bool:
    """Legacy helper retained for compatibility."""
    return bool(username and password)


def _bullet_line(text: str, limit: int = 110) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def _collect_day_start_context(db, user_id: str, language: str) -> dict:
    """Today-dated rows → 'What need to cover'; other recent rows → Summary bullets."""
    today_d = datetime.now().date().isoformat()
    today_memories = db.search_memories_by_date(today_d, language=language, user_id=user_id)
    today_ids = {m.get("id") for m in today_memories if m.get("id")}

    recent_pool = db.get_all_memories(language=language, user_id=user_id)[:40]
    summary_memories = [m for m in recent_pool if m.get("id") not in today_ids][:15]

    return {
        "today_iso": today_d,
        "summary_memories": summary_memories,
        "today_memories": today_memories[:15],
    }


def _raw_summary_bullets(sm: list, language: str) -> str:
    fb = "\n".join(
        f"- {_bullet_line((m.get('text') or '').strip(), 88)}"
        for m in sm
        if (m.get("text") or "").strip()
    )
    return fb if fb.strip() else f"- {t(language, 'day_summary.empty_summary')}"


def _summary_cache_keys(user_id: str, language: str, fp: str) -> tuple[str, str]:
    base = f"home_summary_brief_{user_id}_{language}_{fp}"
    return base, base + "_llm"


def _clear_summary_cache(user_id: str, language: str, fp: str) -> None:
    b, meta = _summary_cache_keys(user_id, language, fp)
    st.session_state.pop(b, None)
    st.session_state.pop(meta, None)


def _raw_today_bullets(tm: list, language: str) -> str:
    fb = "\n".join(
        f"- {_bullet_line((m.get('text') or '').strip(), 88)}"
        for m in tm
        if (m.get("text") or "").strip()
    )
    return fb if fb.strip() else f"- {t(language, 'day_summary.empty_today_tasks')}"


def _tasks_cache_keys(user_id: str, language: str, fp: str) -> tuple[str, str]:
    base = f"home_tasks_brief_{user_id}_{language}_{fp}"
    return base, base + "_meta"


def _clear_tasks_cache(user_id: str, language: str, fp: str) -> None:
    b, meta = _tasks_cache_keys(user_id, language, fp)
    st.session_state.pop(b, None)
    st.session_state.pop(meta, None)


def _call_summarize_brief(gen, language: str, memories: list, focus: str | None):
    if focus:
        try:
            return gen(language=language, memories=memories, focus=focus)
        except TypeError:
            pass
    return gen(language=language, memories=memories)


def _build_summary_panel_markdown(
    ctx: dict,
    language: str,
    components: dict,
    user_id: str,
    fp: str,
) -> tuple[str, str]:
    """Returns (markdown, meta). meta is llm | failed | no_key | no_method | empty."""
    header = f"### {t(language, 'day_summary.section_summary')}\n\n"
    sm = ctx["summary_memories"]
    if not sm:
        return header + f"- {t(language, 'day_summary.empty_summary')}", "empty"

    cache_key, meta_key = _summary_cache_keys(user_id, language, fp)
    if cache_key not in st.session_state:
        llm = components.get("llm_integration")
        gen = getattr(llm, "summarize_memory_notes_brief", None) if llm else None
        env_key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
        if not callable(gen):
            st.session_state[cache_key] = _raw_summary_bullets(sm, language)
            st.session_state[meta_key] = "no_method"
        elif not env_key and not getattr(llm, "api_key", ""):
            st.session_state[cache_key] = _raw_summary_bullets(sm, language)
            st.session_state[meta_key] = "no_key"
        else:
            out = _call_summarize_brief(gen, language, sm, None)
            if out and out.strip():
                st.session_state[cache_key] = out.strip()
                st.session_state[meta_key] = "llm"
            else:
                st.session_state[cache_key] = _raw_summary_bullets(sm, language)
                st.session_state[meta_key] = "failed"
    return header + st.session_state[cache_key], str(st.session_state.get(meta_key, "failed"))


def _build_today_tasks_panel_markdown(
    ctx: dict,
    language: str,
    components: dict,
    user_id: str,
    fp: str,
) -> tuple[str, str]:
    header = f"### {t(language, 'day_summary.section_what_to_cover')}\n\n"
    tm = ctx["today_memories"]
    if not tm:
        return header + f"- {t(language, 'day_summary.empty_today_tasks')}", "empty"

    cache_key, meta_key = _tasks_cache_keys(user_id, language, fp)
    if cache_key not in st.session_state:
        llm = components.get("llm_integration")
        gen = getattr(llm, "summarize_memory_notes_brief", None) if llm else None
        env_key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
        if not callable(gen):
            st.session_state[cache_key] = _raw_today_bullets(tm, language)
            st.session_state[meta_key] = "no_method"
        elif not env_key and not getattr(llm, "api_key", ""):
            st.session_state[cache_key] = _raw_today_bullets(tm, language)
            st.session_state[meta_key] = "no_key"
        else:
            out = _call_summarize_brief(gen, language, tm, "today")
            if out and out.strip():
                st.session_state[cache_key] = out.strip()
                st.session_state[meta_key] = "llm"
            else:
                st.session_state[cache_key] = _raw_today_bullets(tm, language)
                st.session_state[meta_key] = "failed"
    return header + st.session_state[cache_key], str(st.session_state.get(meta_key, "failed"))


def render_day_start_summary(components: dict, db, user_id: str, language: str, username: str):
    """Two buttons: summary (LLM-paraphrased) vs today's dated tasks (on demand)."""
    _ = username
    mems = db.get_all_memories(language=language, user_id=user_id)[:30]
    if not mems:
        return

    fp = hashlib.md5(",".join(str(m.get("id") or "") for m in mems).encode()).hexdigest()[:16]
    ctx = _collect_day_start_context(db, user_id, language)

    sum_flag = f"home_open_summary_{user_id}_{language}_{fp}"
    task_flag = f"home_open_tasks_{user_id}_{language}_{fp}"

    st.subheader(t(language, "day_summary.card_title"))
    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            t(language, "home.btn_summary"),
            key=f"home_btn_summary_{user_id}_{language}",
            use_container_width=True,
        ):
            _clear_summary_cache(user_id, language, fp)
            st.session_state[sum_flag] = True
    with c2:
        if st.button(
            t(language, "home.btn_today_tasks"),
            key=f"home_btn_today_{user_id}_{language}",
            use_container_width=True,
        ):
            _clear_tasks_cache(user_id, language, fp)
            st.session_state[task_flag] = True

    if st.session_state.get(sum_flag):
        md, meta = _build_summary_panel_markdown(
            ctx, language, components, user_id, fp
        )
        st.markdown(md)
        if ctx["summary_memories"] and meta != "llm":
            cap = {
                "no_method": "home.summary_no_method",
                "no_key": "home.summary_raw_fallback",
                "failed": "home.summary_gemini_failed",
            }.get(meta, "home.summary_gemini_failed")
            st.caption(t(language, cap))
    if st.session_state.get(task_flag):
        md_t, meta_t = _build_today_tasks_panel_markdown(
            ctx, language, components, user_id, fp
        )
        st.markdown(md_t)
        if ctx["today_memories"] and meta_t != "llm":
            cap = {
                "no_method": "home.summary_no_method",
                "no_key": "home.summary_raw_fallback",
                "failed": "home.summary_gemini_failed",
            }.get(meta_t, "home.summary_gemini_failed")
            st.caption(t(language, cap))


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
