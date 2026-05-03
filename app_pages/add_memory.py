"""
Add Memory page for Dementia Chatbot (custom router version)
"""
import streamlit as st
from config import SessionKeys, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from i18n import t


def _short_text(text: str, limit: int = 140) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def render_add_memory_page():
    """Render the add memory page"""
    components = st.session_state.get('components', {})
    language = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    if not components:
        st.error(t(language, "common.system_not_init"))
        return
    
    memory_system = components['memory_system']
    audio_processor = components['audio_processor']
    entity_extractor = components['entity_extractor']
    db = components['db']
    
    user_role = st.session_state.get(SessionKeys.USER_ROLE, "user")
    username = st.session_state.get(SessionKeys.USERNAME, "")
    
    st.markdown(t(language, "add.title"))
    st.markdown(t(language, "add.subtitle"))
    tab_voice, tab_text = st.tabs([t(language, "add.tab_voice"), t(language, "add.tab_text")])
    with tab_voice:
        render_mic_record(memory_system, audio_processor, entity_extractor, db, language, username)
    with tab_text:
        render_text_input(memory_system, entity_extractor, db, language, username)
    
    st.markdown("---")
    st.markdown(t(language, "add.recent"))
    
    try:
        uid = st.session_state.get(SessionKeys.USER_ID)
        recent_memories = (
            db.get_all_memories(language=language, user_id=uid) if uid else []
        )
        
        if recent_memories:
            search_term = st.text_input(t(language, "add.search"), placeholder="…")
            filtered_memories = recent_memories
            if search_term and search_term.strip():
                s = search_term.lower().strip()
                filtered_memories = [m for m in recent_memories if s in (m.get("text", "").lower())]

            display_memories = filtered_memories[:10]
            st.caption(f"Showing {len(display_memories)} of {len(filtered_memories)} matching memories")

            for idx, memory in enumerate(display_memories):
                st.markdown(f"**{idx+1}.** {_short_text(memory['text'], 140)}")
                st.caption(
                    f"Added: {memory['created_at']} | Source: {memory['source']} | "
                    f"Language: {SUPPORTED_LANGUAGES.get(memory['language'], memory['language'])}"
                )
                if len((memory.get("text") or "")) > 140:
                    with st.expander(f"View full memory #{idx+1}"):
                        st.write(memory["text"])

                if memory['tags']:
                    st.caption("Tags: " + ", ".join(memory['tags'][:6]))

                if user_role == "caregiver":
                    col_verify, col_delete = st.columns(2)
                    with col_verify:
                        if st.button("✅ Verify", key=f"verify_{memory['id']}", use_container_width=True):
                            memory_system.db.update_memory_caregiver_confirmed(memory['id'], True)
                            db.log_activity(username, "verified_memory", memory['id'])
                            st.success("Memory verified!")
                            st.rerun()
                    with col_delete:
                        if st.button("🗑️ Delete", key=f"delete_{memory['id']}", use_container_width=True):
                            memory_system.delete_memory(memory['id'])
                            db.log_activity(username, "deleted_memory", memory['id'])
                            st.success("Memory deleted!")
                            st.rerun()

                st.markdown("---")
        else:
            st.info(
                t(
                    language,
                    "add.empty_for_language",
                    lang=SUPPORTED_LANGUAGES.get(language, language),
                )
            )
    
    except Exception as e:
        st.error(f"Error loading memories: {e}")


def render_voice_input(memory_system, audio_processor, entity_extractor, db, language, username):
    """Render voice input via file upload (wav/mp3/m4a)"""
    st.markdown("#### 🎤 Upload a Voice Note")
    uploaded = st.file_uploader("Upload an audio file", type=["wav", "mp3", "m4a"])
    if uploaded is not None:
        audio_bytes = uploaded.read()
        st.audio(audio_bytes, format="audio/wav")
        
        # Initialize session state for uploaded transcription
        if 'uploaded_transcription' not in st.session_state:
            st.session_state.uploaded_transcription = None
        if 'uploaded_entities' not in st.session_state:
            st.session_state.uploaded_entities = None
        
        # Process recording button
        if st.button("🔍 Process Recording", type="primary", key="process_uploaded"):
            with st.spinner("Processing audio..."):
                try:
                    transcribed_text = audio_processor.process_streamlit_audio(audio_bytes, language)
                    if transcribed_text:
                        st.session_state.uploaded_transcription = transcribed_text
                        entities = entity_extractor.extract_entities(transcribed_text)
                        st.session_state.uploaded_entities = entities
                        st.rerun()
                    else:
                        st.error("❌ Could not transcribe audio. Please try another file.")
                except Exception as e:
                    st.error(f"Error processing audio: {e}")
        
        # Display processed transcription and save option
        if st.session_state.uploaded_transcription:
            st.success("✅ Audio transcribed successfully!")
            st.markdown(f"**Transcribed text:** {st.session_state.uploaded_transcription}")
            
            entities = st.session_state.uploaded_entities
            if entities and any(entities.values()):
                st.markdown("#### 🔍 Extracted Information:")
                display_entities(entities)
            
            # Save memory button (outside the processing conditional)
            if st.button("💾 Save Memory", type="primary", key="save_uploaded_memory"):
                save_memory(memory_system, db, st.session_state.uploaded_transcription, "voice", entities, language, username)
                # Clear processed data after saving
                st.session_state.uploaded_transcription = None
                st.session_state.uploaded_entities = None


def render_mic_record(memory_system, audio_processor, entity_extractor, db, language, username):
    """Record voice using Streamlit audio recorder"""
    st.markdown("#### 🎙️ Record Your Memory")
    
    # Use Streamlit's built-in audio recorder
    try:
        from st_audiorec import st_audiorec
        audio_bytes = st_audiorec()
        
        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            
            # Initialize session state for processed transcription
            if 'processed_transcription' not in st.session_state:
                st.session_state.processed_transcription = None
            if 'processed_entities' not in st.session_state:
                st.session_state.processed_entities = None
            
            # Process recording button
            if st.button("🔍 Process Recording", type="primary", key="process_recording"):
                with st.spinner("Processing audio..."):
                    try:
                        transcribed_text = audio_processor.process_streamlit_audio(audio_bytes, language)
                        if transcribed_text and len(transcribed_text.strip()) > 0:
                            st.session_state.processed_transcription = transcribed_text
                            entities = entity_extractor.extract_entities(transcribed_text)
                            st.session_state.processed_entities = entities
                            st.rerun()
                        else:
                            st.warning("⚠️ No speech detected in the audio. Please try speaking more clearly.")
                            st.info("💡 Make sure you're speaking clearly and close to the microphone.")
                    except Exception as e:
                        st.error(f"❌ Audio processing failed: {str(e)}")
                        st.info("💡 Please try recording again or use text input instead.")
            
            # Display processed transcription and save option
            if st.session_state.processed_transcription:
                st.success("✅ Audio transcribed successfully!")
                st.markdown(f"**Transcribed text:** {st.session_state.processed_transcription}")
                
                entities = st.session_state.processed_entities
                if entities and any(entities.values()):
                    st.markdown("#### 🔍 Extracted Information:")
                    display_entities(entities)
                
                # Save memory button (outside the processing conditional)
                if st.button("💾 Save Memory", type="primary", key="save_voice_memory"):
                    save_memory(memory_system, db, st.session_state.processed_transcription, "voice", entities, language, username)
                    # Clear processed data after saving
                    st.session_state.processed_transcription = None
                    st.session_state.processed_entities = None
                        
    except ImportError:
        st.error("Audio recording not available. Please install 'streamlit-audiorec' package.")
        st.info("Run: pip install streamlit-audiorec")
    except Exception as e:
        st.error(f"Audio recording error: {e}")
        # Fallback to text input
        st.markdown("**Alternative: Use text input below**")


def render_text_input(memory_system, entity_extractor, db, language, username):
    """Render text input interface"""
    st.markdown("#### ✏️ Type Your Memory")
    st.caption("Type your memory and click Save Memory.")

    if "add_memory_text_input" not in st.session_state:
        st.session_state["add_memory_text_input"] = ""

    memory_text = st.text_area(
        "Memory text",
        placeholder="Example: I have a doctor's appointment tomorrow at 2 PM with Dr. Smith...",
        height=150,
        key="add_memory_text_input"
    )
    
    # Always show submit button; disable when empty
    is_text_present = bool(memory_text and memory_text.strip())
    col_save, col_clear = st.columns([2, 1])
    with col_save:
        save_clicked = st.button("💾 Save Memory", type="primary", disabled=not is_text_present, use_container_width=True)
    with col_clear:
        clear_clicked = st.button("🧹 Clear", use_container_width=True)
        if clear_clicked:
            st.session_state["add_memory_text_input"] = ""
            st.rerun()
    
    if is_text_present:
        entities = entity_extractor.extract_entities(memory_text)
        if any(entities.values()):
            st.markdown("#### 🔍 Extracted Information:")
            display_entities(entities)
        if save_clicked:
            save_memory(memory_system, db, memory_text, "text", entities, language, username)


def display_entities(entities):
    """Display extracted entities"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        dates = list(dict.fromkeys(entities.get('dates', [])))
        if dates:
            st.markdown("**📅 Dates:**")
            for date in dates:
                st.write(f"• {date}")
        
        times = list(dict.fromkeys(entities.get('times', [])))
        if times:
            st.markdown("**🕐 Times:**")
            for time in times:
                st.write(f"• {time}")
    
    with col2:
        medications = list(dict.fromkeys(entities.get('medications', [])))
        if medications:
            st.markdown("**💊 Medications:**")
            for med in medications:
                st.write(f"• {med}")
        
        appointments = list(dict.fromkeys(entities.get('appointments', [])))
        if appointments:
            st.markdown("**📅 Appointments:**")
            for apt in appointments:
                st.write(f"• {apt}")
    
    with col3:
        people = list(dict.fromkeys(entities.get('people', [])))
        if people:
            st.markdown("**👥 People:**")
            for person in people:
                st.write(f"• {person}")
        
        locations = list(dict.fromkeys(entities.get('locations', [])))
        if locations:
            st.markdown("**📍 Locations:**")
            for location in locations:
                st.write(f"• {location}")


def save_memory(memory_system, db, text, source, entities, language, username):
    """Save memory to the system"""
    try:
        st.info(f"🔄 Saving memory: '{text[:50]}...'")
        
        # Prepare tags from entities (deduplicated and normalized)
        tags = []
        seen = set()
        for entity_type, entity_list in (entities or {}).items():
            if not entity_list:
                continue
            for entity in entity_list:
                if not entity:
                    continue
                normalized = " ".join(str(entity).split())
                key = (entity_type, normalized.lower())
                if key in seen:
                    continue
                seen.add(key)
                tags.append(f"{entity_type}:{normalized}")
        
        st.info(f"📝 Tags prepared: {tags}")
        
        user_id = st.session_state.get(SessionKeys.USER_ID)
        has_health_signal = bool((entities or {}).get("medications") or (entities or {}).get("appointments"))
        importance = 0.9 if has_health_signal else 0.6

        memory_id = memory_system.add_memory(
            text=text,
            source=source,
            tags=tags,
            language=language,
            user_id=user_id,
            source_modality=source,
            importance=importance,
        )
        
        st.info(f"💾 Memory ID: {memory_id}")
        
        db.log_activity(username, "added_memory", memory_id, f"Source: {source}")
        
        st.success("✅ Memory saved successfully!")
        st.balloons()
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error saving memory: {e}")
        import traceback
        st.error(f"Full error: {traceback.format_exc()}")


