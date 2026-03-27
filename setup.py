"""
Setup script for Dementia Chatbot
"""
from setuptools import setup, find_packages

setup(
    name="dementia-chatbot",
    version="1.0.0",
    description="Personal Memory Assistant for People with Dementia",
    author="Dementia Bot Team",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.28.0",
        "streamlit-audio-recorder>=0.0.8",
        "openai-whisper>=20231117",
        "pyttsx3>=2.90",
        "coqui-tts>=0.20.5",
        "sounddevice>=0.4.6",
        "soundfile>=0.12.1",
        "sentence-transformers>=2.2.2",
        "faiss-cpu>=1.7.4",
        "chromadb>=0.4.15",
        "google-genai>=1.45.0",
        "requests>=2.31.0",
        "spacy>=3.7.2",
        "nltk>=3.8.1",
        "cryptography>=41.0.7",
        "bcrypt>=4.1.2",
        "pandas>=2.1.3",
        "numpy>=1.24.3",
        "python-dateutil>=2.8.2",
        "librosa>=0.10.1",
        "pyaudio>=0.2.11",
        "python-dotenv>=1.0.0"
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
