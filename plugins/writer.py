"""
plugins/writer.py — "write it for me", in your voice, by the best writer available.

    "Write my teacher an email asking for an extension on the essay"
        action=write kind=email request=... email_to=... save_as=gmail_draft
    "Make this sound more polite: ..."      action=rewrite text=... instruction="more polite"
    "Write an Instagram caption for my new setup"
        action=write kind=post request=...

Which model writes, and your style guide, are set in ⚙ → PLUGIN SETTINGS →
WRITING VOICE (see plugins/_writing.py). With Claude Code installed and signed
in, Claude writes using your Claude subscription.

Writing can take several seconds, so this tool is NON_BLOCKING: on Gemini Live the
assistant keeps talking while it writes, and the text arrives when it is done.
`save_as=gmail_draft` puts an email straight into Gmail's Drafts — nothing is
ever SENT from here; sending stays with gmail_control and its on-screen CONFIRM.
"""
from __future__ import annotations

from core import outcome
from plugins import _writing

PLUGIN_SETTINGS = _writing.PLUGIN_SETTINGS

PLUGIN = {
    "name": "writer",
    "description": (
        "Writes or rewrites text for the user in their own style with a stronger "
        "writing model: emails, messages, documents, posts, essays, cover letters, "
        "replies. Use it whenever the user asks you to write, draft, compose, reword, "
        "shorten or improve something longer than a sentence, instead of writing it "
        "yourself. Give it every fact the user mentioned. For an email, set email_to "
        "and save_as=gmail_draft to put it in Gmail Drafts. Read the result back "
        "briefly; do not rewrite it."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["write", "rewrite"]},
            "kind": {"type": "STRING",
                     "enum": ["email", "message", "document", "post", "essay", "letter", "other"]},
            "request": {"type": "STRING",
                        "description": "For write: what to write, with every fact, name, date "
                                       "and detail the user gave"},
            "audience": {"type": "STRING", "description": "Who it is for, e.g. 'my teacher'"},
            "tone": {"type": "STRING", "description": "e.g. formal, friendly, apologetic"},
            "length": {"type": "STRING", "enum": ["short", "medium", "long"]},
            "text": {"type": "STRING", "description": "For rewrite: the text to change"},
            "instruction": {"type": "STRING", "description": "For rewrite: what to change"},
            "email_to": {"type": "STRING", "description": "For an email: recipient address"},
            "save_as": {"type": "STRING", "enum": ["none", "gmail_draft"],
                        "description": "gmail_draft saves an email to Gmail Drafts (never sends)"},
        },
        "required": ["action"],
    },
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "core",
    "brief": "Write/rewrite emails, messages, docs in the user's style.",
}


def _prompt(p: dict) -> str | None:
    if p.get("action") == "rewrite":
        text = (p.get("text") or "").strip()
        if not text:
            return None
        how = (p.get("instruction") or "improve it").strip()
        return f"Rewrite the text below. Change: {how}. Keep every fact.\n\nTEXT:\n{text}"
    req = (p.get("request") or "").strip()
    if not req:
        return None
    parts = [f"Write a {p.get('kind') or 'piece of text'}."]
    parts.append(f"What it needs to say: {req}")
    if p.get("audience"):
        parts.append(f"It is for: {p['audience']}")
    if p.get("tone"):
        parts.append(f"Tone: {p['tone']}")
    if p.get("length"):
        parts.append(f"Length: {p['length']}")
    return "\n".join(parts)


def _ok(result: str) -> bool:
    return result.startswith("status=done")


def _short(result: str) -> str:
    return result.split(" -- ")[0].replace("status=", "").replace("action=", "")[:140]


def _email_editor(to: str, text: str, state: dict) -> tuple[list, list, str]:
    """Fields and buttons for an email draft. SAVE TO DRAFTS creates the draft
    or updates the one already saved; SEND sends that draft (or a new message)."""
    from plugins import gmail_control
    subject, body = _writing.split_subject(text)
    fields = [{"key": "to", "label": "To", "value": to},
              {"key": "subject", "label": "Subject", "value": subject},
              {"key": "body", "label": "Message", "value": body, "multiline": True}]

    def save(v: dict):
        if "@" not in v.get("to", ""):
            return False, "Add an email address in To first."
        ok, msg, did = gmail_control.save_draft(v["to"], v["subject"], v["body"], state.get("draft_id"))
        if ok:
            state["draft_id"] = did
        return ok, msg

    def send(v: dict):
        if "@" not in v.get("to", ""):
            return False, "Add an email address in To first."
        if state.get("draft_id"):
            ok, msg, _ = gmail_control.save_draft(v["to"], v["subject"], v["body"], state["draft_id"])
            if not ok:
                return False, msg
            res = gmail_control.send_draft(state["draft_id"])
        else:
            res = gmail_control.send_message(v["to"], v["subject"], v["body"])
        return (_ok(res), "Sent ✓" if _ok(res) else _short(res))

    actions = [{"label": "UPDATE DRAFT" if state.get("draft_id") else "SAVE TO DRAFTS",
                "run": save, "primary": True, "close": False, "busy": "Saving…"},
               {"label": "SEND", "run": send, "close": True, "busy": "Sending…"}]
    return fields, actions, "body"


def _text_editor(text: str) -> tuple[list, list, str]:
    """Fields and buttons for anything that is not an email."""
    fields = [{"key": "text", "label": "Text", "value": text, "multiline": True}]

    def as_note(v: dict):
        from plugins import notes
        res = notes.run({"action": "add", "text": v["text"]}, player=None)
        return _ok(res), "Saved as a note ✓" if _ok(res) else _short(res)

    def as_doc(v: dict):
        from plugins import google_drive
        title = (v["text"].strip().splitlines() or ["Untitled"])[0][:60]
        res = google_drive.run({"action": "create_doc", "title": title, "content": v["text"]})
        return _ok(res), "Google Doc created and opened ✓" if _ok(res) else _short(res)

    actions = [{"label": "SAVE AS NOTE", "run": as_note, "primary": True, "busy": "Saving…"},
               {"label": "MAKE GOOGLE DOC", "run": as_doc, "busy": "Creating…"}]
    return fields, actions, "text"


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "write")
    prompt = _prompt(parameters)
    if prompt is None:
        return outcome.ask(f"writer_{action}", "What should I write?" if action == "write"
                           else "What text should I rewrite?")
    try:
        text, engine = _writing.write(prompt)
    except RuntimeError as e:
        return outcome.failed(f"writer_{action}", str(e)[:200])

    to = (parameters.get("email_to") or "").strip()
    is_email = parameters.get("kind") == "email" or bool(to) or \
        text.lower().startswith("subject:")
    saved, state = None, {}
    if parameters.get("save_as") == "gmail_draft":
        if "@" in to:
            from plugins import gmail_control
            subject, body = _writing.split_subject(text)
            ok, msg, did = gmail_control.save_draft(to, subject, body)
            state["draft_id"] = did if ok else None
            saved = "gmail_drafts" if ok else f"not saved: {msg}"
        else:
            saved = "not saved: no email address was given"

    # On screen as an editable draft: fix a word, then SAVE / SEND / COPY.
    fields, actions, copy = _email_editor(to, text, state) if is_email else _text_editor(text)
    from core import addons
    who = {"claude_code": "Claude", "anthropic": "Claude", "gemini": "Gemini"}.get(engine, engine)
    if not addons.edit(f"DRAFT — written by {who}", fields, actions, copy=copy,
                       note="Edit anything, then choose what to do with it.", player=player):
        if player:
            try:
                player.show_content(f"DRAFT ({engine})", text)
            except Exception:
                pass

    return outcome.done(f"writer_{action}", written_by=engine, saved=saved,
                        note="the draft is on screen where the user can edit, save or "
                             "send it with buttons; summarise it in a sentence, do not "
                             "read all of it unless asked") + "\nTEXT:\n" + text
