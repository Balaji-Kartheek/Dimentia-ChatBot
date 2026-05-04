"""Notify trusted contacts about safety alerts via Twilio WhatsApp when configured."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional, Tuple

from trusted_messaging import looks_like_whatsapp_number, send_trusted_whatsapp

if TYPE_CHECKING:
    from database import MemoryDatabase

logger = logging.getLogger(__name__)


def _patient_label(db: "MemoryDatabase", user_id: str) -> str:
    u = db.get_user_by_id(user_id)
    if not u:
        return "patient"
    return (u.get("full_name") or u.get("username") or "patient").strip()


def _whatsapp_body_for_alert(
    alert_type: str,
    label: str,
    message: str,
    patient_question: Optional[str],
) -> str:
    """Short WhatsApp copy: From <logged-in user>: then one line of context."""
    q = (patient_question or "").strip()
    if alert_type == "trusted_lookup":
        if not q:
            m = re.search(r"weak for:\s*(.+?)(?:\.Trusted contact|\.\s*$)", message, re.I | re.DOTALL)
            q = (m.group(1).strip() if m else message)[:500]
        return f"From {label}:\n{q}"[:1500]
    if alert_type == "inactivity":
        return f"From {label}:\nNo recent app activity — please check in."[:1500]
    if alert_type == "repeated_query":
        if q:
            return f"From {label}:\n{q}"[:1500]
        return f"From {label}:\nRepeated similar questions — please review in the app."[:1500]
    return f"From {label}:\n{message[:900]}"[:1500]


def notify_trusted_for_alert(
    db: "MemoryDatabase",
    user_id: str,
    alert_id: Optional[str],
    alert_type: str,
    message: str,
    severity: int,
    patient_question: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Returns (True, "") on successful send, (False, reason) otherwise.
    reason may be: no_trusted_contact, contact_not_whatsapp_capable, twilio_not_configured, invalid_phone, or Twilio API message.

    patient_question: for trusted_lookup / repeated_query, the user's actual question line (short message).
    """
    trusted = db.get_trusted_contact(user_id)
    if not trusted:
        logger.warning("No trusted contact for user %s", user_id)
        return False, "no_trusted_contact"
    contact = trusted.get("contact") or ""
    if not looks_like_whatsapp_number(contact):
        logger.info("Trusted contact is not a usable phone number; skipping WhatsApp.")
        return False, "contact_not_whatsapp_capable"
    label = _patient_label(db, user_id)
    body = _whatsapp_body_for_alert(alert_type, label, message, patient_question)
    ok, err = send_trusted_whatsapp(contact, body)
    if ok and alert_id:
        db.mark_alert_external_notified(alert_id)
    elif not ok and err != "twilio_not_configured":
        logger.error("Trusted WhatsApp failed: %s", err)
    return (True, "") if ok else (False, err or "send_failed")
