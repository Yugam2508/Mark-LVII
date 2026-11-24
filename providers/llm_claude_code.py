"""
Claude through Claude Code — uses your Claude subscription, no API key.

WHAT THIS IS
    Claude Code (the `claude` command) has a print mode, `claude -p`, that answers
    one prompt and exits. Signed in with a Claude Pro or Max account, it draws on
    that subscription's usage limits instead of a pay-per-use API key. This
    provider runs it as a plain text model:

        claude -p --output-format json --tools "" --system-prompt-file <file>
               --no-session-persistence --strict-mcp-config --disable-slash-commands

    * `--tools ""` — no tools at all: it cannot read, edit or run anything on this
      computer. It only writes text.
    * the prompt goes in on stdin and the system prompt in a file, so Windows'
      8,191-character command-line limit never truncates a long request, and no
      user text is ever parsed as a command-line argument;
    * ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN are removed from its environment,
      so it signs in with your Claude account rather than billing an API key;
    * it runs in an empty folder of its own, so no project instructions
      (CLAUDE.md) are picked up.

WHERE IT FITS
    Each call starts a process, which takes a second or more before the first
    word — fine for background work (research, summaries, writing emails and
    documents, the writing voice) and too slow for back-and-forth speech. Keep
    Gemini Live as the voice and choose this as the provider for background
    requests in ⚙ → ENGINE & PROVIDERS. If you do pick it as the pipeline's
    language model it works, with tools described in the prompt
    (`tool_format: "prompt"`), just slowly.

SETUP (once per computer)
    Install Claude Code (https://claude.com/claude-code — on Windows, PowerShell:
    `irm https://claude.ai/install.ps1 | iex`), run `claude` once and log in with
    your Claude account, then TEST here.

    Usage counts against the same limits as your Claude chats and Claude Code.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import AsyncIterator

from .base import DEFAULT_CAPS, Field, FunctionCall

MODELS = ("sonnet", "opus", "haiku")
EFFORTS = ("low", "medium", "high")
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0   # CREATE_NO_WINDOW
_LOGIN_HINT = ("Claude Code is not signed in. Open a terminal, run `claude`, log in with "
               "your Claude account, then press TEST again.")


def find_claude(configured: str = "") -> str | None:
    """The `claude` executable: the configured path, PATH, then the usual installs."""
    if configured and Path(configured).expanduser().is_file():
        return str(Path(configured).expanduser())
    found = shutil.which("claude")
    if found:
        return found
    home = Path.home()
    candidates = [home / ".local" / "bin" / ("claude.exe" if sys.platform == "win32" else "claude")]
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "npm" / "claude.cmd")
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def _render(messages: list[dict]) -> tuple[str, str]:
    """OpenAI-shaped messages -> (system prompt, one prompt for stdin)."""
    system = "\n\n".join(str(m.get("content") or "") for m in messages
                         if m.get("role") == "system" and m.get("content"))
    turns = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        content = m.get("content")
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict) and p.get("type") == "text":
                    parts.append(str(p.get("text", "")))
                elif isinstance(p, dict) and p.get("type") == "image_url":
                    parts.append("[an image was attached here; it cannot be shown to you]")
            content = "\n".join(parts)
        content = str(content or "")
        if role == "assistant" and m.get("tool_calls"):
            calls = "; ".join(f"{c.get('function', {}).get('name')}"
                              f"({c.get('function', {}).get('arguments', '')})"
                              for c in m["tool_calls"])
            content = (content + f"\n[called tools: {calls}]").strip()
        if role == "tool":
            turns.append(f"Tool result ({m.get('name', 'tool')}):\n{content}")
        elif content.strip():
            turns.append(f"{'User' if role == 'user' else 'Assistant'}: {content}")
    if len(turns) == 1 and turns[0].startswith("User: "):
        return system, turns[0][len("User: "):]
    prompt = ("The conversation so far is below. Write the assistant's next reply only, "
              "without a speaker label.\n\n" + "\n\n".join(turns))
    return system, prompt


class ClaudeCodeLLM:
    def __init__(self, cfg: dict):
        self.model = (cfg.get("model") or MODELS[0]).strip()
        self.effort = (cfg.get("effort") or "low").strip()
        self.path_setting = str(cfg.get("claude_path") or "").strip()
        self.timeout = float(cfg.get("timeout") or 180.0)
        self.caps = dict(DEFAULT_CAPS)
        # No native tool calling through `claude -p` with tools off; the pipeline
        # engine describes tools in the prompt and parses a JSON reply instead.
        self.caps.update({"tools": True, "tool_format": "prompt", "vision": False,
                          "max_tools": 14})
        self._workdir = Path(tempfile.gettempdir()) / "jarvis_claude_code"

    # -- the one call ------------------------------------------------------------
    def complete(self, messages: list[dict], tools: list[dict] | None = None,
                 *, timeout: float | None = None,
                 temperature: float | None = None) -> tuple[str, list[FunctionCall]]:
        """Text only. Raises on failure so core/gemini.py's ladder can classify it."""
        exe = find_claude(self.path_setting)
        if exe is None:
            raise RuntimeError("404 Claude Code is not installed (the `claude` command "
                               "was not found)")
        system, prompt = _render(messages)
        self._workdir.mkdir(parents=True, exist_ok=True)
        sys_file = self._workdir / f"system_{os.getpid()}_{time.monotonic_ns()}.txt"
        sys_file.write_text(system or "You are a helpful assistant.", encoding="utf-8")
        args = [exe, "-p", "--output-format", "json", "--tools", "",
                "--system-prompt-file", str(sys_file), "--no-session-persistence",
                "--strict-mcp-config", "--disable-slash-commands",
                "--model", self.model, "--effort", self.effort]
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        try:
            proc = subprocess.run(args, input=prompt, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env,
                                  cwd=str(self._workdir), timeout=timeout or self.timeout,
                                  creationflags=_NO_WINDOW)
        except subprocess.TimeoutExpired:
            raise RuntimeError("504 Claude Code did not answer in time") from None
        finally:
            sys_file.unlink(missing_ok=True)

        out = (proc.stdout or "").strip()
        data = None
        for line in reversed(out.splitlines()):   # the JSON result is the last line
            try:
                data = json.loads(line)
                break
            except ValueError:
                continue
        if data is None:
            detail = " ".join((proc.stderr or out or "no output").split())[:200]
            if any(s in detail.lower() for s in ("login", "log in", "not logged",
                                                  "authenticat", "api key")):
                raise RuntimeError(f"401 {_LOGIN_HINT}")
            raise RuntimeError(f"500 Claude Code failed: {detail}")
        if data.get("is_error"):
            text = str(data.get("result") or data.get("error") or "unknown error")
            if any(s in text.lower() for s in ("login", "log in", "authenticat", "api key")):
                raise RuntimeError(f"401 {_LOGIN_HINT}")
            if "limit" in text.lower():
                raise RuntimeError(f"429 Claude usage limit reached: {text[:150]}")
            raise RuntimeError(f"500 Claude Code error: {text[:200]}")
        return str(data.get("result") or "").strip(), []

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   *, stream: bool = True,
                   temperature: float | None = None) -> AsyncIterator[dict]:
        """The whole answer at once (print mode does not stream text here)."""
        text, _ = await asyncio.to_thread(self.complete, messages, tools)
        if text:
            yield {"text": text}

    # -- the settings panel ---------------------------------------------------------
    def models(self, timeout: float = 8.0) -> list[str]:
        return list(MODELS)

    def probe(self, check_vision: bool = False) -> tuple[bool, str]:
        exe = find_claude(self.path_setting)
        if exe is None:
            return False, ("Claude Code is not installed. In PowerShell run: "
                           "irm https://claude.ai/install.ps1 | iex — then run `claude` "
                           "once and log in.")
        t0 = time.monotonic()
        try:
            text, _ = self.complete([{"role": "user",
                                      "content": "Reply with the single word: ok"}], timeout=90)
        except RuntimeError as e:
            msg = str(e)
            return False, msg[4:] if msg[:3].isdigit() else msg
        return True, f"Answered in {time.monotonic() - t0:.1f}s using your Claude account ✓"


def _make(cfg: dict) -> ClaudeCodeLLM:
    return ClaudeCodeLLM(cfg)


PROVIDER = {
    "id": "claude_code",
    "kind": "llm",
    "label": "Claude (your subscription, via Claude Code)",
    "hint": "No API key: uses the Claude account you log in to Claude Code with. "
            "Best for background work and writing; too slow for live speech.",
    "requires": (),
    "needs": (
        Field("model", "Model", kind="choice", choices=MODELS, default=MODELS[0],
              hint="sonnet = balanced · opus = smartest, uses more of your limit · haiku = quickest"),
        Field("effort", "Effort", kind="choice", choices=EFFORTS, default="low",
              hint="low = quickest · high = more careful"),
        Field("claude_path", "Path to claude (only if not found)", kind="path",
              required=False, advanced=True,
              hint=r"e.g. C:\Users\you\.local\bin\claude.exe"),
    ),
    "caps": {"tools": True, "tool_format": "prompt"},
    "factory": _make,
}


def available() -> bool:
    return find_claude() is not None
