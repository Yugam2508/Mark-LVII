"""
plugins/_writing.py — the writing voice: one place that turns a request into
well-written text, used by the writer, notes and proactive plugins.

WHICH MODEL WRITES
    The voice model (Gemini Live) is chosen for speed. Writing is the opposite
    trade: nobody minds three seconds if the email is right. So writing goes to
    the best writer configured, in this order (⚙ → PLUGIN SETTINGS → WRITING VOICE
    can force one):

        claude_code  Claude through Claude Code — your Claude subscription, no key
        anthropic    Claude through an API key, if one is set up
        gemini       the app's own model ladder (always there)

    If the first choice fails — not signed in, usage limit, no connection — the
    next one writes instead, and the result says which one did.

THE STYLE GUIDE
    A short description of how you write ("casual, short sentences, sign off as
    Yugam, British spelling") lives in the same settings section and is given to
    every writer, along with the name you gave JARVIS for yourself.
"""
from __future__ import annotations

from memory.config_manager import get_plugin_setting

NAMESPACE = "writing"
ENGINES = ("auto", "claude_code", "anthropic", "gemini")

WRITER_SYSTEM = """You write on behalf of {name}. Your text will be sent or saved as it is, so:
- Output ONLY the finished text — no preamble, no notes, no "Here is your draft",
  no surrounding quotes, no markdown unless the format needs it.
- For an email, output the subject on the first line as "Subject: ..." then a
  blank line, then the body. Omit the subject when replying.
- Sound like a real person, not an assistant: plain words, no filler, no
  clichés ("I hope this email finds you well"), no exclamation marks unless the
  request is clearly excited. Match the length to the purpose; shorter is usually better.
- Never invent facts, times, numbers or promises that are not in the request. If
  something essential is missing, leave a clear placeholder like [time].
{style}"""


def _style_block() -> str:
    style = str(get_plugin_setting(NAMESPACE, "style_guide", "") or "").strip()
    sign = str(get_plugin_setting(NAMESPACE, "sign_off", "") or "").strip()
    lines = []
    if style:
        lines.append(f"- The writer's own style: {style}")
    if sign:
        lines.append(f"- Sign emails and letters as: {sign}")
    return "\n".join(lines)


def _user_name() -> str:
    try:
        from memory.config_manager import get_user_name
        return get_user_name() or "the user"
    except Exception:
        return "the user"


def system_prompt() -> str:
    return WRITER_SYSTEM.format(name=_user_name(), style=_style_block())


def _order() -> list[str]:
    choice = str(get_plugin_setting(NAMESPACE, "engine", "auto") or "auto")
    rest = ["claude_code", "anthropic", "gemini"]
    if choice in rest:
        return [choice] + [e for e in rest if e != choice]
    return rest


def _via_provider(pid: str, system: str, prompt: str, timeout: float) -> str:
    from memory.config_manager import get_provider_config
    from providers import registry
    cfg = {**registry.defaults(pid), **(get_provider_config(pid) or {})}
    if pid == "anthropic" and not str(cfg.get("api_key") or "").strip():
        raise RuntimeError("no Anthropic API key is set up")
    if pid == "claude_code":
        from providers.llm_claude_code import find_claude
        if find_claude(str(cfg.get("claude_path") or "")) is None:
            raise RuntimeError("Claude Code is not installed")
    llm = registry.build(pid, cfg)
    if llm is None:
        raise RuntimeError(f"provider {pid} is not available")
    text, _ = llm.complete([{"role": "system", "content": system},
                            {"role": "user", "content": prompt}], timeout=timeout)
    return text


def _via_gemini(system: str, prompt: str, timeout: float) -> str:
    from core import gemini
    return gemini.text(f"{system}\n\n---\n\n{prompt}", tier=gemini.SMART,
                       timeout_ms=int(timeout * 1000))


def write(prompt: str, *, system: str | None = None, timeout: float = 120.0) -> tuple[str, str]:
    """(text, engine that wrote it). Raises RuntimeError only if every engine failed."""
    system = system or system_prompt()
    errors = []
    for engine in _order():
        try:
            text = (_via_gemini(system, prompt, timeout) if engine == "gemini"
                    else _via_provider(engine, system, prompt, timeout))
            text = (text or "").strip()
            if text:
                return text, engine
            errors.append(f"{engine}: empty answer")
        except Exception as e:  # try the next writer
            errors.append(f"{engine}: {e}")
    raise RuntimeError("no writer answered — " + "; ".join(errors))


def split_subject(text: str) -> tuple[str, str]:
    """('subject', 'body') from a draft that may start with 'Subject: ...'."""
    lines = text.strip().splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        return lines[0].split(":", 1)[1].strip(), "\n".join(lines[1:]).strip()
    return "", text.strip()


def _test(values: dict) -> tuple[bool, str]:
    from memory.config_manager import save_plugin_config
    save_plugin_config(NAMESPACE, values)
    try:
        text, engine = write("Write a one-line text message telling a friend I'm running "
                             "five minutes late.", timeout=90)
    except RuntimeError as e:
        return False, str(e)[:200]
    return True, f"{engine} wrote: {text[:120]}"


PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "WRITING VOICE",
    "fields": [
        {"key": "engine", "label": "Who writes (auto = Claude Code, then Claude API, then Gemini)",
         "type": "choice", "options": list(ENGINES), "default": "auto"},
        {"key": "style_guide", "label": "How you write — tone, length, spelling, habits",
         "type": "text", "placeholder": "casual, short sentences, no emojis, British spelling"},
        {"key": "sign_off", "label": "Sign emails as", "type": "text", "placeholder": "Yugam"},
    ],
    "action": {"label": "TRY IT", "run": _test},
}
