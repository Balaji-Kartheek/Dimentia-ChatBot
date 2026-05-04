"""
LLM integration for Dementia Chatbot
Handles Gemini integration for RAG-based responses
"""
import logging
import os
from typing import List, Dict, Optional, Tuple
from google import genai
from google.genai import types
from datetime import datetime
import re
from dateutil.parser import parse as parse_datetime
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU

from config import (
    GEMINI_MODEL,
    GEMINI_API_KEY,
    FEATURE_ADAPTIVE_MODE,
    SUPPORTED_LANGUAGES,
    PERSON_QUERY_SIMILARITY_THRESHOLD,
    PERSON_QUERY_VECTOR_MIN_SIMILARITY,
    SIMILARITY_THRESHOLD,
)
from memory_system import MemorySystem

logger = logging.getLogger(__name__)

class LLMIntegration:
    def __init__(self, memory_system: MemorySystem):
        self.memory_system = memory_system
        self.model = GEMINI_MODEL
        self.api_key = GEMINI_API_KEY
        self.gemini_client = None
        self.model_candidates = [
            self.model,
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
        ]
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize Gemini model if API key is configured."""
        raw = os.getenv("GEMINI_API_KEY", "") or self.api_key or ""
        self.api_key = raw.strip().strip('"').strip("'")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set. LLM responses will use fallback mode.")
            return
        try:
            self.gemini_client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini model '{self.model}' initialized")
        except Exception as e:
            logger.error(f"Error initializing Gemini model '{self.model}': {e}")
    
    # RAG System
    def generate_response(self, query: str, user_context: str = "",
                         language: str = "en", max_tokens: int = 200, user_id: str = None) -> Dict:
        """Generate a response using RAG (Retrieval Augmented Generation)"""
        try:
            # Retrieve relevant memories
            relevant_memories = self.memory_system.search_memories(
                query, k=5, language=language, user_id=user_id
            )
            
            # If no results in selected language, retry without language filter
            if not relevant_memories:
                relevant_memories = self.memory_system.search_memories(
                    query, k=5, language=None, user_id=user_id
                )

            person_q = self._is_person_identity_query(query, language)
            best_score = (
                float(relevant_memories[0].get("similarity_score", 0.0)) if relevant_memories else 0.0
            )
            # Vector hits are always >= SIMILARITY_THRESHOLD; comparing only to 0.42 never escalated.
            person_memory_too_weak = not relevant_memories
            if relevant_memories:
                if best_score >= SIMILARITY_THRESHOLD - 1e-9:
                    person_memory_too_weak = best_score < PERSON_QUERY_VECTOR_MIN_SIMILARITY
                else:
                    person_memory_too_weak = best_score < PERSON_QUERY_SIMILARITY_THRESHOLD
            if person_q and person_memory_too_weak:
                escalate_ui = {
                    "en": (
                        "I could not find a reliable match in your saved memories for this person. "
                        "Your trusted contact has been alerted. When they reply by text, you can read it under Settings."
                    ),
                    "hi": (
                        "इस व्यक्ति के लिए आपकी सुरक्षित यादों में विश्वसनीय जानकारी नहीं मिली। "
                        "आपके विश्वसनीय संपर्क को सूचित किया गया है। उनके जवाब के लिए Settings देखें।"
                    ),
                    "ta": (
                        "இந்த நபரைப் பற்றி உங்கள் நினைவகத்தில் நம்பகமான தகவல் கிடைக்கவில்லை. "
                        "நம்பகமான தொடர்புக்கு அறிவிப்பு அனுப்பப்பட்டது. Settings-ல் பதிலைப் பார்க்கவும்."
                    ),
                }
                return {
                    "response": escalate_ui.get(language, escalate_ui["en"]),
                    "relevant_memories": relevant_memories[:3] if relevant_memories else [],
                    "context_used": "Person-identification query — memory match below threshold.",
                    "timestamp": datetime.now().isoformat(),
                    "escalate_to_trusted": True,
                }

            if not relevant_memories:
                no_memory_responses = {
                    "en": "I could not find any related memory for that question yet. Please add that information in Add Memory first.",
                    "hi": "मुझे इस प्रश्न के लिए कोई संबंधित याद नहीं मिली। कृपया पहले Add Memory में यह जानकारी जोड़ें।",
                    "ta": "இந்த கேள்விக்கு தொடர்புடைய நினைவுகள் கிடைக்கவில்லை. முதலில் Add Memory-ல் இந்த தகவலை சேர்க்கவும்."
                }
                return {
                    "response": no_memory_responses.get(language, no_memory_responses["en"]),
                    "relevant_memories": [],
                    "context_used": "No relevant memories found.",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Create context from retrieved memories
            context = self._create_context_from_memories(relevant_memories)
            
            # Try deterministic appointment resolution for "when" questions
            deterministic_answer = self._resolve_appointment_answer(query, relevant_memories, language)
            if deterministic_answer:
                return {
                    'response': deterministic_answer,
                    'relevant_memories': relevant_memories,
                    'context_used': context,
                    'timestamp': datetime.now().isoformat()
                }

            # If this is an appointment question and we found memories but none are upcoming,
            # return a clear direct answer instead of a generic fallback.
            no_upcoming_answer = self._create_no_upcoming_appointment_answer(query, relevant_memories, language)
            if no_upcoming_answer:
                return {
                    'response': no_upcoming_answer,
                    'relevant_memories': relevant_memories,
                    'context_used': context,
                    'timestamp': datetime.now().isoformat()
                }

            # Generate response using Gemini
            response = self._generate_with_llm(query, context, user_context, language)
            if FEATURE_ADAPTIVE_MODE and len(query.split()) <= 6:
                response = self._simplify_response(response, language)
            
            return {
                'response': response,
                'relevant_memories': relevant_memories,
                'context_used': context,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            err_ui = {
                "en": "I'm sorry, I'm having trouble processing your request right now. Please try again later.",
                "hi": "क्षमा करें, अभी आपके प्रश्न को संसाधित करने में समस्या हो रही है। कृपया थोड़ी देर बाद फिर कोशिश करें।",
                "ta": "மன்னிக்கவும், இப்போது உங்கள் கேள்வியை செயலாக்குவதில் சிக்கல் உள்ளது. பின்னர் முயற்சிக்கவும்.",
            }
            return {
                'response': err_ui.get(language, err_ui["en"]),
                'relevant_memories': [],
                'context_used': "",
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _create_context_from_memories(self, memories: List[Dict]) -> str:
        """Create context string from retrieved memories"""
        if not memories:
            return "No relevant memories found."

        context_parts = [f"CURRENT_DATETIME: {datetime.now().isoformat()}"]
        for i, memory in enumerate(memories, 1):
            memory_text = memory['text']
            timestamp = memory['timestamp']
            source = memory['source']
            similarity = memory.get('similarity_score', 0)
            caregiver = memory.get('caregiver_confirmed', False)

            context_parts.append(
                f"Memory {i} | caregiver_confirmed={caregiver} | similarity={similarity:.2f} | timestamp={timestamp} | source={source}:\n{memory_text}"
            )

        return "\n\n".join(context_parts)

    def _is_person_identity_query(self, query: str, language: str) -> bool:
        q = (query or "").strip()
        low = q.lower()
        patterns = [
            r"\bwho\s+is\b",
            r"\bwho's\b",
            r"\bwho\s+was\b",
            r"\bwho\s+are\b",
            r"\bdo\s+i\s+know\b",
            r"\bdid\s+i\s+know\b",
            r"\bdid\s+we\s+know\b",
            r"\bhave\s+i\s+met\b",
            r"\bhave\s+i\s+known\b",
            r"\bwhat\s+is\s+.+\s'name\b",
        ]
        if any(re.search(p, low) for p in patterns):
            return True
        if language == "hi" and ("कौन है" in q or "कौन था" in q or "कौन हैं" in q):
            return True
        if language == "ta" and ("யார்" in q and ("அது" in q or "இவர்" in q or "அவர்" in q)):
            return True
        return False

    def summarize_for_doctor_visit(
        self,
        recent_questions: List[str],
        memory_excerpts: List[str],
        language: str = "en",
    ) -> str:
        """Short clinician-oriented briefing from repeated questions + memory snippets."""
        q_block = "\n".join(f"- {(t or '')[:220]}" for t in (recent_questions or [])[:12])
        m_block = "\n".join(f"- {(x or '')[:240]}" for x in (memory_excerpts or [])[:6])
        prompt = (
            f"Language for output: {language}.\n"
            "You assist clinicians. From ONLY the data below, write a brief neutral summary for a doctor visit: "
            "observed repetition / confusion themes, relevant facts from memories, and suggested non-diagnostic follow-up. "
            "Do not state a medical diagnosis. Use short bullets.\n\n"
            f"Recent patient questions:\n{q_block or '(none)'}\n\n"
            f"Memory excerpts:\n{m_block or '(none)'}\n"
        )
        try:
            if not self.gemini_client:
                self._initialize_gemini()
            if not self.gemini_client:
                return (q_block + "\n" + m_block).strip() or "No summary (LLM offline)."
            for candidate_model in self.model_candidates:
                try:
                    response = self.gemini_client.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.15,
                            top_p=0.9,
                            max_output_tokens=500,
                        ),
                    )
                    text = getattr(response, "text", "") or ""
                    if text.strip():
                        self.model = candidate_model
                        return text.strip()
                except Exception as model_error:
                    logger.warning("Doctor summary model '%s' failed: %s", candidate_model, model_error)
                    continue
            return "Summary generation failed; see stored queries and memories."
        except Exception as e:
            logger.error("summarize_for_doctor_visit: %s", e)
            return f"Summary error: {e}"

    def _create_no_upcoming_appointment_answer(self, query: str, memories: List[Dict], language: str) -> Optional[str]:
        if not self._query_suggests_appointment_timing(query, language):
            return None
        if not memories:
            return None
        has_appointment_memory = any(
            self._memory_mentions_appointment(m.get("text") or "", language)[0]
            for m in memories
        )
        if not has_appointment_memory:
            return None

        messages = {
            "en": "I found appointment-related memories, but I cannot confirm an upcoming appointment date/time from them. Please add or update the latest appointment details.",
            "hi": "मुझे अपॉइंटमेंट से जुड़ी यादें मिलीं, लेकिन उनमें से अगली अपॉइंटमेंट की तारीख/समय पक्का नहीं हो पा रहा है। कृपया नवीनतम अपॉइंटमेंट विवरण जोड़ें या अपडेट करें।",
            "ta": "சந்திப்பு தொடர்பான நினைவுகள் உள்ளன, ஆனால் அடுத்த சந்திப்பின் தேதி/நேரத்தை உறுதிப்படுத்த முடியவில்லை. சமீபத்திய சந்திப்பு விவரங்களை புதுப்பிக்கவும்."
        }
        return messages.get(language, messages["en"])

    # ------------------------
    # Deterministic appointment resolver
    # ------------------------
    def _query_suggests_appointment_timing(self, query: str, language: str) -> bool:
        """Detect appointment/timing intent in English or selected UI language (e.g. Hindi)."""
        q = query or ""
        low = q.lower()
        en_kw = ["when", "time", "appointment", "dentist", "doctor", "visit", "schedule"]
        if any(k in low for k in en_kw):
            return True
        if language == "hi":
            hi_kw = ["कब", "समय", "अपॉइंटमेंट", "डॉक्टर", "दंत", "चिकित्सक", "मुलाकात", "मिलना"]
            return any(k in q for k in hi_kw)
        if language == "ta":
            ta_kw = ["எப்போது", "நேரம்", "சந்திப்பு", "டாக்டர்", "மருத்துவர்"]
            return any(k in q for k in ta_kw)
        return False

    def _memory_mentions_appointment(self, text: str, language: str) -> Tuple[bool, bool]:
        """Returns (mentions_appointment_or_visit, is_dentist_signal)."""
        raw = text or ""
        low = raw.lower()
        en_app = ["appointment", "dentist", "doctor", "visit", "clinic", "hospital"]
        if any(k in low for k in en_app):
            is_den = "dentist" in low or "दंत" in raw
            return True, is_den
        if language == "hi":
            hi_app = ["अपॉइंटमेंट", "डॉक्टर", "दंत", "चिकित्सक", "मुलाकात", "अस्पताल", "क्लिनिक"]
            if any(k in raw for k in hi_app):
                return True, ("दंत" in raw or "dentist" in low)
        if language == "ta":
            ta_app = ["சந்திப்பு", "டாக்டர்", "மருத்துவமனை", "மருத்துவர்"]
            if any(k in raw for k in ta_app):
                return True, ("பல்" in raw or "dentist" in low)
        return False, False

    def _resolve_appointment_answer(self, query: str, memories: List[Dict], language: str = "en") -> Optional[str]:
        """If the user asks about appointment timing, deterministically compute the next dentist/doctor appointment from memories.
        Returns a short answer string or None to fall back to LLM."""
        if not self._query_suggests_appointment_timing(query, language):
            return None

        now = datetime.now()
        candidates: List[Tuple[datetime, Dict, str]] = []  # (when, memory, note)

        for m in memories:
            text = m.get('text', '') or ''
            mentions, is_dentist = self._memory_mentions_appointment(text, language)
            if not mentions:
                continue

            low = text.lower()

            created_at = m.get("created_at") or m.get("timestamp")
            reference_now = now
            if created_at:
                try:
                    reference_now = parse_datetime(str(created_at))
                except Exception:
                    reference_now = now

            when_dt, note = self._extract_datetime_from_text(low + " " + (text or ""), reference_now)
            if when_dt is None:
                continue

            if when_dt < now:
                # Skip past appointments
                continue

            m['_is_dentist'] = is_dentist
            candidates.append((when_dt, m, note))

        if not candidates:
            return None

        # Rank: caregiver_confirmed > recency soonest > similarity
        def rank_key(item):
            when_dt, m, note = item
            dentist_priority = 1 if m.get('_is_dentist') else 0
            caregiver_priority = 1 if m.get('caregiver_confirmed') else 0
            similarity = float(m.get('similarity_score', 0.0))
            # Earlier future is better => invert timestamp for sorting descending by priorities, then ascending by date
            return (
                dentist_priority,
                caregiver_priority,
                round(similarity, 4),
                -when_dt.timestamp()
            )

        candidates.sort(key=rank_key, reverse=True)

        top_when, top_mem, top_note = candidates[0]

        # Detect conflicts: do we have another candidate on the same date but different time?
        same_date_conflict = False
        for when_dt, m, note in candidates[1:]:
            if when_dt.date() == top_when.date() and abs((when_dt - top_when).total_seconds()) >= 30 * 60:
                same_date_conflict = True
                break

        # Build deterministic answer
        when_str_date = top_when.strftime("%A, %B %d, %Y")
        when_str_time = top_when.strftime("%I:%M %p").lstrip('0')

        return self._format_deterministic_appointment_reply(
            language, same_date_conflict, when_str_date, when_str_time, top_mem
        )

    def _format_deterministic_appointment_reply(
        self,
        language: str,
        same_date_conflict: bool,
        when_str_date: str,
        when_str_time: str,
        top_mem: Dict,
    ) -> str:
        provider = None
        mtext = top_mem.get('text') or ''
        m_prov = re.search(r"(Dr\.?\s+[A-Za-z][A-Za-z\s]+)", mtext)
        if m_prov:
            provider = m_prov.group(1).strip()

        if same_date_conflict:
            msg = {
                "en": (
                    f"I found conflicting times for your appointment on {when_str_date}. "
                    f"One memory suggests {when_str_time}, but another shows a different time. "
                    "Could you confirm the exact time?"
                ),
                "hi": (
                    f"{when_str_date} को आपकी नियुक्ति के लिए समय में विरोधाभास लगता है। "
                    f"एक याद में {when_str_time} है, दूसरी में अलग समय। कृपया सही समय पुष्टि करें।"
                ),
                "ta": (
                    f"{when_str_date} அன்று நேரம் குறித்த முரண்பாடு உள்ளது. "
                    "சரியான நேரத்தை உறுதிப்படுத்தவும்."
                ),
            }
            return msg.get(language, msg["en"])

        iden = top_mem.get('_is_dentist')
        if provider and iden:
            pat = {
                "en": f"Your next dentist appointment with {provider} is on {when_str_date} at {when_str_time}.",
                "hi": f"आपकी अगली दंत चिकित्सक नियुक्ति {provider} के साथ {when_str_date} को {when_str_time} पर है।",
                "ta": f"உங்கள் அடுத்த பல் மருத்துவர் சந்திப்பு {provider} — {when_str_date}, {when_str_time}.",
            }
            return pat.get(language, pat["en"])
        if iden:
            pat = {
                "en": f"Your next dentist appointment is on {when_str_date} at {when_str_time}.",
                "hi": f"आपकी अगली दंत चिकित्सक नियुक्ति {when_str_date} को {when_str_time} पर है।",
                "ta": f"உங்கள் அடுத்த பல் சந்திப்பு {when_str_date}, {when_str_time}.",
            }
            return pat.get(language, pat["en"])
        if provider:
            pat = {
                "en": f"Your next appointment with {provider} is on {when_str_date} at {when_str_time}.",
                "hi": f"आपकी अगली नियुक्ति {provider} के साथ {when_str_date} को {when_str_time} पर है।",
                "ta": f"உங்கள் அடுத்த சந்திப்பு {provider} — {when_str_date}, {when_str_time}.",
            }
            return pat.get(language, pat["en"])
        pat = {
            "en": f"Your next appointment is on {when_str_date} at {when_str_time}.",
            "hi": f"आपकी अगली नियुक्ति {when_str_date} को {when_str_time} पर है।",
            "ta": f"உங்கள் அடுத்த சந்திப்பு {when_str_date}, {when_str_time}.",
        }
        return pat.get(language, pat["en"])

    def _extract_datetime_from_text(self, text: str, now: datetime) -> Tuple[Optional[datetime], str]:
        """Extract a future datetime from free text. Supports relative 'next <weekday>' and explicit times like '3 PM'."""
        # Relative weekday like "next Tuesday"
        rel = re.search(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text, re.I)
        target_date = None
        note = ""
        if rel:
            wd = rel.group(1).lower()
            weekday_map = {
                'monday': MO, 'tuesday': TU, 'wednesday': WE, 'thursday': TH,
                'friday': FR, 'saturday': SA, 'sunday': SU
            }
            target_date = (now + relativedelta(weekday=weekday_map[wd](+1))).date()
            note = "relative-weekday"

        # Time like 3 PM, 2:30pm, around 2PM
        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.I)
        target_time = None
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = time_match.group(3).lower()
            if hour == 12:
                hour = 0
            if meridiem == 'pm':
                hour += 12
            target_time = (hour, minute)

        # Try absolute parsing if no relative date detected
        if target_date is None:
            try:
                # fuzzy parsing to extract explicit dates like "October 16th"
                dt = parse_datetime(text, fuzzy=True, default=now)
                # If parser returns a datetime in the past with default now's time, consider date part
                target_date = dt.date()
                if dt.time() != datetime.min.time():
                    target_time = (dt.hour, dt.minute)
                if not note:
                    note = "absolute-date"
            except Exception:
                pass

        if target_date is None and target_time is None:
            return (None, note)

        # If we only have time, assume next occurrence today or next day
        if target_date is None and target_time is not None:
            cand = now.replace(hour=target_time[0], minute=target_time[1], second=0, microsecond=0)
            if cand <= now:
                cand = cand + relativedelta(days=1)
            return (cand, note or "time-only")

        # If we have date but no time, set a neutral 09:00 for ordering, caller will state uncertainty if needed
        if target_date is not None and target_time is None:
            cand = datetime.combine(target_date, datetime.min.time()).replace(hour=9)
            return (cand, note or "date-only")

        # Both date and time
        if target_date is not None and target_time is not None:
            cand = datetime.combine(target_date, datetime.min.time()).replace(hour=target_time[0], minute=target_time[1])
            return (cand, note or "date-time")

        return (None, note)
    
    def _generate_with_llm(self, query: str, context: str, user_context: str, language: str) -> str:
        """Generate response using Gemini API."""
        try:
            if not self.gemini_client:
                # Retry initialization in case env key was set after app start
                self._initialize_gemini()
                if not self.gemini_client:
                    return self._create_fallback_response(query, context, language)

            # Create system prompt
            system_prompt = self._create_system_prompt(language)
            
            # Create user prompt with context
            user_prompt = self._create_user_prompt(query, context, user_context, language)

            for candidate_model in self.model_candidates:
                try:
                    response = self.gemini_client.models.generate_content(
                        model=candidate_model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.2,
                            top_p=0.9,
                            max_output_tokens=220,
                        ),
                    )
                    text = getattr(response, "text", "") or ""
                    if text.strip():
                        self.model = candidate_model
                        return text.strip()
                except Exception as model_error:
                    logger.warning(f"Gemini model '{candidate_model}' failed: {model_error}")
                    continue

            return self._create_fallback_response(query, context, language)
            
        except Exception as e:
            logger.error(f"Error with Gemini generation: {e}")
            # Fallback response
            return self._create_fallback_response(query, context, language)
    
    def _create_system_prompt(self, language: str) -> str:
        """Create system prompt based on language"""
        prompts = {
            'en': """You are a helpful memory assistant for people with dementia.

Answer ONLY using facts present in the provided memories. If there is any conflict between memories, prefer entries with caregiver_confirmed=true. If conflicts remain or details are missing (date or time), say you are unsure and ask to confirm. Never invent names, dates, or times.

When answering time-sensitive questions (like appointments), interpret relative phrases (e.g., "next Tuesday") using CURRENT_DATETIME from the context. If interpreting would be ambiguous, ask a brief clarifying question.

Guidelines:
- Be patient, gentle, and reassuring
- Use simple, clear language
- State uncertainty explicitly when needed
- Provide the most precise answer available, citing exact date/time if present
- If no relevant memory exists, say so and suggest adding it""",

            'hi': """आप डिमेंशिया से पीड़ित लोगों के लिए एक सहायक स्मृति सहायक हैं।

केवल प्रदान की गई यादों में मौजूद तथ्यों का उपयोग करें। यादों के बीच विरोध हो तो caregiver_confirmed=true वाली प्रविष्टियों को प्राथमिकता दें। तिथि या समय गायब हो तो अस्पष्टता स्वीकार करें और पुष्टि माँगें। नाम, तारीख या समय गढ़ें नहीं।

दिशानिर्देश:
- धैर्यवान, कोमल और आश्वस्त रहें; सरल हिंदी में उत्तर दें
- आपका हर उत्तर पूरी तरह हिंदी (देवनागरी) में हो — अंग्रेज़ी वाक्य न लिखें
- केवल संदर्भ में जो दिखे वही बताएँ; अनुमान न लगाएँ""",

            'ta': """நீங்கள் டிமென்ஷியாவால் பாதிக்கப்பட்டவர்களுக்கு உதவும் நினைவக உதவியாளர்.

வழங்கப்பட்ட நினைவுகளில் உள்ள தகவல்களை மட்டுமே பயன்படுத்தவும். முரண்பாடுகளில் caregiver_confirmed=true உள்ளவற்றை முன்னிலைப்படுத்தவும். தேதி/நேரம் இல்லையெனில் தெளிவுபடுத்த கேளுங்கள்.

வழிகாட்டுதல்கள்:
- பொறுமையாகவும் தெளிவாகவும் பதிலளிக்கவும்
- உங்கள் முழு பதிலும் தமிழில் மட்டுமே இருக்க வேண்டும்
- ஊகிக்காதீர்கள்; சூழலில் இல்லாத விவரங்களைச் சேர்க்காதீர்கள்"""
        }
        
        base = prompts.get(language)
        if base is None:
            base = prompts["en"]
            extra = self._system_prompt_extra_for_language(language)
            return base + "\n\n" + extra
        return base

    def _system_prompt_extra_for_language(self, language: str) -> str:
        """For locales without a full native system prompt, pin output language."""
        extra = {
            "tel": "The user's selected UI language is Telugu. Write every sentence of your answer in Telugu.",
            "es": "The user's selected UI language is Spanish. Write every sentence of your answer in Spanish.",
            "fr": "The user's selected UI language is French. Write every sentence of your answer in French.",
            "de": "The user's selected UI language is German. Write every sentence of your answer in German.",
        }
        return extra.get(language, "Match the user's selected UI language for every word of your answer.")

    def _mandatory_answer_language_line(self, language: str) -> str:
        lines = {
            "en": "LANGUAGE: Write your entire answer in English only.",
            "hi": "LANGUAGE: अपना पूरा उत्तर केवल हिंदी में देवनागरी लिपि में लिखें। अंग्रेज़ी वाक्यों का उपयोग न करें।",
            "ta": "LANGUAGE: Write your entire answer in Tamil only.",
            "tel": "LANGUAGE: Write your entire answer in Telugu only.",
            "es": "LANGUAGE: Write your entire answer in Spanish only.",
            "fr": "LANGUAGE: Write your entire answer in French only.",
            "de": "LANGUAGE: Write your entire answer in German only.",
        }
        return lines.get(language, lines["en"])
    
    def _create_user_prompt(self, query: str, context: str, user_context: str, language: str) -> str:
        """Create user prompt with context"""
        if user_context:
            user_context_part = f"User context: {user_context}\n\n"
        else:
            user_context_part = ""
        
        lang_line = self._mandatory_answer_language_line(language)
        return f"""{user_context_part}Relevant memories:
{context}

Question: {query}

Instructions for answering:
- Use ONLY information present in memories. Do not guess.
- If multiple memories conflict, choose caregiver-confirmed entries; otherwise say you're unsure and ask for confirmation.
- If the question is about dates/times, resolve relative dates using CURRENT_DATETIME in context.
- If either date or time is missing, explicitly state what is missing and ask to confirm.
- Keep answers short and clear for cognitive accessibility.
- {lang_line}"""

    def _simplify_response(self, response: str, language: str) -> str:
        if language != "en":
            return response
        cleaned = " ".join((response or "").split())
        if len(cleaned) <= 220:
            return cleaned
        return cleaned[:220].rstrip() + " Please ask me if you want more details."

    def summarize_memory_notes_brief(
        self,
        *,
        language: str,
        memories: List[Dict],
        focus: str = "recap",
    ) -> Optional[str]:
        """Turn raw notes into neutral bullets. focus='recap' for general summary; 'today' for today's tasks list."""
        if not memories:
            return None
        try:
            self._initialize_gemini()
            if not self.gemini_client:
                return None

            lang_name = SUPPORTED_LANGUAGES.get(language, language)
            lines = []
            for m in memories:
                tx = (m.get("text") or "").strip()
                if tx:
                    lines.append(tx)
            notes_block = "\n".join(f"• {ln}" for ln in lines)

            if focus == "today":
                job_block = f"""These items are stored as **today's** dated notes (appointments, visits, tasks).

RAW NOTES:
{notes_block}

Your job: write **what to cover today** — short, actionable bullets (neutral calendar style), **not** a copy of their words.

Output rules:
- **Only** lines starting with "- ". No title, preamble, or closing.
- **Rewrite** each item: who/what/when if present. Avoid "I have", "I think", "today I" — use forms like "Appointment with … around …", "Visit planned …".
- Merge duplicates. **2–8 bullets**; **≤ 22 words** each unless a name requires more.
- **No new facts** — only what is in the notes.
- Language: **{lang_name}** (code {language}).
- {self._mandatory_answer_language_line(language)}"""
            else:
                job_block = f"""You help someone with memory difficulty. Below are **raw notes** they saved (may be messy or first-person).

RAW NOTES:
{notes_block}

Your job: write a **brief factual summary**, not a copy of their words.

Output rules:
- **Only** lines that start with "- " (markdown bullets). No title, no preamble, no closing.
- **Rewrite** every fact in neutral, calm language (like a short care diary or calendar digest). Do **not** mirror their wording, slang, or sentence openings (avoid "I have", "I think", "I need", "I visited" — use forms like "Visit to … noted", "Appointment regarding …", "Plan: …").
- Merge duplicate or overlapping facts into one bullet when clear.
- About **3–8 bullets** total; each bullet **≤ 20 words** unless a name/place requires more.
- **No new facts** — only what appears in the notes. If a time or place is vague, keep it vague.
- Language for all bullets: **{lang_name}** (code {language}).
- {self._mandatory_answer_language_line(language)}"""

            user_prompt = job_block

            sys_instr = (
                "Output only markdown bullet lines beginning with '- '. "
                "Never paste the user's sentences verbatim."
            )

            for candidate_model in self.model_candidates:
                try:
                    response = self.gemini_client.models.generate_content(
                        model=candidate_model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=sys_instr,
                            temperature=0.15,
                            top_p=0.85,
                            max_output_tokens=360,
                        ),
                    )
                    text = getattr(response, "text", "") or ""
                    if not (text or "").strip():
                        cand = getattr(response, "candidates", None) or []
                        if cand:
                            parts = getattr(getattr(cand[0], "content", None), "parts", None) or []
                            chunks = []
                            for p in parts:
                                t0 = getattr(p, "text", None)
                                if t0:
                                    chunks.append(t0)
                            text = "\n".join(chunks)
                    text = text.strip()
                    if text:
                        self.model = candidate_model
                        # Drop accidental headings / code fences
                        out_lines = []
                        for ln in text.splitlines():
                            s = ln.strip()
                            if not s:
                                continue
                            if s.startswith("```"):
                                continue
                            if s.startswith("#"):
                                continue
                            if not s.startswith("- "):
                                s = "- " + s.lstrip("-• ").strip()
                            out_lines.append(s)
                        return "\n".join(out_lines) if out_lines else None
                except Exception as model_error:
                    logger.warning(f"Memory brief model '{candidate_model}' failed: {model_error}")
                    continue
            return None
        except Exception as e:
            logger.error(f"summarize_memory_notes_brief error: {e}")
            return None

    def generate_day_start_summary(
        self,
        *,
        language: str,
        user_display_name: str,
        today_iso: str,
        summary_memories: List[Dict],
        today_memories: List[Dict],
    ) -> Optional[str]:
        """Morning brief: bullet Summary (prior notes) + What need to cover (today)."""
        try:
            if not self.gemini_client:
                self._initialize_gemini()
            if not self.gemini_client:
                return None

            lang_name = SUPPORTED_LANGUAGES.get(language, language)
            now_s = datetime.now().strftime("%Y-%m-%d %H:%M")

            def block(title: str, rows: List[Dict]) -> str:
                if not rows:
                    return f"{title}\n(none)"
                lines = []
                for i, m in enumerate(rows, 1):
                    tx = (m.get("text") or "").strip()
                    lines.append(f"  {i}. {tx}")
                return f"{title}\n" + "\n".join(lines)

            sum_block = block("SUMMARY_CONTEXT (saved memories to recap; not today's dated tasks below)", summary_memories)
            today_block = block("TODAY_TASKS_CONTEXT (dated for today only)", today_memories)

            user_prompt = f"""Write a short morning brief for a memory assistant user. Tone: calm, clear, respectful.

User name: {user_display_name}
Now: {now_s}
Today date: {today_iso}
Output language: {lang_name} (code {language})

{sum_block}

{today_block}

Output Markdown with EXACTLY these headings (###):

### Good morning
Exactly one short line (greeting only, no bullets).

### Summary
ONLY bullet lines starting with "- ". **Rewrite** facts from SUMMARY_CONTEXT in neutral, factual language (short diary style). **Do not** repeat the user's original phrasing or first-person voice ("I have", "I think", "I need"). Paraphrase every item. Merge duplicates. Max ~18 words per bullet. If SUMMARY_CONTEXT is empty, one bullet that there are no earlier notes yet (in {lang_name}).

### What need to cover
ONLY bullet lines starting with "- ". Each bullet: one concrete task or appointment for today from TODAY_TASKS_CONTEXT. If that context is empty, one bullet that nothing with today's date is stored yet (in {lang_name}).

Rules:
- Do not invent facts, places, or times.
- Do not use "Yesterday" / "Today" as section titles — use the three headings above exactly.
- {self._mandatory_answer_language_line(language)}"""

            sys_instr = "Output only the Markdown brief. No extra commentary."

            for candidate_model in self.model_candidates:
                try:
                    response = self.gemini_client.models.generate_content(
                        model=candidate_model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=sys_instr,
                            temperature=0.2,
                            top_p=0.9,
                            max_output_tokens=480,
                        ),
                    )
                    text = getattr(response, "text", "") or ""
                    if text.strip():
                        self.model = candidate_model
                        return text.strip()
                except Exception as model_error:
                    logger.warning(f"Day-start model '{candidate_model}' failed: {model_error}")
                    continue
            return None
        except Exception as e:
            logger.error(f"Day-start summary error: {e}")
            return None

    def _create_fallback_response(self, query: str, context: str, language: str) -> str:
        """Create fallback response when Gemini is not available"""
        fallback_responses = {
            'en': "I found some related information in your memories, but I'm having trouble generating a complete response right now. Here's what I found: " + context[:200] + "...",
            'hi': "मुझे आपकी यादों में कुछ संबंधित जानकारी मिली, लेकिन अभी पूर्ण प्रतिक्रिया देने में समस्या हो रही है। यहाँ मुझे जो मिला: " + context[:200] + "...",
            'ta': "உங்கள் நினைவுகளில் சில தொடர்புடைய தகவல்கள் கிடைத்தன, ஆனால் இப்போது முழுமையான பதில் தருவதில் சிக்கல் உள்ளது. இங்கே எனக்குக் கிடைத்தது: " + context[:200] + "..."
        }
        
        return fallback_responses.get(language, fallback_responses['en'])
    
    def test_connection(self) -> bool:
        """Test if Gemini is configured and model initialized."""
        return bool(self.gemini_client)
    
    def get_available_models(self) -> List[str]:
        """Return configured Gemini model name."""
        return [self.model] if self.model else []
