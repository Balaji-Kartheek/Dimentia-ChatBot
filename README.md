# 🧠 Dementia Chatbot - Personal Memory Assistant

A **privacy-first Streamlit web application** that helps people with dementia (PwD) recall personal information like medication schedules, appointments, and family details via **voice and text chat** in **multiple languages**.

## 🌟 Key Features

- **🎤 Voice Input/Output**: Record voice notes and ask questions verbally
- **🌐 Multilingual Support**: English, Hindi, Tamil, Spanish, French, German
- **🧠 AI-Powered Memory**: Uses local LLM (Ollama) with RAG for intelligent responses
- **🔒 Privacy-First**: All data stored locally, encrypted with industry-standard encryption
- **👥 Caregiver Console**: Dedicated interface for caregivers to manage and verify memories
- **📱 Easy-to-Use Interface**: Designed specifically for people with dementia

## 🏗️ Architecture

```
Audio/Text Input → Whisper (ASR) → Entity Extraction → Chunk + Embed
→ Store (SQLite + FAISS) → Query → Retrieve Top-k → RAG (Ollama)
→ Answer + TTS Output → Display with Provenance
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+**
2. **Ollama** - Local LLM server
3. **Audio system** - Microphone and speakers

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Dementia-Bot
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv myenv
   # Windows
   myenv\Scripts\activate
   # Linux/Mac
   source myenv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install and setup Ollama:**
   ```bash
   # Download Ollama from https://ollama.ai
   # Install a model (e.g., wizardlm2:latest )
   ollama pull wizardlm2:latest 
   ```

5. **Download spaCy language model:**
   ```bash
   python -m spacy download en_core_web_sm
   ```

6. **Run the application:**
   ```bash
   python run.py
   ```
   Or directly:
   ```bash
   streamlit run main.py
   ```

## 🔑 Login Credentials

### For Person with Dementia:
- **Username:** `user`
- **Password:** `dementia123`

### For Caregiver:
- **Username:** `caregiver`
- **Password:** `caregiver123`

## 📱 How to Use

### 1. Adding Memories
- **Voice**: Click the microphone, record your memory, and let AI transcribe it
- **Text**: Type your memory directly
- The system automatically extracts important information (dates, medications, people)

### 2. Asking Questions
- **Voice**: Record your question and get a spoken response
- **Text**: Type your question for instant answers
- Responses are based on your stored memories

### 3. Caregiver Management
- Review and verify memories
- Monitor user activity
- Manage system settings
- Export/import data

## 🔧 Configuration

### Language Settings
- Change interface language in Settings
- Voice recognition adapts to selected language
- TTS generates responses in chosen language

### Model Configuration
Edit `config.py` to customize:
- Embedding model: `EMBEDDING_MODEL = "all-MiniLM-L6-v2"`
- LLM model: `OLLAMA_MODEL = "wizardlm2:latest "`
- Whisper model: `WHISPER_MODEL = "base"`

## 🛠️ Technical Details

### Core Components

- **`main.py`**: Streamlit application entry point
- **`config.py`**: Configuration management and encryption
- **`database.py`**: SQLite database operations
- **`memory_system.py`**: Vector embeddings and retrieval (FAISS)
- **`audio_processor.py`**: Whisper ASR and TTS integration
- **`llm_integration.py`**: Ollama LLM integration for RAG
- **`pages/`**: Individual Streamlit pages

### Database Schema

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    text_encrypted BLOB NOT NULL,
    timestamp DATETIME NOT NULL,
    source TEXT NOT NULL,
    tags_encrypted BLOB,
    trust_level TEXT DEFAULT 'unverified',
    language TEXT DEFAULT 'en',
    caregiver_confirmed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### How to Check the Table Contents
```bash
sqlite3 data/memories.db
```

Tables
```bash
.tables
```

Schema
```bash
.schema
```


Queries:
```bash
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
SELECT COUNT(*) FROM memories;
SELECT id, user_id, source, language, created_at FROM memories LIMIT 10;
SELECT id, username, role FROM users;
```


### Security Features

- **Fernet Encryption**: All memories encrypted at rest
- **Local Storage**: No data leaves your device
- **Access Control**: Separate user and caregiver interfaces
- **Activity Logging**: Track all interactions

## 🌍 Supported Languages

| Language | Code | Voice Support | Text Support |
|----------|------|---------------|--------------|
| English  | en   | ✅            | ✅           |
| Hindi    | hi   | ✅            | ✅           |
| Tamil    | ta   | ✅            | ✅           |
| Spanish  | es   | ✅            | ✅           |
| French   | fr   | ✅            | ✅           |
| German   | de   | ✅            | ✅           |

## 🔍 Troubleshooting

### Common Issues

1. **Ollama Connection Failed**
   - Ensure Ollama is running: `ollama serve`
   - Check if model is installed: `ollama list`
   - Verify port 11434 is accessible

2. **Audio Issues**
   - Check microphone permissions
   - Verify audio drivers are working
   - Test with system audio settings

3. **Memory Issues**
   - Check disk space (FAISS index can be large)
   - Verify SQLite database permissions
   - Clear cache if needed

### Performance Optimization

- Use smaller Whisper models for faster processing
- Adjust `TOP_K_RESULTS` in config for faster retrieval
- Regularly clean up old activity logs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **OpenAI Whisper** for speech recognition
- **Ollama** for local LLM inference
- **FAISS** for vector similarity search
- **Streamlit** for the web interface
- **sentence-transformers** for embeddings

## 📞 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the configuration options

---

**Made with ❤️ for people with dementia and their caregivers**
