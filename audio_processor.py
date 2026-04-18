"""
Audio processing for Dementia Chatbot
Handles speech-to-text and text-to-speech functionality
"""
import speech_recognition as sr
import pyttsx3
import soundfile as sf
import numpy as np
import tempfile
import os
from typing import Optional, Tuple
import logging
from pathlib import Path
import io

from config import AUDIO_DIR, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.tts_engine = None
        self.tts_loaded = False
        # Load TTS engine on initialization
        self._load_tts()
    
    def _setup_recognizer(self):
        """Setup speech recognition with optimal settings"""
        try:
            # Configure recognizer for better accuracy
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.dynamic_energy_adjustment_damping = 0.15
            self.recognizer.dynamic_energy_ratio = 1.5
            self.recognizer.pause_threshold = 0.8
            self.recognizer.operation_timeout = None
            self.recognizer.phrase_threshold = 0.3
            self.recognizer.non_speaking_duration = 0.8
            logger.info("Speech recognition configured successfully")
        except Exception as e:
            logger.error(f"Error configuring speech recognition: {e}")
    
    def _load_tts(self):
        """Load TTS engine"""
        if self.tts_loaded:
            return
            
        try:
            self.tts_engine = pyttsx3.init()
            self._configure_tts()
            self.tts_loaded = True
            logger.info("TTS engine initialized successfully")
        except Exception as e:
            logger.error(f"Error loading TTS engine: {e}")
    
    def load_models(self):
        """Setup speech recognition and TTS (for backward compatibility)"""
        self._setup_recognizer()
        self._load_tts()
    
    def _configure_tts(self):
        """Configure TTS engine settings"""
        if self.tts_engine:
            # Set speech rate (words per minute)
            self.tts_engine.setProperty('rate', 150)
            
            # Set volume (0.0 to 1.0)
            self.tts_engine.setProperty('volume', 0.8)
            
            # Try to set voice (may not work on all systems)
            voices = self.tts_engine.getProperty('voices')
            if voices:
                # Prefer female voice if available
                for voice in voices:
                    if 'female' in voice.name.lower() or 'woman' in voice.name.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        break
    
    def transcribe_audio(self, audio_data: bytes, language: str = None) -> str:
        """Transcribe audio data to text using SpeechRecognition"""
        try:
            # Save audio data to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # Load audio file with SpeechRecognition
            with sr.AudioFile(temp_file_path) as source:
                audio = self.recognizer.record(source)
            
            # Try Google Speech Recognition first
            try:
                if language and language in SUPPORTED_LANGUAGES:
                    text = self.recognizer.recognize_google(audio, language=language)
                else:
                    text = self.recognizer.recognize_google(audio)
                logger.info(f"Audio transcribed successfully using Google: {len(text)} characters")
                return text.strip()
            except sr.UnknownValueError:
                logger.warning("Google Speech Recognition could not understand audio")
                return ""
            except sr.RequestError as e:
                logger.warning(f"Could not request results from Google Speech Recognition: {e}")
                # Fallback to offline recognition
                try:
                    if language and language in SUPPORTED_LANGUAGES:
                        text = self.recognizer.recognize_sphinx(audio, language=language)
                    else:
                        text = self.recognizer.recognize_sphinx(audio)
                    logger.info(f"Audio transcribed successfully using Sphinx: {len(text)} characters")
                    return text.strip()
                except sr.UnknownValueError:
                    logger.warning("Sphinx could not understand audio")
                    return ""
                except sr.RequestError as e:
                    logger.error(f"Sphinx error: {e}")
                    return ""
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return ""
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass

    def _map_language_code(self, language: str) -> str:
        mapping = {
            "en": "en-US",
            "hi": "hi-IN",
            "ta": "ta-IN",
            "tel": "te-IN",
            "es": "es-ES",
            "fr": "fr-FR",
            "de": "de-DE",
        }
        return mapping.get((language or "en").lower(), "en-US")
    
    def text_to_speech(self, text: str, language: str = "en") -> Optional[bytes]:
        """Convert text to speech and return audio data"""
        if not self.tts_engine:
            raise Exception("TTS engine not initialized")
        
        try:
            # Configure language-specific settings if needed
            self._set_tts_language(language)
            
            # Generate speech
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            # Save speech to temporary file
            self.tts_engine.save_to_file(text, temp_file_path)
            self.tts_engine.runAndWait()
            
            # Read the generated audio file
            with open(temp_file_path, 'rb') as f:
                audio_data = f.read()
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            return None
    
    def _set_tts_language(self, language: str):
        """Set TTS language (basic implementation)"""
        # This is a simplified implementation
        # For better language support, consider using Coqui TTS or other libraries
        
        voices = self.tts_engine.getProperty('voices')
        if voices:
            # Try to find a voice that matches the language
            target_language = language.lower()
            
            for voice in voices:
                voice_lang = getattr(voice, 'languages', [])
                if target_language in voice_lang or target_language in str(voice_lang).lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    return
        
        # Fallback to default voice
        logger.warning(f"Could not find voice for language: {language}")
    
    def process_streamlit_audio(self, audio_bytes: bytes) -> str:
        """Process audio from Streamlit audio recorder using SpeechRecognition"""
        try:
            logger.info("Processing audio with SpeechRecognition...")
            
            # Validate audio bytes
            if not audio_bytes or len(audio_bytes) < 1000:  # Minimum size check
                logger.warning("Audio data too small or empty")
                return ""
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name
            
            try:
                # Load audio file with SpeechRecognition
                with sr.AudioFile(temp_file_path) as source:
                    audio = self.recognizer.record(source)
                
                # Try Google Speech Recognition first (online, more accurate)
                try:
                    text = self.recognizer.recognize_google(audio, language=self._map_language_code("en"))
                    logger.info(f"Transcription completed using Google: '{text[:50]}...'")
                    return text.strip()
                except sr.UnknownValueError:
                    logger.warning("Google Speech Recognition could not understand audio")
                    return self._transcribe_sphinx_fallback(audio)
                except sr.RequestError as e:
                    logger.warning(f"Google Speech Recognition service error: {e}")
                    return self._transcribe_sphinx_fallback(audio)
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
            
        except Exception as e:
            logger.error(f"Error processing Streamlit audio: {e}")
            return ""

    def _transcribe_sphinx_fallback(self, audio) -> str:
        try:
            text = self.recognizer.recognize_sphinx(audio)
            logger.info(f"Transcription completed using Sphinx: '{text[:50]}...'")
            return text.strip()
        except Exception:
            return ""
    
    def get_available_voices(self) -> list:
        """Get list of available TTS voices"""
        if not self.tts_engine:
            return []
        
        voices = self.tts_engine.getProperty('voices')
        return [{"id": voice.id, "name": voice.name} for voice in voices] if voices else []
    
    def test_audio_processing(self) -> bool:
        """Test if audio processing is working correctly"""
        try:
            # Test TTS
            test_text = "Hello, this is a test."
            audio_data = self.text_to_speech(test_text)
            
            if not audio_data:
                return False
            
            logger.info("Audio processing test passed")
            return True
            
        except Exception as e:
            logger.error(f"Audio processing test failed: {e}")
            return False

class EntityExtractor:
    """Extract entities from transcribed text"""
    
    def __init__(self):
        self.date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or DD/MM/YYYY
            r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4}\b',  # DD Month YYYY
            r'\b(?:today|tomorrow|yesterday)\b',  # Relative dates
        ]
        
        self.time_patterns = [
            r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b',  # HH:MM AM/PM
            r'\b\d{1,2}\s*(?:AM|PM|am|pm)\b',  # H AM/PM
        ]
        
        self.medication_keywords = [
            'medicine', 'medication', 'pill', 'tablet', 'capsule', 'dose',
            'take', 'prescription', 'drug'
        ]
        
        self.appointment_keywords = [
            'appointment', 'meeting', 'visit', 'doctor', 'clinic', 'hospital',
            'schedule', 'booked', 'planned'
        ]
    
    def extract_entities(self, text: str) -> dict:
        """Extract entities from text"""
        import re
        
        entities = {
            'dates': [],
            'times': [],
            'medications': [],
            'appointments': [],
            'people': [],
            'locations': []
        }
        
        text_lower = text.lower()
        
        # Extract dates
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['dates'].extend(matches)
        
        # Extract times
        for pattern in self.time_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['times'].extend(matches)
        
        # Extract medication mentions
        for keyword in self.medication_keywords:
            if keyword in text_lower:
                # Extract surrounding context
                context = self._extract_context(text, keyword)
                entities['medications'].append(context)
        
        # Extract appointment mentions
        for keyword in self.appointment_keywords:
            if keyword in text_lower:
                context = self._extract_context(text, keyword)
                entities['appointments'].append(context)
        
        return entities
    
    def _extract_context(self, text: str, keyword: str, context_size: int = 50) -> str:
        """Extract context around a keyword"""
        import re
        
        # Find all occurrences of the keyword
        for match in re.finditer(re.escape(keyword), text, re.IGNORECASE):
            start = max(0, match.start() - context_size)
            end = min(len(text), match.end() + context_size)
            return text[start:end].strip()
        
        return ""
