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

## Trusted contact: WhatsApp two-way (Twilio)

Safety alerts (e.g. weak memory on a person question, inactivity) can notify a **trusted contact** over **WhatsApp only**, using Twilio’s Messaging API. Replies from the trusted person are delivered to your webhook, stored in the database, and indexed as memories so **Ask Assistant** can use them later.

### How the loop works

1. **Outbound (app → trusted person):** `trusted_messaging.py` sends a WhatsApp message with `To` / `From` as `whatsapp:+E164…` (see `TWILIO_WHATSAPP_FROM` in `.env`).
2. **Inbound (trusted person → app):** Twilio POSTs to your **webhook URL** (same payload shape as classic SMS). The app handles **`POST /sms/incoming`** in `twilio_webhook.py` (path name is Twilio convention; it is used for WhatsApp too).
3. **Matching:** The sender’s number is normalized to digits and matched against the **trusted contact** saved for the patient in the app. The trusted person must use the **same** mobile number you saved (E.164 or 10-digit + `DEFAULT_SMS_COUNTRY_CODE`).

### Prerequisites

- [Twilio](https://www.twilio.com) account with **WhatsApp** enabled (start with the **sandbox**).
- **Python packages:** `twilio` and `flask` (already listed in `requirements.txt`).
- **Public HTTPS URL** for local dev: [ngrok](https://ngrok.com) (or similar) so Twilio can reach your machine.

### Environment variables (`.env`)

| Variable | Purpose |
|----------|---------|
| `TWILIO_ACCOUNT_SID` | From Twilio Console → Account |
| `TWILIO_AUTH_TOKEN` | From Twilio Console (no extra spaces or quotes) |
| `TWILIO_WHATSAPP_FROM` | Sandbox default is often `whatsapp:+14155238886`; set your production WhatsApp sender when you graduate from sandbox |
| `DEFAULT_SMS_COUNTRY_CODE` | Optional; default `91`. Used when the trusted contact is stored as **10 digits without** `+` |
| `TRUSTED_TEST_PHONE` | Optional; default destination for `twilio_whatsapp_test.py` (E.164, e.g. `+919876543210`) |

Remove any old `TWILIO_PHONE_NUMBER` or `TWILIO_USE_WHATSAPP` entries; outbound is **WhatsApp-only**.

### Sandbox: one-time setup per trusted number

1. In Twilio Console: **Messaging** → **Try it out** → **Send a WhatsApp message** — note your **join code** and sandbox number (**+1 415 523 8886**).
2. From the trusted person’s WhatsApp, send: `join <your-code>` to that number.
3. Until you use an approved production sender, **only numbers that joined** the sandbox can receive your outbound alerts.

### Configure the inbound webhook (Twilio)

1. Run the webhook server (default port **5001**):
   ```bash
   python twilio_webhook.py
   ```
2. Expose it with ngrok:
   ```bash
   ngrok http 5001
   ```
3. Copy the **HTTPS** URL ngrok prints (e.g. `https://abc123.ngrok-free.app`).
4. In Twilio, set the **WhatsApp sandbox** (or your WhatsApp sender) **“When a message comes in”** URL to:
   ```text
   https://<your-ngrok-host>/sms/incoming
   ```
   Method: **HTTP POST**.

Keep **Streamlit** (`run.py` / `main.py`) and **`twilio_webhook.py`** running while testing replies; inbound does not go through Streamlit.

### Verify in the app

- Register or set a **trusted contact** phone that matches the WhatsApp number (with country code).
- **Settings → System**: green Twilio WhatsApp status and ngrok tunnel hint.
- **Settings → Trusted & safety**: open alerts (resolve to allow new WhatsApp notifications), **replies** from the trusted contact after a successful webhook delivery.

### How to test (CLI)

Use `twilio_whatsapp_test.py` from the project root (loads `.env` automatically).

| Command | What it does |
|---------|----------------|
| `python twilio_whatsapp_test.py send +919876543210` | Sends a short test WhatsApp to that number (must be sandbox-joined if on sandbox). |
| `python twilio_whatsapp_test.py simulate +919876543210 "Kiran is a friend"` | **POSTs a fake inbound** message to `http://127.0.0.1:5001/sms/incoming` (must match a trusted contact in the DB). Requires `twilio_webhook.py` running. |
| `python twilio_whatsapp_test.py twoway +919876543210` | Runs `send` then `simulate` with a default reply body. |

Optional: `WEBHOOK_BASE_URL=http://127.0.0.1:5001` if your webhook listens elsewhere.

**End-to-end check:** (1) `send` → trusted person sees WhatsApp. (2) They reply in WhatsApp → Twilio hits your ngrok URL → `twilio_webhook.py` stores the message. (3) Confirm under **Settings** and that a new memory exists for retrieval.

### Troubleshooting (WhatsApp)

- **20003 / authentication:** Re-copy `TWILIO_AUTH_TOKEN` from Twilio; restart the app after editing `.env`.
- **Message not received (sandbox):** Trusted number must **join** the sandbox; sender must be `TWILIO_WHATSAPP_FROM` for your environment.
- **Inbound not saved:** Webhook URL must be **HTTPS**, path **`/sms/incoming`**, and `twilio_webhook.py` + ngrok must be running; trusted contact digits must match the sender.
- **21265 / invalid number:** Use valid E.164 (India mobile: `+91` + 10 digits starting with 6–9).

Related files: `trusted_messaging.py`, `alert_delivery.py`, `twilio_webhook.py`, `config.py`.

## 🛠️ Technical Details

### Core Components

- **`main.py`**: Streamlit application entry point
- **`config.py`**: Configuration management and encryption
- **`database.py`**: SQLite database operations
- **`memory_system.py`**: Vector embeddings and retrieval (FAISS)
- **`audio_processor.py`**: Whisper ASR and TTS integration
- **`llm_integration.py`**: Ollama LLM integration for RAG
- **`trusted_messaging.py`**, **`alert_delivery.py`**: Trusted-contact WhatsApp alerts (Twilio)
- **`twilio_webhook.py`**: Inbound WhatsApp → DB + memories (`POST /sms/incoming`)
- **`twilio_whatsapp_test.py`**: CLI to test outbound and simulated inbound
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
