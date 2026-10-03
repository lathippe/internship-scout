"""Delivery: the morning email, urgent pings, and reading replies back.

Secrets come from environment variables (GitHub Actions secrets):
  SCOUT_EMAIL, SCOUT_EMAIL_APP_PASSWORD     Gmail address + app password (sends the digest, reads your inbox)
  WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_TO
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  NTFY_TOPIC
"""
from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
import json
import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SUBJECT_TAG = "[Scout]"


def env(k: str) -> str:
    return os.environ.get(k, "").strip()


def _post(url: str, data: dict, headers=None, form=False) -> dict:
    body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
    h = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    try:
        return json.loads(raw)
    except ValueError:
        return {}


# ---------- email ----------

def send_email(subject: str, html: str, text: str) -> bool:
    user, pw = env("SCOUT_EMAIL"), env("SCOUT_EMAIL_APP_PASSWORD")
    if not (user and pw):
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{SUBJECT_TAG} {subject}"
    msg["From"] = user
    msg["To"] = env("SCOUT_EMAIL_TO") or user
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
    return True


def _decode(v) -> str:
    return str(email.header.make_header(email.header.decode_header(v or "")))


def _body(m) -> str:
    if m.is_multipart():
        parts = [p for p in m.walk() if p.get_content_type() == "text/plain"] or \
                [p for p in m.walk() if p.get_content_type() == "text/html"]
        m = parts[0] if parts else m
    raw = m.get_payload(decode=True) or b""
    txt = raw.decode(m.get_content_charset() or "utf-8", "replace")
    if m.get_content_type() == "text/html":
        from .sources import text_of
        txt = text_of(txt)
    return txt


def recent_mail(days: int = 2, limit: int = 60) -> list:
    """Messages from the last few days: [{id, from, subject, body, date}]. Read-only."""
    user, pw = env("SCOUT_EMAIL"), env("SCOUT_EMAIL_APP_PASSWORD")
    if not (user and pw):
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    out = []
    with imaplib.IMAP4_SSL("imap.gmail.com") as im:
        im.login(user, pw)
        im.select("INBOX", readonly=True)
        _, ids = im.search(None, f'(SINCE "{since}")')
        for i in ids[0].split()[-limit:]:
            _, data = im.fetch(i, "(BODY.PEEK[])")
            m = email.message_from_bytes(data[0][1])
            out.append({"id": m.get("Message-ID", i.decode()), "from": _decode(m.get("From")),
                        "subject": _decode(m.get("Subject")), "body": _body(m),
                        "date": email.utils.parsedate_to_datetime(m.get("Date")).isoformat() if m.get("Date") else ""})
    return out


def is_reply_to_digest(m: dict) -> bool:
    me = env("SCOUT_EMAIL").lower()
    return SUBJECT_TAG in m["subject"] and m["subject"].lower().startswith("re:") and me in m["from"].lower()


def strip_quote(body: str) -> str:
    lines = []
    for line in body.splitlines():
        if line.startswith(">") or (line.startswith("On ") and line.rstrip().endswith("wrote:")):
            break
        lines.append(line)
    return "\n".join(lines).strip()


# ---------- urgent pings ----------

def ping(channel: str, text: str, url: str = "") -> bool:
    try:
        if channel == "whatsapp":
            return _whatsapp(text, url)
        if channel == "telegram":
            return _telegram(text + (f"\n{url}" if url else ""))
        if channel == "ntfy":
            return _ntfy(text, url)
        if channel == "email":
            return send_email(text[:80], f"<p>{text}</p>" + (f'<p><a href="{url}">Open</a></p>' if url else ""), text + "\n" + url)
    except Exception as e:  # a failed ping must not lose the run
        print(f"  ! ping via {channel} failed: {e}")
    return False


def _whatsapp(text: str, url: str) -> bool:
    tok, pid, to = env("WHATSAPP_TOKEN"), env("WHATSAPP_PHONE_ID"), env("WHATSAPP_TO")
    if not (tok and pid and to):
        return False
    api = f"https://graph.facebook.com/v21.0/{pid}/messages"
    head = {"Authorization": f"Bearer {tok}"}
    # Outside a 24-hour chat window WhatsApp only delivers approved templates.
    # The setup chat creates a template named 'scout_alert' with one text variable.
    tpl = env("WHATSAPP_TEMPLATE") or "scout_alert"
    try:
        _post(api, {"messaging_product": "whatsapp", "to": to, "type": "template",
                    "template": {"name": tpl, "language": {"code": "en"},
                                 "components": [{"type": "body", "parameters": [{"type": "text", "text": " ".join((text + " " + url).split())[:900]}]}]}}, head)
        return True
    except urllib.error.HTTPError:
        _post(api, {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text + "\n" + url}}, head)
        return True


def _telegram(text: str) -> bool:
    tok, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    _post(f"https://api.telegram.org/bot{tok}/sendMessage", {"chat_id": chat, "text": text, "disable_web_page_preview": True})
    return True


def telegram_replies(offset: int):
    """New messages you sent the bot since the last run. Returns (texts, next_offset)."""
    tok, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return [], offset
    with urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/getUpdates?offset={offset}&timeout=0", timeout=30) as r:
        d = json.loads(r.read())
    texts, nxt = [], offset
    for u in d.get("result", []):
        nxt = max(nxt, u["update_id"] + 1)
        m = u.get("message") or {}
        if str((m.get("chat") or {}).get("id")) == chat and m.get("text"):
            texts.append(m["text"])
    return texts, nxt


def _ntfy(text: str, url: str) -> bool:
    topic = env("NTFY_TOPIC")
    if not topic:
        return False
    h = {"Title": "Internship scout"}
    if url:
        h["Click"] = url
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=text.encode(), headers=h, method="POST")
    urllib.request.urlopen(req, timeout=20).read()
    return True
