"""
Trusted-contact alerts via Twilio WhatsApp only (sandbox or production sender).

Inbound uses the same Twilio Messaging webhook as outbound: POST /sms/incoming on twilio_webhook.py.
"""
from __future__ import annotations

import logging
import re
from typing import Tuple

from config import (
    DEFAULT_SMS_COUNTRY_CODE,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_FROM,
)

logger = logging.getLogger(__name__)


def normalize_phone_digits(contact: str) -> str:
    digits = "".join(c for c in (contact or "") if c.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def looks_like_whatsapp_number(contact: str) -> bool:
    """Trusted contact must be a reachable mobile (digits) for WhatsApp delivery."""
    return len(normalize_phone_digits(contact)) >= 10


def _default_country_code() -> str:
    return (DEFAULT_SMS_COUNTRY_CODE or "91").strip().lstrip("+")


def _normalize_digits(contact: str) -> str:
    """Fix common India entry mistakes (trunk 0) before building E.164."""
    d = contact
    cc = _default_country_code()
    if cc != "91" or not d:
        return d
    while len(d) >= 11 and d.startswith("0") and len(d) > 10 and d[1] in "6789":
        d = d[1:]
    return d


def _is_plausible_e164(e164: str) -> bool:
    if not e164 or not e164.startswith("+"):
        return False
    body = re.sub(r"\D", "", e164)
    if not body or body.startswith("0"):
        return False
    if e164.startswith("+91"):
        return bool(re.fullmatch(r"91[6-9]\d{9}", body))
    if e164.startswith("+1") and len(body) == 11:
        return True
    return 10 <= len(body) <= 14


def _to_e164(contact: str) -> str:
    raw = (contact or "").strip()
    digits = _normalize_digits(re.sub(r"\D", "", raw))
    cc = _default_country_code()

    if raw.startswith("+"):
        candidate = "+" + digits
        if not _is_plausible_e164(candidate):
            logger.warning("E.164 failed validation for input %r → %r", contact, candidate)
            return ""
        return candidate

    if len(digits) == 12 and digits.startswith("91"):
        candidate = "+" + digits
        return candidate if _is_plausible_e164(candidate) else ""

    if len(digits) == 10:
        candidate = f"+{cc}{digits}"
        if cc == "91" and not re.match(r"^[6-9]\d{9}$", digits):
            logger.warning("10-digit India mobile should start with 6–9; got %r", digits)
            return ""
        return candidate if _is_plausible_e164(candidate) else ""

    if len(digits) >= 11:
        candidate = "+" + digits
        return candidate if _is_plausible_e164(candidate) else ""
    return ""


def twilio_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM)


def _format_twilio_error(exc: BaseException) -> str:
    """Short plain-text error for Streamlit (Twilio client may include ANSI / long bodies)."""
    try:
        from twilio.base.exceptions import TwilioRestException

        if isinstance(exc, TwilioRestException):
            code = getattr(exc, "code", None) or getattr(exc, "status", "")
            msg = getattr(exc, "msg", None) or str(exc)
            return f"Twilio {code}: {msg}".strip()
    except ImportError:
        pass
    text = str(exc)
    text = re.sub(r"\x1b\[[0-9;]*[mK]", "", text)
    text = re.sub(r"\[\d{1,2}m", "", text)
    text = " ".join(text.split())
    if "20003" in text or "Authenticate" in text:
        return (
            "Twilio authentication failed (error 20003). Copy the **Auth Token** again from "
            "console.twilio.com (Account → API keys & tokens). In `.env` use `TWILIO_AUTH_TOKEN=...` with no "
            "extra spaces; restart Streamlit after saving."
        )
    return text[:800]


def _whatsapp_from_address() -> str:
    fa = (TWILIO_WHATSAPP_FROM or "").strip()
    if fa.startswith("whatsapp:"):
        return fa
    if fa.startswith("+"):
        return f"whatsapp:{fa}"
    return f"whatsapp:+{fa.lstrip('+')}"


def send_trusted_whatsapp(to_contact: str, body: str) -> Tuple[bool, str]:
    if not twilio_configured():
        logger.info("Twilio not configured; WhatsApp not sent: %s", (body or "")[:100])
        return False, "twilio_not_configured"
    to_e164 = _to_e164(to_contact)
    if not to_e164 or not _is_plausible_e164(to_e164):
        return (
            False,
            "invalid_phone: use +91XXXXXXXXXX (10 digits after 91, starting 6–9), or 10-digit mobile "
            "with DEFAULT_SMS_COUNTRY_CODE=91. Avoid a leading 0 before the number.",
        )
    to_addr = to_e164 if to_e164.startswith("whatsapp:") else f"whatsapp:{to_e164}"
    from_addr = _whatsapp_from_address()
    logger.info("Twilio WhatsApp to=%s from=%s", to_addr, from_addr)
    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(to=to_addr, from_=from_addr, body=(body or "")[:1500])
        return True, ""
    except Exception as e:
        logger.exception("Twilio WhatsApp send failed")
        return False, _format_twilio_error(e)
