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

from config import GEMINI_MODEL, GEMINI_API_KEY
from memory_system import MemorySystem

logger = logging.getLogger(__name__)

class LLMIntegration:
    def __init__(self, memory_system: MemorySystem):
        self.memory_system = memory_system
        self.model = GEMINI_MODEL
        self.api_key = GEMINI_API_KEY
        self.gemini_client = None
        self.model_candidates = [self.model, "gemini-2.5-flash", "gemini-1.5-flash"]
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize Gemini model if API key is configured."""
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
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
                         language: str = "en", max_tokens: int = 200) -> Dict:
        """Generate a response using RAG (Retrieval Augmented Generation)"""
        try:
            # Retrieve relevant memories
            relevant_memories = self.memory_system.search_memories(
                query, k=5, language=language
            )
            
            # If no results in selected language, retry without language filter
            if not relevant_memories:
                relevant_memories = self.memory_system.search_memories(
                    query, k=5, language=None
                )

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
            deterministic_answer = self._resolve_appointment_answer(query, relevant_memories)
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
            
            return {
                'response': response,
                'relevant_memories': relevant_memories,
                'context_used': context,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                'response': "I'm sorry, I'm having trouble processing your request right now. Please try again later.",
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

    def _create_no_upcoming_appointment_answer(self, query: str, memories: List[Dict], language: str) -> Optional[str]:
        q = (query or "").lower()
        if not any(kw in q for kw in ["when", "time", "appointment", "dentist", "doctor"]):
            return None
        if not memories:
            return None
        has_appointment_memory = any(
            any(k in (m.get("text", "") or "").lower() for k in ["appointment", "dentist", "doctor", "visit"])
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
    def _resolve_appointment_answer(self, query: str, memories: List[Dict]) -> Optional[str]:
        """If the user asks about appointment timing, deterministically compute the next dentist/doctor appointment from memories.
        Returns a short answer string or None to fall back to LLM."""
        q = (query or "").lower()
        if not any(kw in q for kw in ["when", "time", "appointment", "dentist", "doctor"]):
            return None

        now = datetime.now()
        candidates: List[Tuple[datetime, Dict, str]] = []  # (when, memory, note)

        for m in memories:
            text = m.get('text', '') or ''
            low = text.lower()
            if not any(k in low for k in ["appointment", "dentist", "doctor", "visit"]):
                continue

            # Prefer entries that actually mention dentist
            is_dentist = ("dentist" in low)

            created_at = m.get("created_at") or m.get("timestamp")
            reference_now = now
            if created_at:
                try:
                    reference_now = parse_datetime(str(created_at))
                except Exception:
                    reference_now = now

            when_dt, note = self._extract_datetime_from_text(low, reference_now)
            if when_dt is None:
                continue

            if when_dt < now:
                # Skip past appointments
                continue

            # Attach soft preference signals
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

        if same_date_conflict:
            return (
                f"I found conflicting times for your appointment on {when_str_date}. "
                f"One memory suggests {when_str_time}, but another shows a different time. "
                f"Could you confirm the exact time?"
            )

        # Include provider if the memory mentions a name like Dr.
        provider = None
        mtext = (top_mem.get('text') or '')
        m_prov = re.search(r"(Dr\.?\s+[A-Z][a-z]+)", mtext)
        if m_prov:
            provider = m_prov.group(1)

        if provider and top_mem.get('_is_dentist'):
            return f"Your next dentist appointment with {provider} is on {when_str_date} at {when_str_time}."
        if top_mem.get('_is_dentist'):
            return f"Your next dentist appointment is on {when_str_date} at {when_str_time}."
        if provider:
            return f"Your next appointment with {provider} is on {when_str_date} at {when_str_time}."
        return f"Your next appointment is on {when_str_date} at {when_str_time}."

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

            'hi': """आप डिमेंशिया से पीड़ित लोगों के लिए एक सहायक स्मृति सहायक हैं। आप उन्हें दवा के समय, अपॉइंटमेंट और परिवार के विवरण जैसी व्यक्तिगत जानकारी याद करने में मदद करते हैं।

दिशानिर्देश:
- धैर्यवान, कोमल और आश्वस्त रहें
- सरल, स्पष्ट भाषा का उपयोग करें
- केवल वही जानकारी दें जो आप प्रदान किए गए संदर्भ में पा सकते हैं
- यदि आप कुछ नहीं जानते, तो ईमानदारी से कहें
- हमेशा प्रोत्साहित और सहायक रहें""",

            'ta': """நீங்கள் டிமென்ஷியாவால் பாதிக்கப்பட்டவர்களுக்கு உதவும் நினைவக உதவியாளர். மருந்து அட்டவணை, சந்திப்புகள் மற்றும் குடும்ப விவரங்கள் போன்ற தனிப்பட்ட தகவல்களை நினைவுகூர உதவுங்கள்.

வழிகாட்டுதல்கள்:
- பொறுமையாக, மென்மையாக, உறுதியளிக்கும் வகையில் இருங்கள்
- எளிய, தெளிவான மொழியைப் பயன்படுத்துங்கள்
- வழங்கப்பட்ட சூழலில் காணக்கூடிய தகவல்களை மட்டுமே வழங்குங்கள்
- எதையாவது தெரியாவிட்டால், நேர்மையாகச் சொல்லுங்கள்
- எப்போதும் ஊக்கமளிக்கும் மற்றும் உதவி செய்யும் வகையில் இருங்கள்"""
        }
        
        return prompts.get(language, prompts['en'])
    
    def _create_user_prompt(self, query: str, context: str, user_context: str, language: str) -> str:
        """Create user prompt with context"""
        if user_context:
            user_context_part = f"User context: {user_context}\n\n"
        else:
            user_context_part = ""
        
        return f"""{user_context_part}Relevant memories:
{context}

Question: {query}

Instructions for answering:
- Use ONLY information present in memories. Do not guess.
- If multiple memories conflict, choose caregiver-confirmed entries; otherwise say you're unsure and ask for confirmation.
- If the question is about dates/times, resolve relative dates using CURRENT_DATETIME in context.
- If either date or time is missing, explicitly state what is missing and ask to confirm."""
    
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
