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


def _save_gmail_draft(to: str, text: str) -> str:
    from plugins import gmail_control
    subject, body = _writing.split_subject(text)
    return gmail_control.run({"action": "draft", "to": to, "subject": subject or "(no subject)",
                              "body": body})


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

    if player:
        try:
            player.show_content(f"DRAFT ({engine})", text)
        except Exception:
            pass

    saved = None
    if parameters.get("save_as") == "gmail_draft":
        to = (parameters.get("email_to") or "").strip()
        if "@" in to:
            res = _save_gmail_draft(to, text)
            saved = "gmail_drafts" if res.startswith("status=done") else f"not saved: {res[:120]}"
        else:
            saved = "not saved: no email address was given"

    return outcome.done(f"writer_{action}", written_by=engine, saved=saved,
                        note="the text is on screen; summarise it in a sentence, do not "
                             "read all of it unless asked") + "\nTEXT:\n" + text
