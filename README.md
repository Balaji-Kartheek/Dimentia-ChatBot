# Dementia Chatbot

Privacy-first Streamlit app for people with dementia to store memories, ask questions, and notify a trusted contact when safety signals are detected.

## What this app does

- Save memories by text or voice.
- Answer questions from saved memories.
- Work in multiple UI languages.
- Trigger trusted-contact alerts (WhatsApp via Twilio).
- Keep data local in SQLite with encrypted memory content.

## Current product shape (important)

- Single-role UI: users register as `user`.
- No separate caregiver console in navigation.
- Trusted-contact safety tools are available under `Settings`.

## Quick start

### 1) Prerequisites

- Python 3.9+
- Microphone/speaker (for voice features)
- Optional for WhatsApp alerts: Twilio account + ngrok

### 2) Setup

```bash
git clone <repository-url>
cd Dimentia-Bot-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m spacy download en_core_web_sm
```

### 3) Configure `.env`

Minimum:

```env
GEMINI_API_KEY=your_key_here
```

Optional WhatsApp alerts:

```env
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
DEFAULT_SMS_COUNTRY_CODE=91
```

### 4) Run app

```bash
streamlit run main.py
```

Default seeded account:

- Username: `user`
- Password: `user`

## Main workflow

1. Register/login.
2. Add memories from `Add Memory`.
3. Ask questions in `Ask Assistant`.
4. Open `Settings` for:
   - trusted contact details
   - open alerts and resolve actions
   - trusted-contact incoming replies
   - data export/import
   - clear memories / clear queries

## Safety alerts and repeated-query logic

- Query history is stored in `query_events`.
- Repeated-query severity is computed from same-signature questions in last 24h.
- `severity >= 3` can trigger trusted-contact notification.
- Cooldown is controlled by:
  - `REPEATED_QUERY_ALERT_COOLDOWN_HOURS` in `config.py`
- `Clear Queries` resets:
  - `query_events`
  - `alert_events` of type `repeated_query`
  - `trusted_inbound_messages` (trusted WhatsApp reply history)

## Trusted WhatsApp setup (Twilio)

### Outbound

- App sends WhatsApp through `trusted_messaging.py`.
- Alert body is formatted in `alert_delivery.py`.

### Inbound replies

- Twilio posts inbound messages to:
  - `POST /sms/incoming` handled by `twilio_webhook.py`
- Reply is matched to trusted contact and stored in DB.

### Local test wiring

1. Run webhook server:

```bash
python3 twilio_webhook.py
```

2. Expose with ngrok:

```bash
ngrok http 5001
```

3. In Twilio sandbox/sender config, set incoming webhook URL:

```text
https://<your-ngrok-host>/sms/incoming
```

4. Keep both running:
   - `streamlit run main.py`
   - `python3 twilio_webhook.py`

## Useful test commands

```bash
python3 twilio_whatsapp_test.py send +919876543210
python3 twilio_whatsapp_test.py simulate +919876543210 "Ramu is your brother"
python3 twilio_whatsapp_test.py twoway +919876543210
```

## Project structure (core files)

- `main.py` - app entry and routing
- `app_pages/` - Streamlit pages
- `database.py` - SQLite operations
- `memory_system.py` - retrieval/index logic
- `llm_integration.py` - LLM response logic
- `audio_processor.py` - speech I/O pipeline
- `trusted_messaging.py` - Twilio WhatsApp send
- `alert_delivery.py` - alert message templates + notify flow
- `twilio_webhook.py` - inbound webhook endpoint

## Troubleshooting

### App does not start

- Recreate venv and reinstall requirements.
- Confirm you are using `python3`.

### LLM answers fail

- Verify `GEMINI_API_KEY` in `.env`.
- Restart Streamlit after changing env values.

### WhatsApp not sending

- Check Twilio credentials and sender.
- Ensure target number joined sandbox (for sandbox mode).
- Verify phone format is valid (+countrycode...).

### Replies not appearing

- Confirm Twilio webhook points to `https://<ngrok>/sms/incoming`.
- Ensure `twilio_webhook.py` is running on port 5001.
- Ensure sender number matches trusted contact saved in app.

## Security notes

- Memory text/tags are encrypted at rest.
- Data is stored locally in SQLite by default.
- You can export data from Settings for backup.
