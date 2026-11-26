"""
plugins/operations.py — "What are you working on?" / "Stop that." / "Cancel the install."

One view of everything Jarvis is doing in the background — jobs in core/ops.py (installs, updates, deep
thinking, speed tests, dictation, backups, the file index), Claude Code jobs and background agent tasks —
and one way to stop any of them by name. Makes the agent something you can see and steer, not a black box.
"""
from __future__ import annotations

from core import ops, outcome


def _claude_jobs() -> list[dict]:
    try:
        from plugins import claude_code
        return [j for j in list(claude_code._jobs) if j.get("state") == "running"]
    except Exception:
        return []


def _agent_tasks() -> list[dict]:
    try:
        from core.tasks import ACTIVE, desktop
        eng = desktop.ensure(None)
        return [t for t in eng.list(20) if t.get("status") in ACTIVE]
    except Exception:
        return []


def listing() -> list[str]:
    rows = [o.line() for o in ops.recent()]
    rows += [f"Claude Code in {j.get('project')}: {str(j.get('task'))[:60]} (running)" for j in _claude_jobs()]
    rows += [f"Agent task: {str(t.get('task'))[:60]} ({t.get('status')})" for t in _agent_tasks()]
    return rows


def stop(what: str) -> list[str]:
    """Stop whatever matches; returns what was stopped (and what couldn't be)."""
    q = (what or "").lower()
    said = []
    for o in ops.find(what):
        said.append(f"stopped {o.name}" if o.cancel() else f"{o.name} can't be stopped half-way")
    if not said or "claude" in q or q in ("all", "everything"):
        for j in _claude_jobs():
            if not q or q in ("all", "everything", "that", "it", "last") or "claude" in q or q in str(j.get("task", "")).lower():
                from plugins import claude_code
                if claude_code.stop(j):
                    said.append(f"stopped Claude Code in {j.get('project')}")
    if not said or "agent" in q or "task" in q or q in ("all", "everything"):
        for t in _agent_tasks():
            if not q or q in ("all", "everything", "that", "it", "last") or "agent" in q or "task" in q \
                    or any(w in str(t.get("task", "")).lower() for w in q.split() if len(w) > 3):
                try:
                    from core.tasks import desktop
                    if desktop.ensure(None).cancel(t["id"]):
                        said.append(f"stopped the agent task '{str(t.get('task'))[:40]}'")
                except Exception:
                    pass
    return said


PLUGIN = {
    "name": "operations",
    "description": (
        "What Jarvis is doing in the background right now, and stopping it: list for 'what are you working "
        "on', 'what's running', 'status of my jobs'; stop (what = a few words naming the job, or 'all', or "
        "'that' for the latest) for 'stop that', 'cancel the install', 'stop everything'. Covers installs, "
        "updates, deep thinking, speed tests, dictation, backups, Claude Code jobs and agent tasks."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["list", "stop"]},
            "what": {"type": "STRING", "description": "For stop: which job, in the user's words; 'all' or 'that'"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Background jobs: list / stop.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    try:
        if action == "stop":
            said = stop(str(parameters.get("what") or "that"))
            if not said:
                return outcome.done("operations_stop", stopped=0, note="nothing matching is running")
            return outcome.done("operations_stop", result="; ".join(said))
        rows = listing()
        if player:
            try:
                player.show_content("OPERATIONS", "\n".join(rows) or "Nothing running.")
            except Exception:
                pass
        if not rows:
            return outcome.done("operations", running=0, note="nothing is running in the background")
        return outcome.done("operations", jobs=len(rows)) + "\n" + outcome.untrusted("operations", "\n".join(rows))
    except Exception as e:
        return outcome.failed(f"operations_{action}", str(e)[:160])
