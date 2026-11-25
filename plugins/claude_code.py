"""
plugins/claude_code.py — tell Claude Code what to build, by voice, and hear when it's done.

    "Ask Claude Code to add dark mode to my portfolio site"     run, project=portfolio
    "Have Claude look at why the tests fail in jarvis, just plan" run, permission=plan
    "Go ahead with that plan"                                     approve
    "Tell Claude to also update the README"                       reply
    "What's Claude Code doing?" / "Stop Claude Code"              status / stop
    "Open Claude Code in my thesis folder"                        open_window
    "Which projects do you know?"                                 projects

It drives the Claude Code you are already signed in to on this PC (`claude -p`),
so it uses your Claude subscription — no API key. Each job runs inside one project
folder, in the background; progress goes to the HUD log, and when it finishes
JARVIS tells you (or leaves a card, or pings your phone, if you are busy or away)
and suggests what to do next.

PERMISSIONS — how much Claude Code may do on its own:
    plan    it reads the project and writes a plan; changes nothing. Then
            "go ahead" runs the plan with file edits allowed.
    edits   it may read and edit files in that folder. Shell commands are only
            run if listed in settings (e.g. "npm test, pytest, git status").
    full    no limits, it may run any command. Off unless switched on in
            settings, and every full job asks you to CONFIRM first.
Edits jobs ask you to confirm too (by voice or on screen) unless you switch that
off. Requests coming from the phone cannot confirm — they wait for you.

PROJECTS — named folders. Add them in settings ("site=C:\\Code\\portfolio;
thesis=D:\\Uni\\thesis") or by voice ("add my portfolio project at ..."). Folders
directly inside your code folders (settings; default: ~/Projects, ~/Code,
~/source/repos, ~/Documents/GitHub) are found by name automatically.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from core import addons, outcome
from memory.config_manager import get_plugin_config, get_plugin_setting, save_plugin_config

NAMESPACE = "claude_code"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_lock = threading.Lock()
_jobs: list[dict] = []          # newest last
_MAX_JOBS = 12
_DEFAULT_ROOTS = ("Projects", "Code", "code", "source/repos", "Documents/GitHub", "dev", "repos")
_READ_ONLY_TOOLS = "Read,Grep,Glob,LS,WebSearch,WebFetch,TodoWrite"


# ── settings and projects ─────────────────────────────────────────────────────

def _s(key: str, default):
    v = get_plugin_setting(NAMESPACE, key, default)
    return default if v in (None, "") else v


def _claude() -> str | None:
    try:
        from providers.llm_claude_code import find_claude
        return find_claude(str(_s("claude_path", "")))
    except Exception:
        return shutil.which("claude")


def _named_projects() -> dict[str, str]:
    raw = str(_s("projects", ""))
    out = {}
    for part in re.split(r"[;\n]", raw):
        if "=" in part:
            name, path = part.split("=", 1)
            if name.strip() and path.strip():
                out[name.strip().lower()] = path.strip().strip('"')
    return out


def _roots() -> list[Path]:
    raw = str(_s("code_roots", ""))
    if raw.strip():
        return [Path(p.strip().strip('"')).expanduser() for p in raw.split(";") if p.strip()]
    home = Path.home()
    return [home / r for r in _DEFAULT_ROOTS]


def projects() -> dict[str, str]:
    """name -> folder: the named ones, plus every folder directly inside a code root."""
    found: dict[str, str] = {}
    for root in _roots():
        try:
            for child in sorted(root.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    found.setdefault(child.name.lower(), str(child))
        except OSError:
            continue
    found.update(_named_projects())
    return found


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def resolve_project(name: str) -> tuple[str, str] | None:
    """(name, folder) for a spoken project name or a path."""
    name = (name or "").strip().strip('"')
    if not name:
        last = _jobs[-1] if _jobs else None
        return (last["project"], last["folder"]) if last else None
    p = Path(name).expanduser()
    if p.is_absolute() and p.is_dir():
        return p.name, str(p)
    known = projects()
    key = _norm(name)
    for n, path in known.items():
        if _norm(n) == key:
            return n, path
    for n, path in known.items():         # 'portfolio' finds 'portfolio-site'
        if key and (key in _norm(n) or _norm(n) in key):
            return n, path
    return None


def add_project(name: str, folder: str) -> tuple[bool, str]:
    p = Path(folder.strip().strip('"')).expanduser()
    if not p.is_dir():
        return False, f"there is no folder at {p}"
    named = _named_projects()
    named[name.strip().lower()] = str(p)
    cfg = get_plugin_config(NAMESPACE)
    cfg["projects"] = "; ".join(f"{k}={v}" for k, v in named.items())
    save_plugin_config(NAMESPACE, cfg)
    return True, str(p)


# ── running Claude Code ───────────────────────────────────────────────────────

def _command(exe: str, job: dict) -> list[str]:
    cmd = [exe, "-p", "--output-format", "stream-json", "--verbose"]
    model = str(_s("model", "default"))
    if model != "default":
        cmd += ["--model", model]
    perm = job["permission"]
    if perm == "plan":
        cmd += ["--permission-mode", "plan", "--allowedTools", _READ_ONLY_TOOLS]
    elif perm == "edits":
        cmd += ["--permission-mode", "acceptEdits"]
        allowed = [c.strip() for c in str(_s("allowed_commands", "")).split(",") if c.strip()]
        if allowed:
            cmd += ["--allowedTools", ",".join(f"Bash({c}:*)" for c in allowed)]
    else:
        cmd += ["--dangerously-skip-permissions"]
    if job.get("resume"):
        cmd += ["--resume", job["resume"]]
    elif job.get("continue_last"):
        cmd += ["--continue"]
    return cmd


def _describe_tool(name: str, inp: dict) -> str:
    target = inp.get("file_path") or inp.get("path") or inp.get("pattern") or inp.get("command") \
        or inp.get("url") or inp.get("query") or ""
    target = str(target)
    if inp.get("file_path"):
        target = Path(target).name
    verbs = {"Read": "reading", "Edit": "editing", "MultiEdit": "editing", "Write": "writing",
             "Bash": "running", "Grep": "searching for", "Glob": "looking for", "LS": "listing",
             "WebSearch": "searching the web for", "WebFetch": "reading", "TodoWrite": "updating its plan",
             "Task": "starting a helper for", "ExitPlanMode": "finishing the plan"}
    return f"{verbs.get(name, name)} {target[:70]}".strip()


def _progress(job: dict, line: str) -> None:
    job["progress"].append(time.strftime("%H:%M:%S ") + line)
    del job["progress"][:-40]
    addons.log(f"CLAUDE CODE [{job['project']}]: {line}")


def _handle_event(job: dict, ev: dict) -> None:
    t = ev.get("type")
    if t == "system" and ev.get("subtype") == "init":
        job["session"] = ev.get("session_id") or job.get("session")
        _progress(job, "started" + (f" ({ev.get('model')})" if ev.get("model") else ""))
    elif t == "assistant":
        for part in (ev.get("message") or {}).get("content") or []:
            if part.get("type") == "tool_use":
                inp = part.get("input") or {}
                if part.get("name") in ("Edit", "MultiEdit", "Write") and inp.get("file_path"):
                    job["files"].add(Path(str(inp["file_path"])).name)
                if part.get("name") == "ExitPlanMode" and inp.get("plan"):
                    job["plan"] = str(inp["plan"])
                _progress(job, _describe_tool(part.get("name", "?"), inp))
            elif part.get("type") == "text" and part.get("text", "").strip():
                job["last_text"] = part["text"].strip()
    elif t == "result":
        job["session"] = ev.get("session_id") or job.get("session")
        job["result"] = str(ev.get("result") or job.get("last_text") or "")
        job["error"] = bool(ev.get("is_error")) or ev.get("subtype") not in (None, "success")
        job["turns"] = ev.get("num_turns")


def _worker(job: dict) -> None:
    exe = _claude()
    if not exe:
        job.update(state="failed", result="Claude Code is not installed on this PC.")
        _finish(job)
        return
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.Popen(_command(exe, job), cwd=job["folder"], env=env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                errors="replace", creationflags=_NO_WINDOW)
    except OSError as e:
        job.update(state="failed", result=f"could not start Claude Code: {e}")
        _finish(job)
        return
    job["proc"] = proc
    try:
        proc.stdin.write(job["prompt"])
        proc.stdin.close()
    except OSError:
        pass
    err_lines: list[str] = []
    threading.Thread(target=lambda: err_lines.extend(proc.stderr.read().splitlines()[-20:]),
                     daemon=True).start()
    deadline = time.time() + float(_s("max_minutes", 30)) * 60
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("{"):
            try:
                _handle_event(job, json.loads(line))
            except ValueError:
                pass
        if time.time() > deadline:
            proc.kill()
            job["result"] = (job.get("result") or "") + " (stopped: took longer than the time limit)"
            break
    proc.wait()
    if job["state"] == "stopping":
        job["state"] = "stopped"
    elif proc.returncode != 0 and not job.get("result"):
        job.update(state="failed", result="\n".join(err_lines)[-400:] or f"exit code {proc.returncode}")
    else:
        job["state"] = "failed" if job.get("error") else "done"
    low = (job.get("result") or "").lower()
    if "usage limit" in low or "limit reached" in low:
        job.update(state="failed", result="Your Claude usage limit is used up for now. " + job["result"][:200])
    elif "not logged in" in low or "/login" in low:
        job.update(state="failed", result="Claude Code is not signed in on this PC: run `claude` once "
                                         "in a terminal and log in.")
    _finish(job)


def _finish(job: dict) -> None:
    job["ended"] = time.time()
    job.pop("proc", None)
    mins = max(1, round((job["ended"] - job["started"]) / 60))
    files = sorted(job["files"])
    summary = (job.get("plan") or job.get("result") or "").strip()
    _progress(job, f"{job['state']} after {mins} min" + (f", changed {len(files)} file(s)" if files else ""))
    body = summary[:1500] + (("\n\nFiles changed: " + ", ".join(files)) if files else "")
    if job["state"] == "stopped":
        return
    title = f"Claude Code · {job['project']}"
    if job["state"] == "failed":
        addons.notify(f"{title} — failed", body or "no details",
                      "[SYSTEM] A Claude Code job the user started has FAILED. In one or two sentences "
                      "say what went wrong and offer the obvious fix:\n"
                      + outcome.untrusted("claude_code", f"task: {job['task']}\n{body[:800]}"),
                      kind="error")
        return
    if job["permission"] == "plan":
        instruction = ("[SYSTEM] Claude Code finished PLANNING (nothing changed yet). Give the user the "
                       "gist of the plan in two or three sentences and ask whether to go ahead "
                       "(if yes: claude_code action=approve).")
    else:
        instruction = ("[SYSTEM] A Claude Code job the user started has finished. In two sentences say "
                       "what it did (no file paths read aloud), then suggest the one most useful next "
                       "step — test it, review the changes, commit — or ask what they'd like next.")
    addons.notify(f"{title} — {'plan ready' if job['permission'] == 'plan' else 'done'}", body,
                  instruction + "\n" + outcome.untrusted(
                      "claude_code", f"task: {job['task']}\nfiles: {', '.join(files) or 'none'}\n{summary[:1200]}"),
                  kind="task")


def start(project: str, task: str, permission: str, *, resume: str = "",
          continue_last: bool = False, folder: str = "") -> dict:
    job = {"id": f"cc{int(time.time()) % 100000}", "project": project, "folder": folder,
           "task": task, "prompt": task, "permission": permission, "resume": resume,
           "continue_last": continue_last, "state": "running", "progress": [], "files": set(),
           "started": time.time(), "session": resume or ""}
    with _lock:
        if any(j["state"] == "running" and j["folder"] == folder for j in _jobs):
            raise RuntimeError(f"Claude Code is already working in {project}; wait or stop it first")
        _jobs.append(job)
        del _jobs[:-_MAX_JOBS]
    threading.Thread(target=_worker, args=(job,), name=f"claude_code_{job['id']}", daemon=True).start()
    return job


def stop(job: dict) -> bool:
    p = job.get("proc")
    if p is None or job["state"] != "running":
        return False
    job["state"] = "stopping"
    try:
        p.kill()
    except OSError:
        pass
    return True


def open_window(folder: str, continue_last: bool) -> tuple[bool, str]:
    """An interactive Claude Code in a terminal window, in that folder."""
    exe = _claude()
    if not exe:
        return False, "Claude Code is not installed on this PC."
    args = [exe] + (["--continue"] if continue_last else [])
    try:
        if sys.platform == "win32":
            wt = shutil.which("wt")
            if wt:
                subprocess.Popen([wt, "-d", folder, *args])
            else:
                subprocess.Popen(["cmd", "/c", "start", "Claude Code", "/D", folder, *args])
        elif sys.platform == "darwin":
            script = f'tell application "Terminal" to do script "cd {json.dumps(folder)[1:-1]} && claude' \
                     + (' --continue' if continue_last else '') + '"'
            subprocess.Popen(["osascript", "-e", script])
        else:
            term = shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal")
            if not term:
                return False, "no terminal program found"
            subprocess.Popen([term, "--", *args], cwd=folder)
        return True, folder
    except OSError as e:
        return False, str(e)


# ── the tool ──────────────────────────────────────────────────────────────────

def _job_line(j: dict) -> str:
    age = int(((j.get("ended") or time.time()) - j["started"]) // 60)
    last = j["progress"][-1][9:] if j["progress"] else ""
    return f"{j['project']} [{j['permission']}] {j['state']} {age} min — {j['task'][:80]} — {last}"


def _latest(project: str = "") -> dict | None:
    with _lock:
        for j in reversed(_jobs):
            if not project or _norm(project) in _norm(j["project"]):
                return j
    return None


PLUGIN = {
    "name": "claude_code",
    "description": (
        "Controls Claude Code (the coding agent signed in on this PC) in the user's project "
        "folders. Use for 'ask Claude Code to …', 'have Claude fix/build/refactor … in <project>', "
        "'what is Claude Code doing', 'stop Claude', 'go ahead with the plan', 'tell Claude to "
        "also …', 'open Claude Code in <project>'. permission: plan = read-only plan first "
        "(default for big or vague jobs), edits = may edit files, full = may run any command. "
        "Pass the user's request as task, in their words, with any detail they gave."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["run", "approve", "reply", "status", "stop",
                                                   "open_window", "projects", "add_project"]},
            "project": {"type": "STRING", "description": "Project name or folder path"},
            "task": {"type": "STRING", "description": "For run/reply: what Claude Code should do"},
            "permission": {"type": "STRING", "enum": ["plan", "edits", "full"]},
            "continue_last": {"type": "BOOLEAN",
                              "description": "Continue the last Claude Code conversation in that folder"},
            "folder": {"type": "STRING", "description": "For add_project: full path"},
        },
        "required": ["action"],
    },
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "extra",
    "brief": "Run Claude Code in a project: plan, edit, status, stop, open.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "CLAUDE CODE CONTROL",
    "fields": [
        {"key": "projects", "label": "Projects (name=folder; name=folder)", "type": "text",
         "placeholder": r"site=C:\Code\portfolio; jarvis=C:\Users\me\Mark-LVII"},
        {"key": "code_roots", "label": "Code folders to find projects in (; between them, empty = usual places)",
         "type": "text", "placeholder": r"C:\Code; D:\Uni"},
        {"key": "default_permission", "label": "When I don't say, Claude Code may", "type": "choice",
         "options": ["plan", "edits"], "default": "plan"},
        {"key": "confirm_edits", "label": "Ask me to confirm before an 'edits' job", "type": "toggle",
         "default": True},
        {"key": "allow_full", "label": "Allow 'full' jobs (any command, always confirmed)", "type": "toggle",
         "default": False},
        {"key": "allowed_commands", "label": "Commands an 'edits' job may run (comma separated)",
         "type": "text", "placeholder": "git status, git diff, npm test, pytest"},
        {"key": "model", "label": "Model", "type": "choice", "options": ["default", "sonnet", "opus"],
         "default": "default"},
        {"key": "max_minutes", "label": "Stop a job after (minutes)", "type": "choice",
         "options": ["10", "30", "60", "120"], "default": "30"},
        {"key": "claude_path", "label": "Path to claude (only if not found by itself)", "type": "text"},
    ],
}


def _gate(title: str, detail: str, permission: str, launch) -> str:
    """Edits (unless switched off) and full jobs wait for the user's CONFIRM."""
    if permission == "plan" or (permission == "edits" and not _s("confirm_edits", True)):
        return launch()
    from core import confirm
    return confirm.request(f"claude_code_{permission}", title, detail, launch)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    try:
        if action == "projects":
            known = projects()
            text = "\n".join(f"{n} — {p}" for n, p in sorted(known.items())) or \
                "No projects yet: add them in ⚙ → PLUGIN SETTINGS → CLAUDE CODE CONTROL."
            addons.show("CLAUDE CODE PROJECTS", text)
            return outcome.done("claude_projects", count=len(known), names=", ".join(sorted(known))[:300])

        if action == "add_project":
            name = str(parameters.get("project") or "").strip()
            if not name or not parameters.get("folder"):
                return outcome.ask("claude_add_project", "What should I call it, and which folder is it?")
            ok, msg = add_project(name, str(parameters["folder"]))
            return outcome.done("claude_add_project", project=name, folder=msg) if ok \
                else outcome.failed("claude_add_project", msg)

        if action == "status":
            with _lock:
                jobs = list(_jobs)
            if not jobs:
                return outcome.done("claude_status", jobs=0, note="nothing has been sent to Claude Code yet")
            j = jobs[-1]
            addons.show(f"CLAUDE CODE · {j['project'].upper()}",
                        f"{j['task']}\n\n" + "\n".join(j["progress"][-15:]))
            return outcome.done("claude_status", running=sum(x["state"] == "running" for x in jobs)) + \
                "\n" + outcome.untrusted("claude_code", "\n".join(_job_line(x) for x in jobs[-4:]))

        if action == "stop":
            j = _latest(str(parameters.get("project") or ""))
            if j is None or not stop(j):
                return outcome.failed("claude_stop", "no Claude Code job is running")
            return outcome.done("claude_stop", project=j["project"])

        if action == "open_window":
            res = resolve_project(str(parameters.get("project") or ""))
            if res is None:
                return outcome.ask("claude_open", "Which project should I open Claude Code in?")
            ok, msg = open_window(res[1], bool(parameters.get("continue_last")))
            return outcome.done("claude_open", project=res[0]) if ok else outcome.failed("claude_open", msg)

        if action == "approve":
            j = _latest(str(parameters.get("project") or ""))
            if j is None or j["permission"] != "plan" or j["state"] != "done" or not j.get("session"):
                return outcome.failed("claude_approve", "there is no finished plan waiting")
            extra = str(parameters.get("task") or "").strip()
            task = "Go ahead and implement the plan." + (f" Also: {extra}" if extra else "")
            perm = "full" if str(parameters.get("permission")) == "full" else "edits"
            if perm == "full" and not _s("allow_full", False):
                return outcome.failed("claude_approve", "full access is switched off in settings")

            def launch() -> str:
                n = start(j["project"], task, perm, resume=j["session"], folder=j["folder"])
                return outcome.started("claude_code", project=n["project"], permission=perm,
                                       note="say you'll tell them when it's done")
            return _gate(f"Claude Code: carry out the plan in {j['project']}",
                         (j.get("plan") or j.get("result") or "")[:600], perm, launch)

        if action in ("run", "reply"):
            task = str(parameters.get("task") or "").strip()
            if not task:
                return outcome.ask("claude_run", "What should Claude Code do?")
            prev = _latest(str(parameters.get("project") or "")) if action == "reply" else None
            if action == "reply" and (prev is None or not prev.get("session")):
                return outcome.failed("claude_reply", "there is no earlier Claude Code job to follow up on")
            if prev is not None:
                name, folder = prev["project"], prev["folder"]
            else:
                res = resolve_project(str(parameters.get("project") or ""))
                if res is None:
                    names = ", ".join(sorted(projects())[:12]) or "none set up yet"
                    return outcome.ask("claude_run", f"Which project? I know: {names}.")
                name, folder = res
            perm = str(parameters.get("permission") or (prev["permission"] if prev and prev["permission"] != "plan"
                                                        else _s("default_permission", "plan")))
            if perm not in ("plan", "edits", "full"):
                perm = "plan"
            if perm == "full" and not _s("allow_full", False):
                return outcome.failed("claude_run", "full access is switched off in settings — "
                                      "use plan or edits, or switch it on in CLAUDE CODE CONTROL")

            def launch() -> str:
                n = start(name, task, perm, resume=prev["session"] if prev else "",
                          continue_last=bool(parameters.get("continue_last")), folder=folder)
                return outcome.started("claude_code", project=n["project"], permission=perm,
                                       note=("planning only, nothing will change yet; " if perm == "plan" else "")
                                       + "say in a few words that it's on it and you'll report back")
            return _gate(f"Claude Code ({perm}) in {name}", task[:600], perm, launch)

        return outcome.failed("claude_code", f"unknown action {action}")
    except Exception as e:
        return outcome.failed(f"claude_{action}", str(e)[:200])
