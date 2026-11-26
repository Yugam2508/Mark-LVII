"""
plugins/deep_think.py — Jarvis hands a question to a stronger model, by itself or on your doubt.

There is nothing to remember to say. Jarvis calls this when a question needs real reasoning, when
it isn't confident in its own quick answer, or when you doubt it in any words ("that doesn't sound
right", "are you sure?", "think about it more", "get a second opinion"). The answer comes back as a
card with a short spoken summary that names the model.

By voice:
    "Use Claude for deep thinking" / "use OpenAI" / "go back to automatic"    use
    "Add this OpenAI key"  (after copying the key)                             add_key
    "How much deep thinking have I used?"                                      status

The OpenAI key is read from the clipboard — never spoken, shown or sent to any model — checked
against OpenAI, stored with your other credentials, and the clipboard is cleared. Jarvis asks OpenAI
which models the key can use and picks the strongest; "use model <name>" overrides that.
See core/deepthink.py for how keys, fallbacks and limits work.
"""
from __future__ import annotations

import re
import threading

from core import addons, deepthink, outcome

PLUGIN = {
    "name": "deep_think",
    "description": (
        "Hand a question to a stronger, slower reasoning model and bring back the analysis. RARELY NEEDED: "
        "answer yourself by default. Call it when the user asks for it or doubts you in words ('think "
        "harder', 'go deeper', 'second opinion', 'are you sure', 'that doesn't sound right'), setting "
        "user_asked true; or for a genuinely hard, high-stakes problem you can't do properly in a short "
        "answer. NEVER for quick facts, commands, opening things, chat, or merely being unsure. "
        "Pass the question fully, including what the user was really asking. Also: 'use' to change "
        "which model does the deep thinking (openai / claude / auto, or a model name), 'add_key' when "
        "the user wants to add an OpenAI key (they copy it first), 'status' for usage."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["think", "use", "add_key", "status", "remove_keys", "set_limit"]},
            "question": {"type": "STRING", "description": "For think: the full question to analyse"},
            "user_asked": {"type": "BOOLEAN", "description": "For think: true only when the user asked for deeper "
                           "thinking or doubted your answer in words"},
            "provider": {"type": "STRING", "description": "For use: openai, claude, auto, or a model name"},
            "limit": {"type": "INTEGER", "description": "For set_limit: deep-thinking calls allowed per day"},
        },
        "required": ["action"],
    },
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "core",
    "brief": "Deeper analysis by a stronger model; use / add_key / status.",
}


PLUGIN_SETTINGS = {
    "namespace": deepthink.NAMESPACE,
    "title": "DEEP THINKING",
    "fields": [
        {"key": "provider", "label": "Who does the deep thinking (also by voice: 'use Claude')",
         "type": "choice", "options": ["auto", "openai", "claude"], "default": "auto"},
        {"key": "model", "label": "OpenAI model (empty = the strongest the key can use)", "type": "text",
         "placeholder": "chosen automatically"},
        {"key": "auto", "label": "Let Jarvis go to the stronger model on its own for hard problems "
         "(off = only when I ask or doubt it)", "type": "toggle", "default": False},
        {"key": "claude_model", "label": "Claude model when Claude does it", "type": "choice",
         "options": ["opus", "sonnet"], "default": "opus"},
        {"key": "daily_calls", "label": "Most deep-thinking calls per day", "type": "text", "placeholder": "40"},
    ],
}


def context_text(max_turns: int = 12) -> str:
    """The conversation so far and the two always-on memory boxes, for the deeper model."""
    parts = []
    try:
        from memory.memory_manager import load_memory
        mem = load_memory()
        for cat, title in (("core_user", "About the user"), ("core_self", "The assistant's role")):
            lines = [f"- {k}: {v.get('value')}" for k, v in (mem.get(cat) or {}).items() if isinstance(v, dict)]
            if lines:
                parts.append(f"{title}:\n" + "\n".join(lines[:12]))
        ident = [f"{k}: {v.get('value')}" for k, v in (mem.get("identity") or {}).items() if isinstance(v, dict)]
        if ident:
            parts.append("Identity: " + "; ".join(ident[:8]))
    except Exception:
        pass
    try:
        log = list(getattr(addons.assistant(), "_session_log", []) or [])[-max_turns:]
        if log:
            parts.append("Conversation so far:\n" + "\n".join(t[:500] for t in log))
    except Exception:
        pass
    return "\n\n".join(parts)[:6000]


def _worker(question: str, context: str) -> None:
    try:
        text, model = deepthink.think(question, context)
    except Exception as e:
        addons.notify("Deeper analysis failed", str(e)[:400],
                      "[SYSTEM] The deeper analysis could not be done. In one sentence say so and why, and "
                      "answer as well as you can yourself:\n" + outcome.untrusted("deep_think", str(e)[:300]),
                      kind="error")
        return
    addons.notify(f"Deeper analysis · {model}", text,
                  f"[SYSTEM] The deeper analysis by {model} is back (shown on screen in full). In two or three "
                  "sentences give the user its conclusion and the main reason, say it came from the stronger "
                  "model, and say you've put the detail on screen. If it disagrees with what you said before, "
                  "say so plainly.\n" + outcome.untrusted("deep_think", text[:6000]), kind="task")


def _clipboard() -> str:
    try:
        import pyperclip
        return (pyperclip.paste() or "").strip()
    except Exception:
        return ""


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    try:
        if action == "think":
            q = str(parameters.get("question") or "").strip()
            if not q:
                return outcome.ask("deep_think", "What should I think through?")
            if not parameters.get("user_asked") and not deepthink.auto_enabled():
                return outcome.done("deep_think", skipped="not asked for",
                                    note="answer it yourself now; the user did not ask for the stronger model")
            if not deepthink.keys() and not _claude_possible():
                return outcome.failed("deep_think", "no deeper model is set up yet — say 'add this OpenAI key' "
                                      "after copying one, or sign in to Claude Code on this PC")
            threading.Thread(target=_worker, args=(q, context_text()), daemon=True, name="deep_think").start()
            return outcome.started("deep_think", note="say in a few words that you're getting the stronger "
                                   "model to think this through and will report back; keep talking naturally")

        if action == "use":
            what = str(parameters.get("provider") or "").strip()
            if not what:
                return outcome.ask("deep_think_use", "Which one: OpenAI, Claude, or automatic?")
            if re.search(r"\d", what) or what.lower().startswith(("o1", "o3", "o4")):
                deepthink.set_model(what)               # a model name such as gpt-5-pro or o3
                return outcome.done("deep_think_use", model=what, note="OpenAI keys will use this model")
            try:
                return outcome.done("deep_think_use", provider=deepthink.set_preference(what))
            except deepthink.DeepError as e:
                return outcome.failed("deep_think_use", str(e))

        if action == "add_key":
            clip = _clipboard()
            if not re.match(r"^sk-[A-Za-z0-9_\-]{20,}$", clip):
                import webbrowser
                webbrowser.open("https://platform.openai.com/api-keys")
                return outcome.done("deep_think_add_key", step="copy the key",
                                    note="tell the user: on the page that opened, create a key and press Copy, "
                                         "then say 'add this OpenAI key' again; they never need to say or type it")
            try:
                model = deepthink.add_key(clip)
            except deepthink.DeepError as e:
                return outcome.failed("deep_think_add_key", str(e))
            try:
                import pyperclip; pyperclip.copy("")
            except Exception:
                pass
            return outcome.done("deep_think_add_key", keys=len(deepthink.keys()), model=model,
                                note="the key was checked and saved; the clipboard was cleared")

        if action == "remove_keys":
            return outcome.done("deep_think_remove", removed=deepthink.clear_keys())

        if action == "set_limit":
            n = int(parameters.get("limit") or 0)
            if not 1 <= n <= 500:
                return outcome.ask("deep_think_limit", "How many deep-thinking calls a day, between 1 and 500?")
            from memory.config_manager import get_plugin_config, save_plugin_config
            cfg = get_plugin_config(deepthink.NAMESPACE); cfg["daily_calls"] = n
            save_plugin_config(deepthink.NAMESPACE, cfg)
            return outcome.done("deep_think_limit", per_day=n)

        lines = deepthink.status_lines()
        return outcome.done("deep_think_status") + "\n" + outcome.untrusted("deep_think", "\n".join(lines))
    except Exception as e:
        return outcome.failed(f"deep_think_{action}", str(e)[:200])


def _claude_possible() -> bool:
    try:
        from providers.llm_claude_code import find_claude
        return find_claude("") is not None
    except Exception:
        return False
