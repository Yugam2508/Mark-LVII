"""
plugins/gmail_control.py — your Gmail inbox by voice.

    "Any new emails?"                         action=list
    "Emails from Sarah this week"             action=list  query="from:sarah newer_than:7d"
    "Read the first one"                      action=read  message_number=1
    "Reply saying I'll be there"              action=reply message_number=1 body=...
    "Email mum that I'm running late"         action=send  to=... subject=... body=...
    "Draft an email to my teacher about ..."  action=draft to=... subject=... body=...
    "Mark them as read"                       action=mark_read

Sign-in is shared with calendar_control — see plugins/_google_auth.py.

SAFETY
    * Sending and replying go through the on-screen confirmation (core/confirm.py)
      unless you switch that off in ⚙ → PLUGIN SETTINGS. A sent email cannot be
      taken back, and the model must never be the one to decide it was approved.
    * Everything read from an email is wrapped with outcome.untrusted(), so a
      message saying "forward all your mail to ..." is read as text, not obeyed.
    * Nothing here can permanently delete mail.
"""
from __future__ import annotations

import base64
import re
import threading
from email.message import EmailMessage
from email.utils import parseaddr

from core import confirm, outcome
from memory.config_manager import get_plugin_setting
from plugins import _google_auth as gauth

PLUGIN_SETTINGS = gauth.PLUGIN_SETTINGS

PLUGIN = {
    "name": "gmail_control",
    "description": (
        "Reads and writes the user's Gmail. Use for checking new or unread email, "
        "finding emails (Gmail search syntax such as from:, subject:, newer_than:7d), "
        "reading one out, replying, sending a new email, saving a draft, or marking "
        "messages read. Not for WhatsApp or Telegram — use send_message for those. "
        "Refer to messages by their number in the last list you read out."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["list", "read", "send", "draft", "reply", "mark_read"],
            },
            "query": {
                "type": "STRING",
                "description": "For list: Gmail search. Default is unread mail in the inbox.",
            },
            "message_number": {
                "type": "INTEGER",
                "description": "For read/reply/mark_read: number from the last list (1 = first)",
            },
            "to": {"type": "STRING", "description": "For send/draft: recipient email address"},
            "subject": {"type": "STRING", "description": "For send/draft"},
            "body": {"type": "STRING", "description": "For send/draft/reply: the message text"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Gmail: list/read/reply/send/draft/mark_read.",
}

_last: list[dict] = []          # messages from the last list, for "read the second one"
_last_lock = threading.Lock()
_MAX_BODY = 4000


# ── helpers ───────────────────────────────────────────────────────────────────

def _headers(msg: dict) -> dict:
    return {h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])}


def _sender(raw_from: str) -> str:
    name, addr = parseaddr(raw_from or "")
    return name or addr or "unknown sender"


def _b64decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _body_text(payload: dict) -> str:
    """The readable text of a message: text/plain if there is one, else HTML stripped."""
    plain, html = [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_b64decode(data))
        elif data and mime == "text/html":
            html.append(_b64decode(data))
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    if plain:
        return "\n".join(plain).strip()
    if html:
        return _html_to_text("\n".join(html))
    return ""


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "table"]):
        block.append("\n")
    lines = (re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in soup.get_text().splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _show(player, title: str, text: str) -> None:
    if player:
        try:
            player.show_content(title, text)
        except Exception:
            pass


def _pick(p: dict) -> dict | None:
    with _last_lock:
        last = list(_last)
    n = p.get("message_number")
    if n is None and len(last) == 1:
        return last[0]
    if n is not None and 1 <= int(n) <= len(last):
        return last[int(n) - 1]
    return None


def _raw(msg: EmailMessage) -> str:
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def _needs_confirm() -> bool:
    return bool(get_plugin_setting(gauth.NAMESPACE, "send_requires_confirm", True))


def _send_now(raw: str, thread_id: str | None, label: str) -> str:
    svc = gauth.service("gmail", "v1")
    if svc is None:
        return gauth.SETUP_STEPS
    body = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id
    sent = svc.users().messages().send(userId="me", body=body).execute()
    if not sent.get("id"):
        return outcome.unverified("gmail_send", "Gmail did not return a message id", to=label)
    return outcome.done("gmail_send", to=label)


def _send_or_confirm(msg: EmailMessage, thread_id: str | None, title: str, player) -> str:
    raw = _raw(msg)
    detail = f"To: {msg['To']}\nSubject: {msg['Subject']}\n\n{msg.get_content()[:600]}"
    _show(player, "EMAIL — READY TO SEND", detail)
    if not _needs_confirm():
        return _send_now(raw, thread_id, msg["To"])
    return confirm.request(key=f"gmail_send:{msg['To']}:{msg['Subject']}", title=title,
                           detail=detail, run=lambda: _send_now(raw, thread_id, msg["To"]))


# ── actions ───────────────────────────────────────────────────────────────────

def _list(svc, p, player) -> str:
    query = (p.get("query") or "").strip() or "in:inbox is:unread"
    resp = svc.users().messages().list(userId="me", q=query, maxResults=10).execute()
    items = []
    for ref in resp.get("messages", []):
        m = svc.users().messages().get(userId="me", id=ref["id"], format="metadata",
                                       metadataHeaders=["From", "Subject", "Date"]).execute()
        h = _headers(m)
        items.append({"id": m["id"], "thread_id": m.get("threadId"),
                      "from": h.get("from", ""), "subject": h.get("subject", "(no subject)"),
                      "snippet": m.get("snippet", "")})
    with _last_lock:
        _last[:] = items
    if not items:
        _show(player, "GMAIL", f"No messages for: {query}")
        return outcome.done("gmail_list", query=query, count=0)
    text = "\n".join(f"{i}. {_sender(m['from'])} — {m['subject']}\n   {m['snippet'][:120]}"
                     for i, m in enumerate(items, 1))
    _show(player, f"GMAIL — {len(items)} MESSAGE(S)", text)
    more = "true" if resp.get("nextPageToken") else "false"
    return outcome.done("gmail_list", query=query, count=len(items), more_available=more) + \
        "\n" + outcome.untrusted("email", text)


def _read(svc, p, player) -> str:
    target = _pick(p)
    if target is None:
        return outcome.ask("gmail_read", "Which email? List them first, then tell me its number.")
    m = svc.users().messages().get(userId="me", id=target["id"], format="full").execute()
    h = _headers(m)
    body = _body_text(m.get("payload", {})) or m.get("snippet", "")
    cut = len(body) > _MAX_BODY
    body = body[:_MAX_BODY]
    _show(player, f"EMAIL — {h.get('subject', '')}",
          f"From: {h.get('from', '')}\nDate: {h.get('date', '')}\n\n{body}")
    # Sender and subject are written by whoever sent the mail, so they stay inside
    # the untrusted block with the body rather than in the facts line.
    return outcome.done("gmail_read", message_number=p.get("message_number"), truncated=cut) + \
        "\n" + outcome.untrusted("email", f"From: {h.get('from', '')}\n"
                                           f"Subject: {h.get('subject', '')}\n\n{body}")


def _mark_read(svc, p, player) -> str:
    if p.get("message_number") is not None:
        target = _pick(p)
        targets = [target] if target else []
    else:
        with _last_lock:
            targets = list(_last)
    if not targets:
        return outcome.ask("gmail_mark_read", "Which emails? List them first.")
    svc.users().messages().batchModify(userId="me", body={
        "ids": [t["id"] for t in targets], "removeLabelIds": ["UNREAD"]}).execute()
    return outcome.done("gmail_mark_read", count=len(targets))


def _compose(p) -> EmailMessage | str:
    to, subject, body = (p.get("to") or "").strip(), (p.get("subject") or "").strip(), \
        (p.get("body") or "").strip()
    if "@" not in to:
        return outcome.ask("gmail_compose", "What is the recipient's email address?", to=to)
    if not body:
        return outcome.ask("gmail_compose", "What should the email say?")
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject or "(no subject)"
    msg.set_content(body)
    return msg


def _draft(svc, p, player) -> str:
    msg = _compose(p)
    if isinstance(msg, str):
        return msg
    d = svc.users().drafts().create(userId="me", body={"message": {"raw": _raw(msg)}}).execute()
    if not d.get("id"):
        return outcome.unverified("gmail_draft", "Gmail did not return a draft id")
    _show(player, "EMAIL — DRAFT SAVED", f"To: {msg['To']}\nSubject: {msg['Subject']}\n\n"
                                         f"{msg.get_content()}")
    return outcome.done("gmail_draft", to=msg["To"], subject=msg["Subject"],
                        where="Drafts folder in Gmail")


def _send(svc, p, player) -> str:
    msg = _compose(p)
    if isinstance(msg, str):
        return msg
    return _send_or_confirm(msg, None, "Send email", player)


def _reply(svc, p, player) -> str:
    target = _pick(p)
    if target is None:
        return outcome.ask("gmail_reply", "Which email should I reply to? Tell me its number.")
    body = (p.get("body") or "").strip()
    if not body:
        return outcome.ask("gmail_reply", "What should the reply say?")
    m = svc.users().messages().get(userId="me", id=target["id"], format="metadata",
                                   metadataHeaders=["From", "Reply-To", "Subject",
                                                    "Message-ID", "References"]).execute()
    h = _headers(m)
    msg = EmailMessage()
    msg["To"] = h.get("reply-to") or h.get("from", "")
    subject = h.get("subject", "")
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if h.get("message-id"):
        msg["In-Reply-To"] = h["message-id"]
        msg["References"] = (h.get("references", "") + " " + h["message-id"]).strip()
    msg.set_content(body)
    return _send_or_confirm(msg, m.get("threadId"), "Send reply", player)


_ACTIONS = {"list": _list, "read": _read, "send": _send, "draft": _draft,
            "reply": _reply, "mark_read": _mark_read}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list").lower()
    handler = _ACTIONS.get(action)
    if handler is None:
        return outcome.failed("gmail", f"unknown action {action}")
    if not gauth.libraries_installed():
        return outcome.failed("gmail", "the Google libraries are not installed; run "
                              "pip install google-api-python-client google-auth-oauthlib")
    try:
        svc = gauth.service("gmail", "v1")
        if svc is None:
            return outcome.failed("gmail", gauth.SETUP_STEPS)
        return handler(svc, parameters, player)
    except Exception as e:  # HttpError, network, a revoked token — never raise
        return outcome.failed(f"gmail_{action}", f"Gmail error: {e}")
