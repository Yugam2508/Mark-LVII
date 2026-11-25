"""
plugins/life_profile.py — JARVIS remembers your life, not just facts.

Each part of your life is an AREA — studies, work, music lessons, comedy and
writing, travel, training for a race, anything — with three sections:

    About   who/what/where: "Guitar lessons on Thursdays with Sam, learning fingerstyle"
    Goals   with optional target dates: "Finish IRONMAN 70.3 — 2027-10-12"
    Log     dated entries: "2026-11-25 — 12 km run, felt strong"

You don't have to say "remember": when you mention something about your life the
assistant saves it to the right area. You can also ask:

    "Set up my profile" / "get to know me"       action=setup   (it interviews you)
    "What do you know about my IRONMAN training?" action=recall area=...
    "What do you know about me?"                  action=profile
    "I finished the travel goal of seeing Japan"  action=goal_done

WHERE IT LIVES
    Plain files in your knowledge folder (OneDrive): JARVIS Life/<Area>.md. Both PCs
    and your phone (OneDrive app) see them; you can read and edit them yourself; the
    knowledge folder search covers them too. A one-line summary of each area is also
    kept in JARVIS's own memory so it knows the basics at the start of every
    conversation, and fetches the details here when it needs them.
"""
from __future__ import annotations

import datetime as dt
import difflib
import re
import threading
import time
from pathlib import Path

from core import addons, outcome
from memory.config_manager import get_plugin_setting, save_plugin_config

NAMESPACE = "life_profile"
SECTIONS = ("About", "Goals", "Log")
STARTER_AREAS = {
    "Studies": "What do you study, where, which year, and what's hard or fun about it right now?",
    "Work": "What work or projects are you doing, and what's on your plate this month?",
    "Music": "Which lessons (instrument, singing), with whom, how often, and what you're working on?",
    "Comedy & Writing": "What kind of comedy or writing, do you perform or post anywhere, any bits in progress?",
    "Travel": "Where do you want to go, when, and what's already planned?",
    "Fitness & Training": "What are you training for, the race date, and your current weekly routine?",
}
_lock = threading.Lock()


# ── files ─────────────────────────────────────────────────────────────────────

def folder() -> Path:
    from plugins import knowledge_base
    f = knowledge_base._folder() / "JARVIS Life"
    f.mkdir(parents=True, exist_ok=True)
    return f


def _safe(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", " ", name).strip()
    return re.sub(r"\s+", " ", name)[:60] or "General"


def areas() -> list[str]:
    return sorted(p.stem for p in folder().glob("*.md"))


def resolve(area: str, create: bool = True) -> str | None:
    """An existing area for a spoken name ('my ironman' -> 'IRONMAN 70.3'), or a new one."""
    want = re.sub(r"^(?:my|the)\s+", "", (area or "").strip(), flags=re.I)
    if not want:
        return None
    existing = areas()
    low = {a.lower(): a for a in existing}
    if want.lower() in low:
        return low[want.lower()]
    hits = [a for a in existing if want.lower() in a.lower() or a.lower() in want.lower()]
    if len(hits) == 1:
        return hits[0]
    close = difflib.get_close_matches(want.lower(), list(low), n=1, cutoff=0.75)
    if close:
        return low[close[0]]
    return _safe(want[:1].upper() + want[1:]) if create else None


def _path(area: str) -> Path:
    return folder() / f"{_safe(area)}.md"


def read(area: str) -> dict:
    p = _path(area)
    data = {"About": [], "Goals": [], "Log": []}
    if not p.exists():
        return data
    current = None
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(About|Goals|Log)\s*$", line.strip())
        if m:
            current = m.group(1)
            continue
        if current and line.strip():
            data[current].append(line.rstrip())
    return data


def write(area: str, data: dict) -> None:
    lines = [f"# {area}", f"_Last updated: {dt.date.today().isoformat()}_", ""]
    for sec in SECTIONS:
        lines.append(f"## {sec}")
        lines += data.get(sec) or []
        lines.append("")
    _path(area).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def summary(area: str, data: dict | None = None) -> str:
    data = data or read(area)
    about = " ".join(l.strip() for l in data["About"])[:160]
    open_goals = [g[6:] for g in data["Goals"] if g.startswith("- [ ]")]
    last = data["Log"][-1][2:] if data["Log"] else ""
    bits = [about] if about else []
    if open_goals:
        bits.append("goal: " + open_goals[0][:90])
    if last:
        bits.append("latest: " + last[:90])
    return f"{area}: " + "; ".join(bits) if bits else area


def _sync_memory(area: str, data: dict) -> None:
    """Keep a one-line summary in JARVIS's own memory, which rides in every session."""
    try:
        from memory.memory_manager import update_memory
        key = "life_" + re.sub(r"[^a-z0-9]+", "_", area.lower()).strip("_")
        update_memory({"projects": {key: {"value": summary(area, data)[:370]}}})
    except Exception as e:
        print(f"[Life] memory sync skipped: {e}")


# ── changes ───────────────────────────────────────────────────────────────────

def remember(area: str, info: str, kind: str = "auto", target_date: str = "") -> tuple[str, str]:
    """Save something. kind: about | goal | log | auto. Returns (area, what was stored)."""
    name = resolve(area)
    info = re.sub(r"\s+", " ", (info or "").strip())
    if not name or not info:
        raise ValueError("need an area and what to remember")
    if kind == "auto":
        kind = ("goal" if re.search(r"\b(want to|goal|plan to|hope to|aim|dream|bucket list|by \d{4})\b", info, re.I)
                else "log" if re.search(r"\b(today|yesterday|this week|just|finished|did|ran|swam|rode|"
                                        r"learned|learnt|performed|wrote|booked|had (?:a|my))\b", info, re.I)
                else "about")
    with _lock:
        data = read(name)
        if kind == "goal":
            date = f" — target {target_date[:10]}" if target_date else ""
            line = f"- [ ] {info}{date}"
            if line not in data["Goals"]:
                data["Goals"].append(line)
        elif kind == "log":
            data["Log"].append(f"- {dt.date.today().isoformat()} — {info}")
        else:
            if info not in " ".join(data["About"]):
                data["About"].append(info)
        write(name, data)
    _sync_memory(name, data)
    return name, kind


def goal_done(area: str, query: str) -> str | None:
    name = resolve(area, create=False)
    if not name:
        return None
    with _lock:
        data = read(name)
        q = (query or "").lower()
        for i, g in enumerate(data["Goals"]):
            if g.startswith("- [ ]") and (not q or q in g.lower()):
                data["Goals"][i] = g.replace("- [ ]", "- [x]", 1) + f" (done {dt.date.today().isoformat()})"
                data["Log"].append(f"- {dt.date.today().isoformat()} — Achieved: {g[6:]}")
                write(name, data)
                _sync_memory(name, data)
                return g[6:]
    return None


def next_goals(within_days: int = 400) -> list[tuple[int, str, str]]:
    """(days left, area, goal) for open goals with a target date, soonest first."""
    out = []
    today = dt.date.today()
    for a in areas():
        for g in read(a)["Goals"]:
            m = re.search(r"target (\d{4}-\d{2}-\d{2})", g)
            if g.startswith("- [ ]") and m:
                days = (dt.date.fromisoformat(m.group(1)) - today).days
                if 0 <= days <= within_days:
                    out.append((days, a, re.sub(r" — target .*$", "", g[6:])))
    return sorted(out)


def _offer_once() -> None:
    """The first time, offer to set the profile up (after the greeting)."""
    time.sleep(75)
    try:
        if areas() or get_plugin_setting(NAMESPACE, "offered", False):
            return
        save_plugin_config(NAMESPACE, {"offered": True})
        addons.say("[SYSTEM] You don't know much about the user's life yet. In one short "
                   "sentence, offer to get to know them properly — their studies, work, "
                   "hobbies and goals — whenever they have five minutes (they can say "
                   "'set up my profile').")
    except Exception as e:
        print(f"[Life] offer skipped: {e}")


# ── tool ──────────────────────────────────────────────────────────────────────

PLUGIN = {
    "name": "life_profile",
    "description": (
        "The user's life profile — long-term memory of their life by area (studies, work, "
        "music lessons, comedy, writing, travel, training for a race, any hobby or project). "
        "SAVE WITHOUT BEING ASKED whenever the user mentions anything about their life: a "
        "fact (about), a goal with an optional date (goal), or something that happened or "
        "progress (log). Recall an area before answering questions about it. 'setup' when "
        "they want you to get to know them: then ask its questions one area at a time and "
        "save each answer. Short facts like their name also go to the regular memory."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "enum": ["remember", "recall", "profile", "goal_done", "setup"]},
            "area": {"type": "STRING",
                     "description": "Short area name, e.g. 'Studies', 'Guitar lessons', 'IRONMAN 70.3', 'Travel'"},
            "info": {"type": "STRING", "description": "For remember: what to save, in a full sentence"},
            "kind": {"type": "STRING", "enum": ["auto", "about", "goal", "log"]},
            "target_date": {"type": "STRING", "description": "For a goal: YYYY-MM-DD if there is one"},
            "query": {"type": "STRING", "description": "For recall across areas, or goal_done: words from the goal"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Long-term life memory by area: remember / recall / profile / setup.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "profile")
    try:
        if action == "remember":
            name, kind = remember(str(parameters.get("area") or ""), str(parameters.get("info") or ""),
                                  str(parameters.get("kind") or "auto"),
                                  str(parameters.get("target_date") or ""))
            return outcome.done("life_remember", area=name, saved_as=kind,
                                note="acknowledge briefly and naturally; don't read it back")
        if action == "goal_done":
            g = goal_done(str(parameters.get("area") or ""), str(parameters.get("query") or ""))
            return outcome.done("life_goal_done", goal=g) if g else \
                outcome.ask("life_goal_done", "Which goal did you finish?")
        if action == "recall":
            area = resolve(str(parameters.get("area") or ""), create=False) if parameters.get("area") else None
            if area:
                d = read(area)
                d["Log"] = d["Log"][-15:]
                text = "\n".join(f"## {s}\n" + "\n".join(d[s]) for s in SECTIONS if d[s])
                if player:
                    player.show_content(area.upper(), text[:3000])
                return outcome.done("life_recall", area=area) + "\n" + outcome.untrusted("profile", text[:5000])
            q = str(parameters.get("query") or parameters.get("area") or "").lower()
            hits = []
            for a in areas():
                for sec, lines in read(a).items():
                    hits += [f"{a} / {sec}: {l.lstrip('- ')}" for l in lines if q and q in l.lower()]
            return outcome.done("life_recall", matches=len(hits)) + \
                ("\n" + outcome.untrusted("profile", "\n".join(hits[-20:])) if hits else "")
        if action == "setup":
            have = {a.lower() for a in areas()}
            todo = [(a, q) for a, q in STARTER_AREAS.items() if a.lower() not in have]
            text = "\n".join(f"{a}: {q}" for a, q in todo) or "All starter areas have something."
            return outcome.done("life_setup", areas_to_ask=len(todo),
                                note="ask these one at a time, conversationally; skip any that don't "
                                     "apply; save each answer with action=remember (use the user's own "
                                     "area names, e.g. 'Guitar lessons' instead of 'Music' if that fits)") + \
                "\n" + text
        names = areas()
        if not names:
            return outcome.done("life_profile", areas=0, note="nothing yet; offer to set it up")
        text = "\n".join(summary(a) for a in names)
        soon = next_goals(120)
        if soon:
            text += "\n\nComing up: " + "; ".join(f"{g} ({a}) in {d} days" for d, a, g in soon[:3])
        if player:
            player.show_content("WHAT I KNOW ABOUT YOU", text)
        return outcome.done("life_profile", areas=len(names)) + "\n" + outcome.untrusted("profile", text)
    except Exception as e:
        return outcome.failed(f"life_{action}", str(e)[:150])


threading.Thread(target=_offer_once, name="life_profile_offer", daemon=True).start()
