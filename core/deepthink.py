"""
core/deepthink.py — a second, stronger mind for the questions that deserve it.

Jarvis answers most things with fast models. When a question needs real reasoning, or when
neither of you trusts the quick answer, it hands the question — with the conversation and your
two always-on memory boxes — to a deeper model and brings the result back.

Who decides: Jarvis itself (the prompt tells it when) or you, in ordinary speech ("that doesn't
sound right", "are you sure?", "think about it more"). plugins/deep_think.py is the tool it calls.

Backends, tried in your preferred order:
    openai   one or more OpenAI API keys. Each key's strongest usable model is found by asking
             OpenAI what that key can use (and Gemini to pick the strongest, with a rule-based
             fallback). Works with both OpenAI endpoints, because some of the strongest models
             are only on /v1/responses. When a key runs out of credit or is refused, the next
             key is used; a key that merely hit a rate limit rests for a minute.
    claude   your Claude subscription through Claude Code (no API key).

Keys are stored like every other credential in config/api_keys.json and are never logged,
spoken or sent to a model. Usage (calls and tokens, not money — prices change) is counted per day.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

NAMESPACE = "deepthink"
OPENAI_BASE = "https://api.openai.com/v1"
_lock = threading.Lock()
_rest: dict[str, float] = {}            # key id -> time it may be tried again
_bad_models: set[str] = set()           # "keyid:model" pairs this key can't call
_down_until = 0.0                       # every backend failed: don't hammer them until then
_down_reason = ""
_DOWN_FOR = 300.0
MAX_KEYS = 5
_REST_RATE = 60.0
_REST_EMPTY = 6 * 3600.0
_NOT_CHAT = re.compile(r"embed|tts|whisper|dall|image|audio|realtime|moderation|transcribe|search|"
                       r"davinci|babbage|computer|codex|instruct|vision-preview|sora|omni-moderation", re.I)


class DeepError(RuntimeError):
    pass


# ── settings ──────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    from memory.config_manager import get_plugin_config
    return get_plugin_config(NAMESPACE) or {}


def _save(cfg: dict) -> None:
    from memory.config_manager import save_plugin_config
    save_plugin_config(NAMESPACE, cfg)


def base_url() -> str:
    return str(_cfg().get("openai_base") or OPENAI_BASE).rstrip("/")


def keys() -> list[str]:
    return [k for k in (_cfg().get("openai_keys") or []) if isinstance(k, str) and k]


def key_id(key: str) -> str:
    return "…" + key[-4:]


def preference() -> str:
    p = str(_cfg().get("provider") or "auto").lower()
    return p if p in ("auto", "openai", "claude") else "auto"


def set_preference(p: str) -> str:
    low = (p or "").lower()
    if "claude" in low or "anthropic" in low:
        p = "claude"
    elif any(w in low for w in ("openai", "chatgpt", "gpt")):
        p = "openai"
    elif any(w in low for w in ("auto", "default", "gemini", "back", "normal")):
        p = "auto"
    else:
        raise DeepError("choose openai, claude or auto")
    cfg = _cfg(); cfg["provider"] = p; _save(cfg)
    return p


def set_model(model: str) -> None:
    cfg = _cfg(); cfg["model"] = (model or "").strip(); cfg.pop("models", None); _save(cfg)


def auto_enabled() -> bool:
    """Whether Jarvis may escalate by itself, without being asked (off by default)."""
    return bool(_cfg().get("auto", False))


def daily_cap() -> int:
    try:
        return max(1, int(_cfg().get("daily_calls") or 40))
    except (TypeError, ValueError):
        return 40


# ── keys ──────────────────────────────────────────────────────────────────────

def _http(method: str, url: str, key: str, body: dict | None = None, timeout: float = 120.0):
    import httpx
    return httpx.request(method, url, json=body, timeout=timeout,
                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})


def list_models(key: str) -> list[str]:
    r = _http("GET", base_url() + "/models", key, timeout=20.0)
    if r.status_code in (401, 403):
        raise DeepError("OpenAI refused that key")
    if r.status_code >= 400:
        raise DeepError(f"OpenAI error {r.status_code}")
    return sorted({m.get("id", "") for m in r.json().get("data", []) if m.get("id")})


def rank_models(ids: list[str]) -> list[str]:
    """Strongest-looking chat models first, by rule. Names change, so this only needs to be a
    sensible fallback for when asking Gemini to choose isn't possible."""
    def score(m: str) -> tuple:
        s = m.lower()
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)] or [0.0]
        return (("pro" in s) * 3 + (bool(re.match(r"o\d", s)) or "reason" in s or "think" in s) * 2
                + ("gpt" in s) * 1 - ("mini" in s or "nano" in s or "lite" in s) * 2 - ("preview" in s) * 0.5,
                nums[0], len(s) * -1)
    return sorted((m for m in ids if not _NOT_CHAT.search(m)), key=score, reverse=True)


def choose_model(ids: list[str]) -> str:
    """The strongest model this key can use: ask Gemini to choose from the usable list, falling
    back to the rule above. A model you named yourself always wins."""
    named = str(_cfg().get("model") or "").strip()
    if named:
        return named
    ranked = rank_models(ids)
    if not ranked:
        raise DeepError("that key can't use any chat model")
    try:
        from core import gemini
        data = gemini.as_json(
            "From these OpenAI model ids pick the single strongest one for deep reasoning and "
            "analysis (not a mini/nano/lite model, not embedding, audio or image). Reply with JSON "
            f'only: {{"model": "<id from the list>"}}\n\n{json.dumps(ranked[:40])}', tier=gemini.FAST, timeout_ms=20000)
        pick = str((data or {}).get("model") or "") if isinstance(data, dict) else ""
        if pick in ranked:
            return pick
    except Exception:
        pass
    return ranked[0]


def add_key(key: str) -> str:
    """Validate a key against OpenAI and keep it. Returns the model it will use."""
    key = (key or "").strip()
    if not re.match(r"^sk-[A-Za-z0-9_\-]{20,}$", key):
        raise DeepError("that doesn't look like an OpenAI key")
    existing = keys()
    if key in existing:
        raise DeepError("that key is already added")
    if len(existing) >= MAX_KEYS:
        raise DeepError(f"at most {MAX_KEYS} keys")
    model = choose_model(list_models(key))
    cfg = _cfg()
    cfg["openai_keys"] = existing + [key]
    models = cfg.get("models") or {}
    models[key_id(key)] = model
    cfg["models"] = models
    _save(cfg)
    return model


def clear_keys() -> int:
    cfg = _cfg(); n = len(keys()); cfg["openai_keys"] = []; cfg["models"] = {}; _save(cfg)
    _rest.clear()
    return n


def model_for(key: str) -> str:
    named = str(_cfg().get("model") or "").strip()
    if named:
        return named
    m = (_cfg().get("models") or {}).get(key_id(key))
    if m and f"{key_id(key)}:{m}" not in _bad_models:
        return m
    ids = [i for i in list_models(key) if f"{key_id(key)}:{i}" not in _bad_models]
    m = choose_model(ids)
    cfg = _cfg(); models = cfg.get("models") or {}; models[key_id(key)] = m; cfg["models"] = models; _save(cfg)
    return m


# ── usage ─────────────────────────────────────────────────────────────────────

def _usage_path() -> Path:
    from memory.config_manager import CONFIG_DIR
    return CONFIG_DIR / "deepthink_usage.json"


def usage_today() -> dict:
    try:
        data = json.loads(_usage_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return data.get(time.strftime("%Y-%m-%d"), {"calls": 0, "tokens": 0, "by": {}})


def _note_usage(label: str, tokens: int) -> None:
    with _lock:
        try:
            data = json.loads(_usage_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        today = time.strftime("%Y-%m-%d")
        data = {d: v for d, v in data.items() if d >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))}
        d = data.setdefault(today, {"calls": 0, "tokens": 0, "by": {}})
        d["calls"] += 1
        d["tokens"] += int(tokens or 0)
        d["by"][label] = d["by"].get(label, 0) + 1
        try:
            _usage_path().parent.mkdir(parents=True, exist_ok=True)
            _usage_path().write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass


# ── the backends ──────────────────────────────────────────────────────────────

def _messages(question: str, context: str) -> list[dict]:
    system = ("You are the deeper-reasoning model behind a voice assistant. Think the problem through "
              "carefully and give the user the best-reasoned answer: state your conclusion first, then the "
              "key reasoning and any assumptions or uncertainty. Be concrete and as brief as the problem "
              "allows; it will be summarised aloud and shown in full on screen.")
    user = (f"BACKGROUND (what the assistant knows about the user and the conversation so far):\n{context}\n\n"
            f"THE QUESTION TO THINK DEEPLY ABOUT:\n{question}") if context.strip() else question
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _openai_once(key: str, model: str, msgs: list[dict]) -> tuple[str, int]:
    base = base_url()
    r = _http("POST", base + "/chat/completions", key, {"model": model, "messages": msgs})
    if r.status_code == 400 and ("v1/responses" in r.text or "not supported in the v1/chat" in r.text
                                 or "only supported in" in r.text):
        text = "\n\n".join(m["content"] for m in msgs)
        r = _http("POST", base + "/responses", key, {"model": model, "input": text})
        if r.status_code == 200:
            j = r.json()
            out = j.get("output_text") or "".join(
                c.get("text", "") for item in j.get("output", []) if item.get("type") == "message"
                for c in item.get("content", []))
            return out.strip(), int((j.get("usage") or {}).get("total_tokens") or 0)
    if r.status_code == 200:
        j = r.json()
        return str(j["choices"][0]["message"].get("content") or "").strip(), int((j.get("usage") or {}).get("total_tokens") or 0)
    raise _classify(r.status_code, r.text)


class _KeyProblem(DeepError):
    def __init__(self, msg: str, rest: float):
        super().__init__(msg); self.rest = rest


class _ModelProblem(DeepError):
    """This key can't call this model; another model on the same key may work."""


def _api_message(text: str) -> str:
    try:
        return str((json.loads(text).get("error") or {}).get("message") or "")[:200]
    except Exception:
        return text[:200]


def _classify(status: int, text: str) -> Exception:
    low = text.lower()
    msg = _api_message(text)
    if status in (401, 403) and ("model" in low and ("access" in low or "does not have" in low)):
        return _ModelProblem(f"no access to that model ({msg})")
    if status in (401, 403):
        return _KeyProblem(f"the key was refused ({msg})", _REST_EMPTY)
    if status == 402 or "insufficient_quota" in low or "exceeded your current quota" in low:
        return _KeyProblem(f"out of credit ({msg})", _REST_EMPTY)
    if status == 404 or "does not exist" in low or "model_not_found" in low:
        return _ModelProblem(f"that model isn't available to this key ({msg})")
    if status == 429:
        return _KeyProblem(f"rate limited ({msg})", _REST_RATE)
    return DeepError(f"OpenAI error {status}: {msg}")


def _via_openai(question: str, context: str) -> tuple[str, str]:
    ks = keys()
    if not ks:
        raise DeepError("no OpenAI key is set up")
    msgs = _messages(question, context)
    tried, last = 0, "no key is available"
    for key in ks:
        if time.time() < _rest.get(key_id(key), 0):
            continue
        tried += 1
        try:
            text = ""
            for _ in range(4):                    # a model this key can't call: try the next one
                model = model_for(key)
                try:
                    text, tokens = _openai_once(key, model, msgs)
                    break
                except _ModelProblem as e:
                    _bad_models.add(f"{key_id(key)}:{model}")
                    last = f"key {key_id(key)}, {model}: {e}"
                    if str(_cfg().get("model") or "").strip():
                        break                     # a model you named yourself isn't swapped
        except _KeyProblem as e:
            _rest[key_id(key)] = time.time() + e.rest
            last = f"key {key_id(key)}: {e}"
            continue
        except DeepError as e:
            last = f"key {key_id(key)}: {e}"
            continue
        if not text:
            last = "it returned nothing"
            continue
        _note_usage(f"openai:{model}", tokens)
        return text, model
    raise DeepError(f"OpenAI keys unavailable ({last})" if tried else
                    "every OpenAI key is resting (out of credit or rate limited); try again soon")


def _via_claude(question: str, context: str) -> tuple[str, str]:
    from providers.llm_claude_code import ClaudeCodeLLM
    cfg = {"model": str(_cfg().get("claude_model") or "opus"), "effort": "high", "timeout": 300}
    text, _ = ClaudeCodeLLM(cfg).complete(_messages(question, context))
    if not text:
        raise DeepError("Claude returned nothing")
    _note_usage(f"claude:{cfg['model']}", 0)
    return text, f"Claude {cfg['model']}"


def think(question: str, context: str = "") -> tuple[str, str]:
    """(answer, label of the model that answered). Raises DeepError if every backend failed."""
    global _down_until, _down_reason
    if time.time() < _down_until:
        raise DeepError(f"deep thinking is unavailable for a few minutes ({_down_reason})")
    used = usage_today()["calls"]
    if used >= daily_cap():
        raise DeepError(f"today's deep-thinking limit ({daily_cap()} calls) is used up; say "
                        "'raise the deep thinking limit' to change it")
    pref = preference()
    order = {"openai": ["openai", "claude"], "claude": ["claude", "openai"],
             "auto": ["openai", "claude"] if keys() else ["claude", "openai"]}[pref]
    errors = []
    for backend in order:
        if backend == "openai" and not keys():
            continue
        try:
            text, model = (_via_openai if backend == "openai" else _via_claude)(question, context)
            return text, model
        except Exception as e:
            errors.append(f"{backend}: {str(e)[:120]}")
    _down_reason = "; ".join(errors)[:300]
    if errors:
        _down_until = time.time() + _DOWN_FOR
    raise DeepError("; ".join(errors) or "no deep-thinking model is set up yet")


def status_lines() -> list[str]:
    u = usage_today()
    ks = keys()
    out = [f"Preferred: {preference()}",
           f"OpenAI keys: {len(ks)}" + ("".join(f"\n  {key_id(k)}: {_cfg().get('model') or (_cfg().get('models') or {}).get(key_id(k), 'model not chosen yet')}"
                                                 + (" (resting)" if time.time() < _rest.get(key_id(k), 0) else "") for k in ks)),
           f"Today: {u['calls']} of {daily_cap()} calls, {u['tokens']} tokens"]
    for label, n in sorted(u.get("by", {}).items()):
        out.append(f"  {label}: {n}")
    return out
