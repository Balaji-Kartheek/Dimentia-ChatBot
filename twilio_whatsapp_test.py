#!/usr/bin/env python3
"""
Test Twilio WhatsApp outbound + simulate inbound (2-way) without a real phone reply.

.env
----
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
  TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   (sandbox sender; override for production)
  TRUSTED_TEST_PHONE=+919390971479             → default destination for send / twoway

Commands
--------
  send [phone]       Outbound WhatsApp to trusted number.
  simulate <phone> <message>
                     POST a fake Twilio webhook to local `twilio_webhook.py`
                     (must match a **trusted contact** number in the DB). Saves reply in DB.
  twoway [phone]     Runs `send` then `simulate` with message "Sandbox test reply."

  WEBHOOK_BASE_URL=http://127.0.0.1:5001   optional (simulate / twoway)

WhatsApp sandbox: trusted person must WhatsApp **join your-code** to **+1 415-523-8886** once
(Twilio Console → Messaging → Try it out).
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).resolve().parent
load_dotenv(_root / ".env")
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _argv_phone(default_env: str = "TRUSTED_TEST_PHONE") -> str:
    return (sys.argv[2] if len(sys.argv) > 2 else os.getenv(default_env, "")).strip()


def cmd_send() -> int:
    from trusted_messaging import twilio_configured, send_trusted_whatsapp, _to_e164

    to = _argv_phone()
    if not to:
        print("Usage: python twilio_whatsapp_test.py send +919390971479")
        print("   or: set TRUSTED_TEST_PHONE in .env")
        return 1
    print("channel: WhatsApp")
    print("twilio_configured:", twilio_configured())
    e164 = _to_e164(to)
    print("destination:", e164 or "(invalid)")
    if not e164 or not twilio_configured():
        print("Fix .env and phone format, then retry.")
        return 2
    body = "From DementiaBot test:\nOutbound OK."
    ok, err = send_trusted_whatsapp(to, body)
    if ok:
        print("OK: Twilio accepted the message.")
        return 0
    print("FAILED:", err)
    return 3


def cmd_simulate() -> int:
    try:
        import requests
    except ImportError:
        print("pip install requests")
        return 4

    from config import TWILIO_WHATSAPP_FROM
    from trusted_messaging import _to_e164

    if len(sys.argv) < 4:
        print('Usage: python twilio_whatsapp_test.py simulate +919390971479 "Kiran is a friend"')
        return 1
    raw_from = sys.argv[2].strip()
    body = sys.argv[3]
    fr = _to_e164(raw_from)
    if not fr:
        print("invalid phone:", raw_from)
        return 2
    base = os.getenv("WEBHOOK_BASE_URL", "http://127.0.0.1:5001").rstrip("/")
    url = f"{base}/sms/incoming"

    wa_from = TWILIO_WHATSAPP_FROM
    data = {
        "From": f"whatsapp:{fr}",
        "To": wa_from if wa_from.startswith("whatsapp:") else f"whatsapp:{wa_from}",
        "Body": body,
        "MessageSid": f"SM_SIM_{uuid.uuid4().hex[:10]}",
        "NumMedia": "0",
    }

    print("POST", url)
    print("payload From/To:", data.get("From"), "|", data.get("To"))
    try:
        r = requests.post(url, data=data, timeout=10)
    except requests.RequestException as e:
        print("Request failed (is twilio_webhook.py running?):", e)
        return 5
    print("status:", r.status_code)
    print("body:", (r.text or "")[:600])
    return 0 if r.ok else 6


def cmd_twoway() -> int:
    phone = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    sys.argv = ["twilio_whatsapp_test.py", "send"] + ([phone] if phone else [])
    rc = cmd_send()
    if rc != 0:
        return rc
    to = phone or os.getenv("TRUSTED_TEST_PHONE", "").strip()
    if not to:
        print(
            "Set phone: python twilio_whatsapp_test.py twoway +919390971479 or TRUSTED_TEST_PHONE in .env"
        )
        return 7
    sys.argv = ["twilio_whatsapp_test.py", "simulate", to, "Sandbox test reply (simulated inbound)."]
    return cmd_simulate()


def main() -> int:
    if len(sys.argv) > 1:
        first = sys.argv[1].strip()
        if first and first[0] in "+0123456789":
            sys.argv = [sys.argv[0], "send", first] + list(sys.argv[2:])
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "send").lower().strip()
    if cmd in ("send", "wa", "whatsapp"):
        if cmd in ("wa", "whatsapp"):
            sys.argv = ["twilio_whatsapp_test.py", "send"] + sys.argv[2:]
        return cmd_send()
    if cmd == "simulate":
        return cmd_simulate()
    if cmd in ("twoway", "two-way", "2way"):
        return cmd_twoway()
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    print("Unknown command:", cmd)
    print(__doc__)
    return 9


if __name__ == "__main__":
    raise SystemExit(main())
