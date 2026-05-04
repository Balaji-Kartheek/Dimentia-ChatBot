"""
Support page: A friendly help center for users and caregivers.
Features:
- Select preferred language (applies only here)
- Upload saved memories (CSV/JSON/TXT) and PDFs
- Prepare a temporary knowledge space from uploads
- Ask questions, preview info used, and get clear answers
"""
import streamlit as st
from typing import List, Dict
import pandas as pd
import io
from dataclasses import dataclass
import numpy as np

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

from config import SessionKeys, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from i18n import t


def _short_text(text: str, limit: int = 220) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


@dataclass
class SupportIndex:
    texts: List[str]
    vectors: np.ndarray  # shape: (N, D), L2-normalized
    language: str


def _get_or_create_model():
    # Lazy import to avoid loading model unless the Support page is used
    from sentence_transformers import SentenceTransformer
    model = st.session_state.get("_support_embed_model")
    if model is None:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        st.session_state["_support_embed_model"] = model
    return model


def _normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8
    return vecs / norms


def _embed_texts(texts: List[str]) -> np.ndarray:
    model = _get_or_create_model()
    vecs = model.encode(texts, convert_to_numpy=True).astype("float32")
    return _normalize(vecs)


def _build_index(chunks: List[str], language: str) -> SupportIndex:
    vectors = _embed_texts(chunks)
    return SupportIndex(texts=chunks, vectors=vectors, language=language)


def _chunk_text(text: str, max_chars: int = 800) -> List[str]:
    if not text:
        return []
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks


def _read_pdf(file) -> str:
    if PdfReader is None:
        st.error("PDF support not available. Please install pypdf.")
        return ""
    try:
        reader = PdfReader(file)
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n\n".join(pages)
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return ""


def _read_memories_upload(file) -> List[str]:
    name = file.name.lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(file)
            cols = [c for c in df.columns if c.lower() in ("text", "memory", "content", "note")] or [df.columns[0]]
            return [str(x) for x in df[cols[0]].dropna().astype(str).tolist()]
        if name.endswith(".json"):
            data = file.read()
            try:
                import json
                obj = json.loads(data)
            except Exception:
                obj = []
            texts: List[str] = []
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        for key in ("text", "memory", "content", "note"):
                            if key in item and item[key]:
                                texts.append(str(item[key]))
                                break
                    elif isinstance(item, str):
                        texts.append(item)
            elif isinstance(obj, dict):
                for key in ("text", "memory", "content", "note"):
                    if key in obj and obj[key]:
                        texts.append(str(obj[key]))
            return texts
        # Fallback: treat as plaintext
        content = file.read()
        if isinstance(content, bytes):
            content = content.decode(errors="ignore")
        return [content]
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return []


def render_support_page():
    lang_ui = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    st.markdown(t(lang_ui, "support.title"))
    st.caption(t(lang_ui, "support.caption"))

    components = st.session_state.get('components', {})
    if not components:
        st.error(t(lang_ui, "common.system_not_init"))
        return

    llm_integration = components['llm_integration']
    db = components['db']
    username = st.session_state.get(SessionKeys.USERNAME, "")

    st.markdown(t(lang_ui, "support.lang"))
    current_support_lang = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)
    keys = list(SUPPORTED_LANGUAGES.keys())
    idx = keys.index(current_support_lang) if current_support_lang in keys else 0
    selected_support_lang = st.selectbox(
        t(lang_ui, "support.lang_preferred"),
        options=keys,
        format_func=lambda x: SUPPORTED_LANGUAGES[x],
        index=idx,
        key="support_lang_selectbox",
    )
    if st.button(t(lang_ui, "support.lang_submit"), key="support_submit_language"):
        st.session_state[SessionKeys.SELECTED_LANGUAGE] = selected_support_lang
        st.session_state["support_language"] = selected_support_lang
        st.success(
            t(selected_support_lang, "support.lang_ok", name=SUPPORTED_LANGUAGES[selected_support_lang])
        )
        st.rerun()

    lang_code = st.session_state.get(SessionKeys.SELECTED_LANGUAGE, DEFAULT_LANGUAGE)

    st.markdown("#### Add information")
    col_mem, col_pdf = st.columns(2)
    with col_mem:
        mem_files = st.file_uploader("Upload saved memories (CSV/JSON/TXT)", type=["csv", "json", "txt"], accept_multiple_files=True)
    with col_pdf:
        pdf_files = st.file_uploader("Upload PDFs (optional)", type=["pdf"], accept_multiple_files=True)

    if st.button("Prepare", type="primary"):
        with st.spinner("Preparing your information..."):
            texts: List[str] = []
            # Memories
            for f in mem_files or []:
                texts.extend(_read_memories_upload(f))
            # PDFs
            for f in pdf_files or []:
                texts.append(_read_pdf(f))
            # Chunk
            chunks: List[str] = []
            for txt in texts:
                chunks.extend(_chunk_text(txt))
            # Build index
            if chunks:
                st.session_state["support_index"] = _build_index(chunks, lang_code)
                st.success(f"Prepared {len(chunks)} chunks for search.")
            else:
                st.info("No usable text found in uploads.")

    # Ask
    st.markdown("#### Ask a question")
    st.caption("Type your question and click Submit Question.")
    question = st.text_input("Your question", placeholder={
        'en': "Example: When is my next appointment?",
        'hi': "उदाहरण: मेरा अगला अपॉइंटमेंट कब है?",
        'ta': "உதாரணம்: எனது அடுத்த சந்திப்பு எப்போது?",
    }.get(lang_code, "Example: When is my next appointment?"))

    idx: SupportIndex = st.session_state.get("support_index")
    col_prev, col_ans, col_clear = st.columns(3)

    def _retrieve(q: str, k: int = 5) -> List[Dict]:
        if not idx or not q.strip():
            return []
        qvec = _embed_texts([q])[0]
        sims = np.dot(idx.vectors, qvec)
        order = np.argsort(-sims)
        results = []
        for i in order[:k]:
            results.append({
                'text': idx.texts[i],
                'similarity_score': float(sims[i])
            })
        return results

    with col_prev:
        if st.button("Preview info", use_container_width=True):
            if not question.strip():
                st.warning("Please enter a question first.")
            else:
                with st.spinner("Searching your uploaded information..."):
                    results = _retrieve(question, k=5)
                    if not results:
                        st.info("Nothing relevant found yet. Try uploading files and clicking Prepare.")
                    for i, m in enumerate(results, 1):
                        st.markdown(f"**Source {i}**")
                        st.caption(f"Relevance: {m['similarity_score']:.2f}")
                        st.write(_short_text(m['text'], 260))
                        if len((m.get("text") or "")) > 260:
                            with st.expander(f"View full source {i}"):
                                st.write(m["text"])

    with col_ans:
        if st.button("✅ Submit Question", type="primary", use_container_width=True):
            if not question.strip():
                st.warning("Please enter a question first.")
            else:
                with st.spinner("Preparing answer..."):
                    results = _retrieve(question, k=5)
                    # Build simple context section
                    if results:
                        context = "CURRENT_DATETIME: "
                        from datetime import datetime as _dt
                        context += _dt.now().isoformat() + "\n\n"
                        for i, m in enumerate(results, 1):
                            context += f"Source {i} | similarity={m['similarity_score']:.2f}:\n{m['text']}\n\n"
                    else:
                        context = "No relevant information found."

                    try:
                        # Use existing LLM integration to generate grounded answer
                        resp_text = llm_integration._generate_with_llm(
                            question,
                            context,
                            user_context=f"User: {username}, Language: {lang_code}",
                            language=lang_code,
                        )
                        st.success("Answer ready")
                        st.markdown(f"**{_short_text(resp_text, 320)}**")
                        with st.expander("View full answer"):
                            st.write(resp_text)
                        if results:
                            st.markdown("#### Sources used")
                            for i, m in enumerate(results[:3]):
                                st.caption(f"{i+1}. {_short_text(m['text'], 160)}")
                        try:
                            uid = st.session_state.get(SessionKeys.USER_ID)
                            db.log_activity(uid or username, "support_query", None, f"Q: {question[:80]}...")
                        except Exception:
                            pass
                    except Exception as e:
                        st.error(f"Error generating answer: {e}")

    with col_clear:
        if st.button("🧹 Clear", use_container_width=True):
            st.rerun()


