"""
plugins/knowledge_base.py — ask questions about your own documents.

    "What does my physics revision sheet say about momentum?"   action=ask
    "Check my notes: when is the history coursework due?"       action=ask
    "What's in my knowledge folder?"                            action=list
    "Re-read my knowledge folder"                               action=reindex

Put notes, PDFs, Word documents, slides and text files in one folder and JARVIS
can look things up in them. By default the folder is inside OneDrive —

    %OneDrive%\\JARVIS Knowledge

— so every computer JARVIS runs on sees the same documents, and you can add a
file from your phone with the OneDrive app. Change it in ⚙ → PLUGIN SETTINGS.

HOW IT WORKS
    Each file's text is split into passages of a few hundred words and indexed
    locally (BM25, the classic search-engine ranking — no model, no upload, no
    new library). A question returns the best few passages with the file they
    came from, and the assistant answers from those. The index is kept in
    config/knowledge_index.json and only files that changed are re-read.

    Readable: .txt .md .pdf .docx .pptx .csv .json and most code files. Scanned
    PDFs with no text layer cannot be read; the list action says which ones.

    Passages are returned wrapped as untrusted content: a document that says
    "ignore your instructions" is something JARVIS reports, not obeys.
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path

from core import outcome
from memory.config_manager import CONFIG_DIR, get_plugin_setting

NAMESPACE = "knowledge_base"
INDEX_FILE = CONFIG_DIR / "knowledge_index.json"
TEXT_EXT = {".txt", ".md", ".markdown", ".csv", ".json", ".py", ".js", ".ts", ".html",
            ".htm", ".xml", ".yaml", ".yml", ".ini", ".log", ".java", ".c", ".cpp", ".cs"}
DOC_EXT = {".pdf", ".docx", ".pptx"}
MAX_FILE_BYTES = 40_000_000
PASSAGE_WORDS = 220
OVERLAP_WORDS = 40

_lock = threading.Lock()
_index: dict = {"files": {}}        # path -> {"mtime", "size", "passages": [str], "error"}
_stats: dict = {"df": Counter(), "n": 0, "avgdl": 1.0, "built_for": None}
_building = threading.Event()

_WORD = re.compile(r"[\w']+", re.UNICODE)
_STOP = set("""a an and are as at be but by for from has have i if in into is it its of on
or our so than that the their them then there these they this to was we were what when
where which who why will with you your do does did can could would should my me""".split())


def _default_folder() -> str:
    root = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    return str(Path(root) / "JARVIS Knowledge") if root else str(Path.home() / "JARVIS Knowledge")


def _folder() -> Path:
    raw = str(get_plugin_setting(NAMESPACE, "folder", "") or "").strip()
    return Path(raw or _default_folder()).expanduser()


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


# ── reading files ─────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in TEXT_EXT:
        return path.read_text(encoding="utf-8", errors="replace")
    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        except ImportError:
            from PyPDF2 import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    if ext == ".docx":
        import docx
        d = docx.Document(str(path))
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(parts)
    if ext == ".pptx":
        from pptx import Presentation
        out = []
        for i, slide in enumerate(Presentation(str(path)).slides, 1):
            texts = [sh.text_frame.text for sh in slide.shapes if getattr(sh, "has_text_frame", False)]
            out.append(f"[Slide {i}] " + "\n".join(texts))
        return "\n".join(out)
    return ""


def _passages(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = PASSAGE_WORDS - OVERLAP_WORDS
    return [" ".join(words[i:i + PASSAGE_WORDS]) for i in range(0, len(words), step)
            if words[i:i + PASSAGE_WORDS]]


# ── the index ─────────────────────────────────────────────────────────────────

def _load_index() -> None:
    global _index
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("files"), dict):
            _index = data
    except (OSError, ValueError):
        pass


def _recompute_stats() -> None:
    df, n, total = Counter(), 0, 0
    for info in _index["files"].values():
        for p in info.get("passages", []):
            toks = set(_tokens(p))
            df.update(toks)
            n += 1
            total += len(p.split())
    _stats.update(df=df, n=n, avgdl=(total / n) if n else 1.0, built_for=str(_folder()))


def build_index() -> tuple[int, int, list[str]]:
    """Re-read changed files. Returns (files indexed, passages, unreadable files)."""
    folder = _folder()
    folder.mkdir(parents=True, exist_ok=True)
    _building.set()
    try:
        with _lock:
            if not _index["files"]:
                _load_index()
            seen, unreadable = set(), []
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.name.startswith(("~$", ".")):
                    continue
                ext = path.suffix.lower()
                if ext not in TEXT_EXT | DOC_EXT:
                    continue
                key = str(path)
                seen.add(key)
                st = path.stat()
                old = _index["files"].get(key)
                if old and old.get("mtime") == st.st_mtime and old.get("size") == st.st_size:
                    if old.get("error"):
                        unreadable.append(path.name)
                    continue
                entry = {"mtime": st.st_mtime, "size": st.st_size, "passages": [], "error": ""}
                if st.st_size > MAX_FILE_BYTES:
                    entry["error"] = "too large"
                else:
                    try:
                        entry["passages"] = _passages(_read(path))
                        if not entry["passages"]:
                            entry["error"] = "no text (a scan, or empty)"
                    except Exception as e:  # a damaged file must not stop the others
                        entry["error"] = f"{type(e).__name__}"
                if entry["error"]:
                    unreadable.append(path.name)
                _index["files"][key] = entry
            for gone in set(_index["files"]) - seen:
                del _index["files"][gone]
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            INDEX_FILE.write_text(json.dumps(_index), encoding="utf-8")
            _recompute_stats()
            files = sum(1 for f in _index["files"].values() if f.get("passages"))
            return files, _stats["n"], unreadable
    finally:
        _building.clear()


def search(question: str, k: int = 5) -> list[tuple[float, str, str]]:
    """(score, file name, passage), best first. BM25 with k1=1.5, b=0.75."""
    q = _tokens(question)
    if not q or not _stats["n"]:
        return []
    k1, b, n, avgdl, df = 1.5, 0.75, _stats["n"], _stats["avgdl"], _stats["df"]
    results = []
    folder = _folder()
    for path, info in _index["files"].items():
        for p in info.get("passages", []):
            tf = Counter(_tokens(p))
            dl = len(p.split())
            score = 0.0
            for term in q:
                if term in tf:
                    idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                    score += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * dl / avgdl))
            if score > 0:
                try:
                    name = str(Path(path).relative_to(folder))
                except ValueError:
                    name = Path(path).name
                results.append((score, name, p))
    results.sort(key=lambda r: r[0], reverse=True)
    return results[:k]


def _ensure_fresh(max_age_s: float = 60.0) -> None:
    """Rebuild when the folder changed or the index is for another folder."""
    if _stats["built_for"] != str(_folder()) or time.time() - _ensure_fresh.last > max_age_s:
        build_index()
        _ensure_fresh.last = time.time()


_ensure_fresh.last = 0.0


# ── plugin ────────────────────────────────────────────────────────────────────

def _test(values: dict) -> tuple[bool, str]:
    try:
        files, passages, bad = build_index()
    except OSError as e:
        return False, f"Cannot use that folder: {e}"
    note = f" — could not read: {', '.join(bad[:3])}" if bad else ""
    return True, f"{files} file(s), {passages} passages indexed{note}"


PLUGIN = {
    "name": "knowledge_base",
    "description": (
        "Searches the user's own documents (notes, PDFs, Word, slides) in their "
        "knowledge folder. Use when they ask about 'my notes', 'my documents', 'my "
        "files', a named document of theirs, or anything they say they saved there. "
        "Answer only from the passages returned and say which file they came from. "
        "For files elsewhere on the computer use file_processor instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["ask", "list", "reindex"]},
            "question": {"type": "STRING", "description": "For ask: what to look up, in the user's words"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Search the user's own documents: ask / list / reindex.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "KNOWLEDGE FOLDER",
    "fields": [
        {"key": "folder", "label": "Folder with your documents (same on every computer)",
         "type": "text", "placeholder": _default_folder()},
    ],
    "action": {"label": "INDEX NOW", "run": _test},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "ask").lower()
    try:
        if action == "reindex":
            files, passages, bad = build_index()
            _ensure_fresh.last = time.time()
            return outcome.done("knowledge_reindex", files=files, passages=passages,
                                unreadable=", ".join(bad[:5]) or None, folder=str(_folder()))
        _ensure_fresh()
        if action == "list":
            names = sorted(Path(p).name + (f" (unreadable: {i['error']})" if i.get("error") else "")
                           for p, i in _index["files"].items())
            if player and names:
                player.show_content("KNOWLEDGE FOLDER", "\n".join(names))
            return outcome.done("knowledge_list", count=len(names), folder=str(_folder())) + \
                ("\n" + outcome.untrusted("files", "\n".join(names[:40])) if names else "")
        if action == "ask":
            question = (parameters.get("question") or "").strip()
            if not question:
                return outcome.ask("knowledge_ask", "What should I look up in your documents?")
            hits = search(question)
            if not hits:
                return outcome.done("knowledge_ask", matches=0, folder=str(_folder()),
                                    note="nothing in the user's documents matches; say so "
                                         "rather than guessing")
            text = "\n\n".join(f"[{name}]\n{p}" for _s, name, p in hits)
            if player:
                try:
                    player.show_content("FROM YOUR DOCUMENTS",
                                        "\n\n".join(f"{name}:\n{p[:400]}…" for _s, name, p in hits[:3]))
                except Exception:
                    pass
            return outcome.done("knowledge_ask", matches=len(hits),
                                files=", ".join(sorted({n for _s, n, _p in hits}))) + "\n" + \
                outcome.untrusted("documents", text)
        return outcome.failed("knowledge", f"unknown action {action}")
    except Exception as e:
        return outcome.failed(f"knowledge_{action}", f"{type(e).__name__}: {e}")


def _warm() -> None:
    """Index in the background at start-up so the first question is quick. Only
    when the folder already exists: nobody gets a folder they never asked for."""
    time.sleep(8)
    try:
        if _folder().is_dir():
            _ensure_fresh()
    except Exception as e:
        print(f"[Knowledge] warm-up skipped: {e}")


threading.Thread(target=_warm, name="knowledge_index", daemon=True).start()
