"""
Inbound WhatsApp (Twilio Messaging webhook; same payload shape as classic SMS). Run in a separate terminal:

  pip install twilio flask
  python twilio_webhook.py

Expose port 5001 (e.g. ngrok http 5001) and set the WhatsApp sender’s webhook to:
  https://<your-ngrok-host>/sms/incoming

Trusted person can reply with:
  REPLY <their message>
or any text (stored as-is).

Each reply is also appended as a memory (FAISS + DB) so Ask Assistant can retrieve it later.
"""
from pathlib import Path
import logging
import sys

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from config import DEFAULT_LANGUAGE
from database import MemoryDatabase
from trusted_messaging import normalize_phone_digits

logger = logging.getLogger(__name__)

app = Flask(__name__)
_db = MemoryDatabase()


def _trusted_reply_as_memory(user_id: str, trusted_name: str, msg: str) -> None:
    """Persist trusted person’s WhatsApp reply as a searchable memory for the patient account."""
    try:
        from memory_system import MemorySystem
    except Exception as e:
        logger.warning("MemorySystem unavailable: %s", e)
        return
    label = (trusted_name or "Trusted contact").strip()
    text = (
        f"{label} (trusted contact) answered by text: {msg.strip()}. "
        "Use this to answer future questions about people or facts the patient asked about."
    )
    try:
        ms = MemorySystem()
        ms.add_memory(
            text=text,
            source="trusted_contact_whatsapp",
            tags=["trusted_reply", "people"],
            language=DEFAULT_LANGUAGE,
            user_id=user_id,
            source_modality="text",
            importance=0.9,
        )
    except Exception:
        logger.exception("Could not add trusted reply to memory index")


@app.route("/", methods=["GET"])
def health():
    """Ping in browser or curl; Twilio uses POST /sms/incoming only."""
    return (
        "DementiaBot WhatsApp webhook OK. Twilio should POST to /sms/incoming — not GET /.",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


@app.route("/sms/incoming", methods=["POST"])
def incoming_sms():
    body = (request.values.get("Body") or "").strip()
    from_raw = request.values.get("From") or ""
    resp = MessagingResponse()
    logger.info("POST /sms/incoming From=%r Body_len=%d", from_raw, len(body))
    if not body:
        logger.info("Empty Body — ignoring (Twilio may send status callbacks without text).")
        return str(resp), 200

    if body.upper().startswith("REPLY"):
        msg = body[5:].lstrip(" :")
    else:
        msg = body

    norm = normalize_phone_digits(from_raw)
    user_ids = _db.find_user_ids_by_trusted_phone(norm)
    logger.info("Normalized sender digits (last 10): %r → matched user_ids: %s", norm[-10:] if len(norm) >= 10 else norm, user_ids)
    if not user_ids:
        resp.message("DementiaBot: This number is not registered as a trusted contact.")
        return str(resp), 200

    for uid in user_ids:
        _db.add_trusted_inbound_message(uid, msg, from_raw)
        tc = _db.get_trusted_contact(uid)
        tname = (tc or {}).get("name") or "Trusted contact"
        _trusted_reply_as_memory(uid, tname, msg)

    resp.message(
        "Thanks — your message was saved for the patient (Settings) and added to their memories for later questions."
    )
    return str(resp), 200


if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)
