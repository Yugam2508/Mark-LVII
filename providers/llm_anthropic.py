"""
Claude, through Anthropic's own API — as the brain of the pipeline engine, or as
the model behind background requests.

WHERE IT FITS
    Gemini Live is one socket that hears, thinks and speaks. Claude does the
    thinking only, so choosing it means the PIPELINE engine: speech recognition
    (Whisper, on this computer) -> Claude -> a voice (Piper, the system voice or
    ElevenLabs). ⚙ → ENGINE & PROVIDERS: pick "Claude" as the language model.
    It can also serve as the sidecar provider, so research, summaries and other
    background calls go to Claude while the voice stays on Gemini Live.

WHY A SEPARATE FILE AND NOT AN OPENAI-COMPATIBLE PRESET
    Claude's tool calls and its reasoning come back as typed content blocks, and
    the reasoning ("thinking") blocks must be handed back unchanged on the next
    request of the same conversation. The pipeline keeps its history in the
    OpenAI chat shape, which has nowhere to put them. So this provider:

      * converts the OpenAI-shaped history the engine sends into Claude's shape;
      * remembers the exact content of every reply it produced, keyed by its
        tool-call ids (or its text), and puts those blocks back in place of the
        converted copy, so Claude's reasoning survives a tool round trip;
      * sends `prefix_mismatch_behavior: "drop_block"`, because the pipeline
        trims old turns off the front of long conversations. Trimming changes
        what came before a reasoning block, and Claude's API refuses an edited
        history unless it is told to drop the reasoning it can no longer verify.
        With the setting, an old block is dropped and the turn carries on.

THE SDK IS INSTALLED ON DEMAND
    `anthropic` is not in requirements.txt: nobody who never picks Claude pays
    for it. The panel's INSTALL button installs it ("install" below), and like
    every provider it is imported inside the factory, never at module scope.

COSTS
    Claude is billed per use (console.anthropic.com). Effort defaults to "low",
    which keeps spoken replies quick and cheap; raise it for harder questions.
"""
from __future__ import annotations

import json
import re
from importlib.util import find_spec
from typing import Any, AsyncIterator

from .base import DEFAULT_CAPS, Field, FunctionCall

MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
EFFORTS = ("low", "medium", "high")

# Beta features this provider uses:
#   server-side-fallback  — if Claude declines on safety grounds, the API retries
#                           the request on a fallback model instead of failing.
#                           Not available for Haiku.
#   thinking-binding      — lets us send drop_block (see the module docstring).
_BETA_FALLBACK = "server-side-fallback-2026-07-01"
_BETA_BINDING = "thinking-binding-controls-2026-08-01"

_REFUSAL_LINE = "Sorry, I can't help with that one."


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _dump(block: Any) -> dict:
    """An SDK content block as a plain dict that can be sent back unchanged."""
    if isinstance(block, dict):
        return block
    return block.model_dump(mode="json", exclude_none=True)


def _image_from_data_uri(url: str) -> dict | None:
    m = re.match(r"^data:([^;]+);base64,(.*)$", url or "", re.S)
    if not m:
        return {"type": "image", "source": {"type": "url", "url": url}} if url else None
    return {"type": "image", "source": {"type": "base64", "media_type": m.group(1),
                                        "data": m.group(2)}}


def _user_content(content: Any) -> list[dict]:
    """OpenAI user content (a string or a list of parts) -> Claude blocks."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content.strip() else []
    blocks: list[dict] = []
    for part in content or []:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and str(part.get("text", "")).strip():
            blocks.append({"type": "text", "text": part["text"]})
        elif part.get("type") == "image_url":
            img = _image_from_data_uri((part.get("image_url") or {}).get("url", ""))
            if img:
                blocks.append(img)
    return blocks


class ClaudeLLM:
    def __init__(self, cfg: dict):
        import anthropic  # inside the factory path — never at module scope

        self._anthropic = anthropic
        self.key = (cfg.get("api_key") or "").strip()
        self.model = (cfg.get("model") or MODELS[0]).strip()
        self.effort = (cfg.get("effort") or "low").strip()
        self.timeout = float(cfg.get("timeout") or 60.0)
        self.caps = dict(DEFAULT_CAPS)
        self.caps.update({"tools": True, "tool_format": "anthropic", "vision": True,
                          "max_tools": None})
        # Replies this instance produced, so they can be replayed unchanged.
        self._by_calls: dict[frozenset, list[dict]] = {}
        self._by_text: dict[str, list[dict]] = {}

    # -- clients -------------------------------------------------------------
    def _client_kwargs(self, timeout: float | None) -> dict:
        kw: dict = {"timeout": timeout or self.timeout, "max_retries": 2}
        if self.key:
            kw["api_key"] = self.key
        return kw

    # -- request shape -------------------------------------------------------
    def _convert(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI-shaped history -> (system, Claude messages)."""
        system_parts: list[str] = []
        out: list[dict] = []

        def add(role: str, blocks: list[dict]) -> None:
            if not blocks:
                return
            if out and out[-1]["role"] == role:
                out[-1]["content"].extend(blocks)
            else:
                out.append({"role": role, "content": list(blocks)})

        for m in messages:
            role = m.get("role")
            if role == "system":
                if str(m.get("content") or "").strip():
                    system_parts.append(str(m["content"]))
            elif role == "user":
                add("user", _user_content(m.get("content")))
            elif role == "tool":
                add("user", [{"type": "tool_result",
                              "tool_use_id": str(m.get("tool_call_id") or m.get("name") or ""),
                              "content": str(m.get("content") or "")}])
            elif role == "assistant":
                calls = m.get("tool_calls") or []
                ids = frozenset(str(c.get("id")) for c in calls)
                stored = (self._by_calls.get(ids) if calls
                          else self._by_text.get(_norm(m.get("content") or "")))
                if stored is not None:
                    add("assistant", [dict(b) for b in stored])
                    continue
                blocks: list[dict] = []
                if str(m.get("content") or "").strip():
                    blocks.append({"type": "text", "text": m["content"]})
                for c in calls:
                    fn = c.get("function") or {}
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    blocks.append({"type": "tool_use", "id": str(c.get("id")),
                                   "name": fn.get("name", ""), "input": args})
                add("assistant", blocks)

        # A trimmed history can start on an assistant turn; Claude needs a user first.
        while out and out[0]["role"] != "user":
            out.pop(0)
        return "\n\n".join(system_parts), out

    def _params(self, messages: list[dict], tools: list[dict] | None,
                max_tokens: int) -> dict:
        system, msgs = self._convert(messages)
        if not msgs:
            msgs = [{"role": "user", "content": [{"type": "text", "text": "Hello."}]}]
        betas = [_BETA_BINDING]
        params: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": msgs,
            "thinking": {"type": "adaptive",
                         "block_binding": {"prefix_mismatch_behavior": "drop_block"}},
            "output_config": {"effort": self.effort},
            # The system prompt and tool list are the same every turn: cache them.
            "cache_control": {"type": "ephemeral"},
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = tools
        if "haiku" not in self.model:
            betas.append(_BETA_FALLBACK)
            params["fallbacks"] = "default"
        params["betas"] = betas
        return params

    def _remember(self, content: list) -> tuple[str, list[FunctionCall]]:
        blocks = [_dump(b) for b in content]
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        calls = [FunctionCall(id=b["id"], name=b["name"], args=dict(b.get("input") or {}))
                 for b in blocks if b.get("type") == "tool_use"]
        if calls:
            self._by_calls[frozenset(c.id for c in calls)] = blocks
        elif text:
            self._by_text[_norm(text)] = blocks
        return text, calls

    # -- one-shot, synchronous: core/gemini.py's ladder uses this ------------
    def complete(self, messages: list[dict], tools: list[dict] | None = None,
                 *, timeout: float | None = None,
                 temperature: float | None = None) -> tuple[str, list[FunctionCall]]:
        """Text and any tool calls. Raises on failure so the ladder can classify
        it. `temperature` is accepted for the interface and ignored: current
        Claude models do not take sampling parameters."""
        client = self._anthropic.Anthropic(**self._client_kwargs(timeout))
        resp = client.beta.messages.create(**self._params(messages, tools, 16000))
        if resp.stop_reason == "refusal":
            return _REFUSAL_LINE, []
        return self._remember(resp.content)

    # -- streaming, async: the pipeline engine uses this ---------------------
    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   *, stream: bool = True,
                   temperature: float | None = None) -> AsyncIterator[dict]:
        """Yields {"text": ...} as Claude writes and one {"tool_calls": [...]} at
        the end, the same contract as the OpenAI-compatible provider."""
        client = self._anthropic.AsyncAnthropic(**self._client_kwargs(None))
        params = self._params(messages, tools, 16000)
        if not stream:
            resp = await client.beta.messages.create(**params)
            if resp.stop_reason == "refusal":
                yield {"text": _REFUSAL_LINE}
                return
            text, calls = self._remember(resp.content)
            if text:
                yield {"text": text}
            if calls:
                yield {"tool_calls": calls}
            return

        async with client.beta.messages.stream(**params) as s:
            async for event in s:
                if (event.type == "content_block_delta"
                        and getattr(event.delta, "type", "") == "text_delta"):
                    yield {"text": event.delta.text}
            final = await s.get_final_message()
        if final.stop_reason == "refusal":
            yield {"text": " " + _REFUSAL_LINE}
            return
        _text, calls = self._remember(final.content)
        if calls:
            yield {"tool_calls": calls}

    # -- the settings panel ---------------------------------------------------
    def models(self, timeout: float = 8.0) -> list[str]:
        return list(MODELS)

    def probe(self, check_vision: bool = False) -> tuple[bool, str]:
        import time
        if not self.key:
            return False, "Paste your Anthropic API key first."
        t0 = time.monotonic()
        try:
            text, _ = self.complete(
                [{"role": "user", "content": "Reply with the single word: ok"}],
                timeout=30.0)
        except self._anthropic.AuthenticationError:
            return False, "Anthropic refused the key."
        except self._anthropic.NotFoundError:
            return False, f"No model called '{self.model}'."
        except self._anthropic.RateLimitError:
            return False, "Rate limited — check your plan or try again in a minute."
        except self._anthropic.APIConnectionError:
            return False, "Could not reach api.anthropic.com."
        except self._anthropic.APIStatusError as e:
            return False, f"Anthropic error {e.status_code}: {str(e)[:80]}"
        return True, f"Answered in {time.monotonic() - t0:.2f}s  |  can see images"


def _make(cfg: dict) -> ClaudeLLM:
    return ClaudeLLM(cfg)


PROVIDER = {
    "id": "anthropic",
    "kind": "llm",
    "label": "Claude (Anthropic)",
    "hint": "Claude Opus 5.5 · Sonnet 5.5 · Haiku 5.5 — needs an API key from console.anthropic.com",
    "requires": ("anthropic",),
    "install": "anthropic>=2.13.0",
    "needs": (
        Field("api_key", "API key", kind="secret",
              hint="console.anthropic.com → Settings → API Keys"),
        Field("model", "Model", kind="choice", choices=MODELS, default=MODELS[0],
              hint="Opus = smartest · Sonnet = balanced · Haiku = fastest and cheapest"),
        Field("effort", "Effort", kind="choice", choices=EFFORTS, default="low",
              hint="low = quickest spoken replies · high = more careful on hard questions"),
    ),
    "caps": {"tools": True, "tool_format": "anthropic", "vision": True},
    "factory": _make,
}


def available() -> bool:
    return all(find_spec(m) is not None for m in PROVIDER["requires"])
