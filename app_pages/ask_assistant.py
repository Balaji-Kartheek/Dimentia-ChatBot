"""
Ask Assistant page for Dementia Chatbot (custom router version)
"""
import streamlit as st
from datetime import datetime
from config import SessionKeys, SUPPORTED_LANGUAGES


def _short_text(text: str, limit: int = 180) -> str:
    """Return a compact one-line preview for long text blocks."""
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def render_ask_assistant_page():
    """Render the ask assistant page"""
    st.markdown("### 🔍 Ask Your Memory Assistant")
    
    components = st.session_state.get('components', {})
    if not components:
        st.error("System components not initialized")
        return
    
    memory_system = components['memory_system']
    audio_processor = components['audio_processor']
    llm_integration = components['llm_integration']
    db = components['db']
    
    user_role = st.session_state.get(SessionKeys.USER_ROLE, "user")
    language = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, "en")
    username = st.session_state.get(SessionKeys.USERNAME, "")
    
    # Input method selection
    st.markdown("#### Ask in the way you prefer")
    tab_voice, tab_text = st.tabs(["🎙️ Voice Question", "✏️ Text Question"])
    with tab_voice:
        render_voice_question_record(memory_system, audio_processor, llm_integration, db, language, username)
    with tab_text:
        render_text_question(memory_system, llm_integration, db, language, username)
    
    # Show conversation history
    if 'conversation_history' not in st.session_state:
        st.session_state['conversation_history'] = []
    
    if st.session_state['conversation_history']:
        st.markdown("---")
        st.markdown("### 💬 Recent Questions")
        recent_entries = list(reversed(st.session_state['conversation_history'][-5:]))
        options = [f"{idx + 1}. {_short_text(e['question'], 70)} ({e['timestamp']})" for idx, e in enumerate(recent_entries)]
        selected_label = st.selectbox("Select a recent question", options=options, key="recent_question_select")
        selected_idx = options.index(selected_label)
        selected_entry = recent_entries[selected_idx]

        st.markdown(f"**Question:** {_short_text(selected_entry['question'], 180)}")
        with st.expander("View full question"):
            st.write(selected_entry['question'])

        st.markdown(f"**Answer:** {_short_text(selected_entry['answer'], 240)}")
        with st.expander("View full answer"):
            st.write(selected_entry['answer'])

        if selected_entry.get('relevant_memories'):
            st.markdown("**Sources used:**")
            for memory in selected_entry['relevant_memories'][:3]:
                st.caption(f"• {_short_text(memory['text'], 120)}")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔊 Play Answer", key=f"play_recent_{selected_idx}", use_container_width=True):
                play_audio_response(selected_entry['answer'], language)
        with col2:
            if st.button("↩️ Reuse Question", key=f"reuse_recent_{selected_idx}", use_container_width=True):
                st.session_state["ask_question_input"] = selected_entry["question"]
                st.rerun()
        with col3:
            if st.button("🗑️ Remove", key=f"remove_recent_{selected_idx}", use_container_width=True):
                absolute_index = len(st.session_state['conversation_history']) - 1 - selected_idx
                st.session_state['conversation_history'].pop(absolute_index)
                st.rerun()


def render_voice_question(memory_system, audio_processor, llm_integration, db, language, username):
    """Render voice question via file upload"""
    st.markdown("#### 🎤 Upload Your Question as Audio")
    uploaded = st.file_uploader("Upload an audio file", type=["wav", "mp3", "m4a"], key="ask_audio")
    if uploaded is not None:
        audio_bytes = uploaded.read()
        st.audio(audio_bytes, format="audio/wav")
        
        if st.button("🔍 Process Question", type="primary"):
            with st.spinner("Processing your question..."):
                try:
                    transcribed_question = audio_processor.process_streamlit_audio(audio_bytes)
                    if transcribed_question:
                        st.success("✅ Question understood!")
                        st.markdown(f"**Your question:** {transcribed_question}")
                        response = generate_response(
                            transcribed_question, memory_system, llm_integration, 
                            db, language, username, "voice"
                        )
                        display_response(response, transcribed_question, language)
                    else:
                        st.error("❌ Could not understand your question. Please try another file.")
                except Exception as e:
                    st.error(f"Error processing audio: {e}")


def render_voice_question_record(memory_system, audio_processor, llm_integration, db, language, username):
    """Record voice using Streamlit audio recorder"""
    st.markdown("#### 🎙️ Record Your Question")
    
    # Use Streamlit's built-in audio recorder
    try:
        from st_audiorec import st_audiorec
        audio_bytes = st_audiorec()
        
        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            if st.button("🔍 Process Question", type="primary"):
                with st.spinner("Processing your question..."):
                    try:
                        # Use actual audio transcription
                        try:
                            transcribed_question = audio_processor.process_streamlit_audio(audio_bytes)
                            if transcribed_question and len(transcribed_question.strip()) > 0:
                                st.success("✅ Question understood!")
                                st.markdown(f"**Your question:** {transcribed_question}")
                                response = generate_response(
                                    transcribed_question, memory_system, llm_integration, 
                                    db, language, username, "voice"
                                )
                                display_response(response, transcribed_question, language)
                            else:
                                st.warning("⚠️ No speech detected in the audio. Please try speaking more clearly.")
                                st.info("💡 Make sure you're speaking clearly and close to the microphone.")
                        except Exception as e:
                            st.error(f"❌ Audio processing failed: {str(e)}")
                            st.info("💡 Please try recording again or use text input instead.")
                    except Exception as e:
                        st.error(f"Error processing audio: {e}")
                        
    except ImportError:
        st.error("Audio recording not available. Please install 'streamlit-audiorec' package.")
        st.info("Run: pip install streamlit-audiorec")
    except Exception as e:
        st.error(f"Audio recording error: {e}")
        # Fallback to text input
        st.markdown("**Alternative: Use text input below**")


def render_text_question(memory_system, llm_integration, db, language, username):
    """Render text question interface"""
    st.markdown("#### ✏️ Type Your Question")
    st.caption("Type your question and click Submit Question.")

    if "ask_question_input" not in st.session_state:
        st.session_state["ask_question_input"] = ""

    question = st.text_input(
        "Question",
        placeholder="Example: When is my next doctor's appointment?",
        key="ask_question_input"
    )
    
    # Quick question suggestions
    st.markdown("**Quick questions**")
    quick_questions = get_quick_questions(language)

    quick_pick = st.selectbox("Pick a quick question", options=["Select..."] + quick_questions, key="quick_question_picker")
    if quick_pick != "Select..." and quick_pick != st.session_state.get("ask_question_input", ""):
        st.session_state["ask_question_input"] = quick_pick
        st.rerun()

    submit_clicked = st.button(
        "✅ Submit Question",
        type="primary",
        disabled=not bool(question and question.strip()),
        use_container_width=True
    )

    if submit_clicked:
        with st.spinner("Thinking about your question..."):
            response = generate_response(
                question, memory_system, llm_integration, 
                db, language, username, "text"
            )
            display_response(response, question, language)


def generate_response(question, memory_system, llm_integration, db, language, username, source):
    """Generate response to user question"""
    try:
        response_data = llm_integration.generate_response(
            query=question,
            user_context=f"User: {username}, Language: {language}",
            language=language
        )
        
        db.log_activity(username, "asked_question", None, f"Question: {question[:100]}...")
        
        conversation_entry = {
            'question': question,
            'answer': response_data['response'],
            'relevant_memories': response_data.get('relevant_memories', []),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'source': source
        }
        
        if 'conversation_history' not in st.session_state:
            st.session_state['conversation_history'] = []
        
        st.session_state['conversation_history'].append(conversation_entry)
        
        return response_data
        
    except Exception as e:
        return {
            'response': f"I'm sorry, I encountered an error while processing your question: {str(e)}",
            'relevant_memories': [],
            'context_used': "",
            'error': str(e)
        }


def display_response(response_data, question, language):
    """Display the response to user"""
    st.markdown("---")
    st.markdown("### 💡 Answer")
    st.markdown(f"**{_short_text(response_data['response'], 320)}**")
    with st.expander("View full answer"):
        st.write(response_data['response'])
    
    if response_data.get('relevant_memories'):
        st.markdown("#### 📚 Sources Used")
        for i, memory in enumerate(response_data['relevant_memories'][:3]):
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**Source {i+1}:** {_short_text(memory['text'], 200)}")
                    st.caption(f"Added: {memory['created_at']}")
                with col2:
                    similarity_score = memory.get('similarity_score', 0)
                    st.metric("Relevance", f"{similarity_score:.2f}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔊 🔊 Play Answer", use_container_width=True):
            play_audio_response(response_data['response'], language)
    with col2:
        if st.button("📝 Add Related Memory", use_container_width=True):
            st.session_state['nav_page'] = 'add_memory'
            st.rerun()
    with col3:
        if st.button("🔄 Ask Another", use_container_width=True):
            st.rerun()


def play_audio_response(text, language):
    """Play audio response using TTS"""
    try:
        components = st.session_state.get('components', {})
        audio_processor = components.get('audio_processor')
        
        if audio_processor:
            with st.spinner("Generating speech..."):
                audio_data = audio_processor.text_to_speech(text, language)
                if audio_data:
                    st.audio(audio_data, format="audio/wav")
                else:
                    st.error("Could not generate speech")
        else:
            st.error("Audio processor not available")
            
    except Exception as e:
        st.error(f"Error generating speech: {e}")


def get_quick_questions(language):
    """Get quick question suggestions based on language"""
    questions = {
        'en': [
            "When is my next appointment?",
            "What medications do I take?",
            "Tell me about my family",
            "What did I do yesterday?",
            "Where do I live?"
        ],
        'hi': [
            "मेरा अगला अपॉइंटमेंट कब है?",
            "मैं कौन सी दवाएं लेता हूं?",
            "मेरे परिवार के बारे में बताएं",
            "मैंने कल क्या किया था?",
            "मैं कहाँ रहता हूं?"
        ],
        'ta': [
            "எனது அடுத்த சந்திப்பு எப்போது?",
            "நான் என்ன மருந்துகளை எடுத்துக்கொள்கிறேன்?",
            "எனது குடும்பத்தைப் பற்றி சொல்லுங்கள்",
            "நான் நேற்று என்ன செய்தேன்?",
            "நான் எங்கே வாழ்கிறேன்?"
        ]
    }
    
    return questions.get(language, questions['en'])


