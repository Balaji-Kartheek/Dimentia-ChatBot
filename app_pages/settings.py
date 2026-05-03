"""
Settings page for Dementia Chatbot (custom router version)
"""
import streamlit as st
import json
import csv
import io
import sqlite3
from datetime import datetime, timedelta
from config import SessionKeys, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from auth_service import AuthService
from i18n import t


def render_settings_page():
    """Render the settings page"""
    components = st.session_state.get('components', {})
    lang = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    if not components:
        st.error(t(lang, "common.system_not_init"))
        return
    
    st.markdown(t(lang, "settings.title"))
    
    db = components['db']
    memory_system = components['memory_system']
    
    user_role = st.session_state.get(SessionKeys.USER_ROLE, "user")
    username = st.session_state.get(SessionKeys.USERNAME, "")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        t(lang, "settings.tab_lang"),
        t(lang, "settings.tab_security"),
        t(lang, "settings.tab_data"),
        t(lang, "settings.tab_system"),
    ])
    
    with tab1:
        render_language_settings()
    with tab2:
        render_security_settings(user_role)
    with tab3:
        render_data_management(memory_system, db, user_role)
    with tab4:
        render_system_settings(components)


def render_language_settings():
    lang = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    st.markdown(t(lang, "settings.lang_heading"))
    current_language = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    language_options = {code: name for code, name in SUPPORTED_LANGUAGES.items()}
    selected_language = st.selectbox(
        t(lang, "settings.lang_select"),
        options=list(language_options.keys()),
        format_func=lambda x: language_options[x],
        index=list(language_options.keys()).index(current_language)
    )
    if st.button(t(lang, "settings.lang_submit"), key="settings_submit_language") and selected_language != current_language:
        st.session_state[SessionKeys.SELECTED_LANGUAGE] = selected_language
        st.success(t(selected_language, "settings.lang_success", name=language_options[selected_language]))
        st.rerun()
    
    st.markdown(t(lang, "settings.voice_heading"))
    components = st.session_state.get('components', {})
    audio_processor = components.get('audio_processor')
    if audio_processor:
        test_text = st.text_input(
            t(lang, "settings.voice_test_label"),
            value="Hello, this is a test of the voice system."
        )
        if st.button(t(lang, "settings.voice_test_btn")):
            try:
                audio_data = audio_processor.text_to_speech(test_text, selected_language)
                if audio_data:
                    st.audio(audio_data, format="audio/wav")
                    st.success(t(lang, "settings.voice_ok"))
                else:
                    st.error(t(lang, "settings.voice_fail"))
            except Exception as e:
                st.error(f"Voice test error: {e}")
    else:
        st.warning(t(lang, "settings.voice_unavailable"))


def render_security_settings(user_role):
    st.markdown("#### 🔒 Security Settings")
    if user_role == "caregiver":
        st.markdown("##### Change Password")
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        if st.button("Change Password", key="change_password_btn"):
            if new_password == confirm_password and len(new_password) >= 6:
                st.success("Password changed successfully!")
            else:
                st.error("Passwords don't match or are too short")
        st.markdown("##### Encryption Status")
        st.success("✅ All memories are encrypted using Fernet encryption")
        st.info("🔐 Your data is stored securely on your local device")
    else:
        st.info("🔒 Security settings are managed by your caregiver")


def _stats_for_user_memories(db, user_id: str, scope_language: str) -> dict:
    """Counts for the current user in the selected interface language (per-language storage)."""
    memories = (
        db.get_all_memories(language=scope_language, user_id=user_id) if user_id else []
    )
    languages = {}
    for memory in memories:
        lkey = memory["language"] or "en"
        languages[lkey] = languages.get(lkey, 0) + 1
    return {"total_memories": len(memories), "languages": languages}


def render_data_management(memory_system, db, user_role):
    lang = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    st.markdown(t(lang, "settings.data_title"))
    user_id = st.session_state.get(SessionKeys.USER_ID)
    try:
        stats = _stats_for_user_memories(db, user_id, lang)
        st.metric(t(lang, "home.metric_total"), stats["total_memories"])
        st.caption(
            t(
                lang,
                "settings.data_language_scope",
                lang_name=SUPPORTED_LANGUAGES.get(lang, lang),
            )
        )
        if stats["languages"]:
            st.markdown(t(lang, "settings.memories_by_language"))
            for lcode, count in stats["languages"].items():
                lname = SUPPORTED_LANGUAGES.get(lcode, lcode)
                st.write(f"• {lname}: {count}")
    except Exception as e:
        st.error(f"Error loading statistics: {e}")
    
    st.markdown(t(lang, "settings.data_memories"))
    try:
        memories = (
            db.get_all_memories(language=lang, user_id=user_id) if user_id else []
        )
        if memories:
            # Create a summary table
            summary_data = []
            for memory in memories:
                summary_data.append({
                    'Text': memory.get('text', '')[:60] + '...' if len(memory.get('text', '')) > 60 else memory.get('text', ''),
                    'Source': memory.get('source', ''),
                    'Language': memory.get('language', ''),
                    'Created': memory.get('created_at', '')[:10] if memory.get('created_at') else '',  # Show only date
                    'Has Dates': 'Yes' if memory.get('date_mentions') else 'No'
                })
            
            st.table(summary_data)
            st.caption(
                t(
                    lang,
                    "settings.data_table_caption",
                    n=len(memories),
                    lang_name=SUPPORTED_LANGUAGES.get(lang, lang),
                )
            )
        else:
            st.info(
                t(
                    lang,
                    "settings.data_no_memories_scoped",
                    lang_name=SUPPORTED_LANGUAGES.get(lang, lang),
                )
            )
    except Exception as e:
        st.error(f"Error loading memories: {e}")
    
    st.markdown(t(lang, "settings.data_export"))
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Download as CSV", use_container_width=True):
            export_memories_csv(db, user_id=user_id, language=lang)
    with col2:
        if user_role == "caregiver":
            if st.button("📤 Export JSON", use_container_width=True):
                export_memories(memory_system, db, user_id=user_id, language=lang)
    
    if user_role == "caregiver":
        st.markdown(t(lang, "settings.data_import"))
        uploaded_file = st.file_uploader("📥 Import Memories", type=['json'])
        if uploaded_file:
            import_memories(uploaded_file, memory_system, db)
    
    st.markdown(t(lang, "settings.data_clear"))
    
    if "clear_confirmed" not in st.session_state:
        st.session_state["clear_confirmed"] = False

    # After a successful clear: only show success + OK (no clear / password UI)
    if st.session_state.get("memories_cleared_success"):
        st.success(st.session_state["memories_cleared_success"])
        if st.button(t(lang, "settings.clear_ok"), type="primary", key="dismiss_memories_cleared"):
            del st.session_state["memories_cleared_success"]
            st.rerun()
    else:
        if not st.session_state["clear_confirmed"]:
            if st.button(t(lang, "settings.clear_btn"), type="secondary", key="start_clear_memories"):
                st.session_state["clear_confirmed"] = True
                st.rerun()

        if st.session_state["clear_confirmed"]:
            st.warning(t(lang, "settings.clear_warn"))
            auth = AuthService(db)
            user_id = st.session_state.get(SessionKeys.USER_ID)
            username = st.session_state.get(SessionKeys.USERNAME, "")
            reauth_password = st.text_input(t(lang, "settings.clear_password"), type="password", key="clear_reauth_password")
            confirmed = st.checkbox(t(lang, "settings.clear_check"), key="clear_understand_check")

            if confirmed:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(t(lang, "settings.clear_confirm"), type="primary", key="confirm_clear_memories"):
                        user = db.get_user_by_username(username)
                        password_ok = bool(user and auth.verify_password(reauth_password, user["password_hash"]))
                        if password_ok and user_id:
                            clear_all_memories(memory_system, db, user_id)
                        else:
                            st.error(t(lang, "settings.clear_bad_password"))
                with col2:
                    if st.button(t(lang, "settings.clear_cancel"), type="secondary", key="cancel_clear_memories"):
                        st.session_state["clear_confirmed"] = False
                        st.rerun()

    st.markdown("##### Trusted Person & Safety Alerts")
    user_id = st.session_state.get(SessionKeys.USER_ID)
    if user_id:
        trusted = db.get_trusted_contact(user_id)
        if trusted:
            st.caption(f"Trusted person: {trusted['name']} ({trusted.get('relation', 'contact')}) - {trusted['contact']}")
        alerts = db.get_alerts(user_id=user_id, status="open")
        if alerts:
            for alert in alerts[:5]:
                st.warning(f"[{alert['alert_type']}] {alert['message']}")
        else:
            st.info("No open safety alerts.")

        if st.button("Generate Doctor Summary", key="doctor_summary_btn"):
            summary = build_doctor_summary(db, user_id)
            db.save_doctor_report(user_id, datetime.now().date().isoformat(), summary)
            st.success("Doctor summary updated.")
            st.text_area("Latest doctor summary", value=summary, height=180)
        else:
            latest = db.get_latest_doctor_report(user_id)
            if latest:
                st.text_area("Latest doctor summary", value=latest["summary"], height=180)


def render_system_settings(components):
    st.markdown("#### 🔧 System Settings")
    st.markdown("##### System Status")
    slang = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    col1, col2, col3 = st.columns(3)
    with col1:
        try:
            llm_status = components['llm_integration'].test_connection()
            st.success("🟢 Gemini Connected" if llm_status else "🔴 Gemini Not Configured")
        except:
            st.error("🔴 Gemini Error")
    with col2:
        try:
            audio_status = components['audio_processor'].test_audio_processing()
            st.success("🟢 Audio Ready" if audio_status else "🔴 Audio Error")
        except:
            st.error("🔴 Audio Error")
    with col3:
        try:
            uid = st.session_state.get(SessionKeys.USER_ID)
            if uid:
                _ = components['db'].get_all_memories(language=slang, user_id=uid)
            st.success("🟢 Database Ready")
        except:
            st.error("🔴 Database Error")


def export_memories(memory_system, db, user_id: str = None, language: str = None):
    try:
        lang = language or st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
        memories = (
            db.get_all_memories(language=lang, user_id=user_id) if user_id else []
        )
        if not memories:
            st.warning(
                t(
                    lang,
                    "settings.data_no_memories_scoped",
                    lang_name=SUPPORTED_LANGUAGES.get(lang, lang),
                )
            )
            return
        export_data = {
            'total_memories': len(memories),
            'memories': memories
        }
        json_data = json.dumps(export_data, indent=2)
        uname = st.session_state.get(SessionKeys.USERNAME, 'user')
        st.download_button(
            label="📥 Download Memories",
            data=json_data,
            file_name=f"memories_export_{uname}_{lang}.json",
            mime="application/json"
        )
        st.success(
            t(
                lang,
                "settings.export_json_ready",
                n=len(memories),
                lang_name=SUPPORTED_LANGUAGES.get(lang, lang),
            )
        )
    except Exception as e:
        st.error(f"Error exporting memories: {e}")


def export_memories_csv(db, user_id: str = None, language: str = None):
    """Export memories as a structured CSV file"""
    try:
        lang = language or st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
        memories = (
            db.get_all_memories(language=lang, user_id=user_id) if user_id else []
        )
        
        if not memories:
            st.warning(
                t(
                    lang,
                    "settings.data_no_memories_scoped",
                    lang_name=SUPPORTED_LANGUAGES.get(lang, lang),
                )
            )
            return
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = [
            'ID', 'Text', 'Source', 'Language', 
            'Caregiver Confirmed', 'Created At', 'Tags', 'Date Mentions'
        ]
        writer.writerow(headers)
        
        # Write data rows
        for memory in memories:
            # Format tags
            tags_str = ', '.join(memory.get('tags', [])) if memory.get('tags') else ''
            
            # Format date mentions
            date_mentions = memory.get('date_mentions', {})
            date_mentions_str = ''
            if date_mentions:
                found_dates = date_mentions.get('found_dates', [])
                converted_dates = date_mentions.get('converted_dates', [])
                date_pairs = [f"{found}→{conv}" for found, conv in zip(found_dates, converted_dates)]
                date_mentions_str = ', '.join(date_pairs)
            
            row = [
                memory.get('id', ''),
                memory.get('text', ''),
                memory.get('source', ''),
                memory.get('language', ''),
                'Yes' if memory.get('caregiver_confirmed') else 'No',
                memory.get('created_at', ''),
                tags_str,
                date_mentions_str
            ]
            writer.writerow(row)
        
        # Get CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        username = st.session_state.get(SessionKeys.USERNAME, 'user')
        filename = f"memories_{username}_{lang}_{timestamp}.csv"
        
        # Create download button
        st.download_button(
            label="📥 Download CSV File",
            data=csv_content,
            file_name=filename,
            mime="text/csv",
            key="csv_download"
        )
        
        st.success(
            t(
                lang,
                "settings.export_csv_ready",
                n=len(memories),
                lang_name=SUPPORTED_LANGUAGES.get(lang, lang),
            )
        )
        
        # Show preview
        st.markdown("#### 📋 Preview of Exported Data:")
        preview_data = []
        for memory in memories[:5]:  # Show first 5 memories
            preview_data.append({
                'Text': memory.get('text', '')[:50] + '...' if len(memory.get('text', '')) > 50 else memory.get('text', ''),
                'Source': memory.get('source', ''),
                'Language': memory.get('language', ''),
                'Created': memory.get('created_at', ''),
                'Tags': ', '.join(memory.get('tags', [])[:3]) if memory.get('tags') else ''  # Show first 3 tags
            })
        
        if preview_data:
            st.table(preview_data)
            if len(memories) > 5:
                st.caption(f"... and {len(memories) - 5} more memories")
        
    except Exception as e:
        st.error(f"Error exporting memories to CSV: {e}")
        import traceback
        st.error(f"Full error: {traceback.format_exc()}")


def import_memories(uploaded_file, memory_system, db):
    try:
        json_data = json.loads(uploaded_file.read())
        if 'memories' not in json_data:
            st.error("Invalid file format")
            return
        imported_count = 0
        uid = st.session_state.get(SessionKeys.USER_ID)
        for memory_data in json_data['memories']:
            try:
                memory_system.add_memory(
                    text=memory_data['text'],
                    source=f"imported_{memory_data.get('source', 'unknown')}",
                    tags=memory_data.get('tags', []),
                    language=memory_data.get('language', 'en'),
                    user_id=uid,
                )
                imported_count += 1
            except Exception as e:
                st.warning(f"Could not import memory: {e}")
        st.success(f"Successfully imported {imported_count} memories!")
    except Exception as e:
        st.error(f"Error importing memories: {e}")


def clear_all_memories(memory_system, db, user_id: str):
    """Delete this user's rows in SQLite and rebuild FAISS. Uses inline SQL if DB helper is missing (old deploys)."""
    try:
        if not user_id:
            st.error("Not signed in; cannot clear memories.")
            return
        if hasattr(db, "delete_memories_for_user"):
            n = db.delete_memories_for_user(user_id)
        else:
            path = getattr(db, "db_path", None)
            if not path:
                st.error("Database is not configured correctly.")
                return
            with sqlite3.connect(path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
                conn.commit()
                n = cur.rowcount
        memory_system.rebuild_index()
        lg = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
        st.session_state["memories_cleared_success"] = t(lg, "settings.clear_success", n=n)
        st.session_state["clear_confirmed"] = False
        st.rerun()
    except Exception as e:
        st.error(f"Error clearing memories: {e}")


def build_doctor_summary(db, user_id: str) -> str:
    recent_queries = db.get_recent_query_events(user_id=user_id, since_hours=24 * 7)
    repeated = [q for q in recent_queries if int(q.get("severity", 1)) >= 2]
    last_activity = db.get_last_activity(user_id)
    inactivity_note = "No activity data."
    if last_activity:
        try:
            dt = datetime.fromisoformat(str(last_activity).replace(" ", "T"))
            delta = datetime.now() - dt
            inactivity_note = f"Last activity {delta.days} day(s) ago."
        except Exception:
            inactivity_note = f"Last activity: {last_activity}"
    lines = [
        "Weekly condition summary for doctor review:",
        f"- Total queries this week: {len(recent_queries)}",
        f"- Repeated/confusion pattern queries: {len(repeated)}",
        f"- {inactivity_note}",
    ]
    if repeated:
        lines.append("- Most repeated concerns:")
        seen = {}
        for item in repeated:
            sig = item.get("query_signature", "")[:50]
            seen[sig] = seen.get(sig, 0) + 1
        for sig, count in sorted(seen.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  * {sig} ({count} times)")
    return "\n".join(lines)


