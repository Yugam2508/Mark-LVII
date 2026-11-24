"""
core/confirm.py — a confirmation the model cannot forge.

THE PROBLEM WITH THE OLD GATE
    computer_settings guarded shutdown and restart like this:

        confirmed = str(params.get("confirmed", "")).lower()
        if confirmed not in ("yes", "true", "1", "confirm"):
            return "Please confirm by calling again with confirmed=yes."

    `confirmed` is a tool parameter, which means the *model* writes it. Nothing
    stops it from sending confirmed=yes on the first call, and nothing checks
    that a human was ever involved. It is a convention, not a gate — and its
    coverage was two actions, so deleting files and switching off the WiFi the
    assistant is talking over went through with no gate at all.

THE DESIGN HERE
    The confirmation token is issued by the *interface*, never by the model:

      1. An action calls `request(...)` with a callable that does the real work.
      2. This module hands the UI a banner with CONFIRM / CANCEL and returns
         IMMEDIATELY with a sentence for the model to say out loud.
      3. If — and only if — the user presses CONFIRM, the UI calls `resolve()`,
         which runs the stored callable off the Qt thread.

    Nothing blocks. The model keeps talking while the banner is up, so this
    costs no latency at all; in fact it is cheaper than the old gate, which
    burned two tool round trips (reject, then re-call) on every shutdown.

WHAT BELONGS HERE AND WHAT DOES NOT
    Only genuinely irreversible things. Anything that can be reversed should be
    done at once and pushed onto core/undo.py instead — undo is faster than a
    question, and an assistant that asks before every action is one nobody uses.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

# A pending confirmation is abandoned after this long. Chosen to outlast a
# normal "hang on, let me look at the screen" pause without leaving a live
# shutdown button sitting on the HUD for the rest of the day.
TIMEOUT_SECONDS = 90.0


@dataclass
class _Pending:
    key:     str
    title:   str
    detail:  str
    run:     Callable[[], str]
    at:      float
    # Optional EDIT support. `fields` is a list of
    #   {"key": str, "label": str, "value": str, "multiline": bool}
    # and `run_edited(values)` performs the action with what the person typed.
    # The values come from the person's own keyboard on the HUD — never from the
    # model — so editing does not weaken the gate.
    fields:     Optional[list] = None
    run_edited: Optional[Callable[[dict], str]] = None
    editing:    bool = False


_pending: Optional[_Pending] = None
_lock = threading.Lock()

# Set once at startup by main.py. Signature: (title, detail) -> None for show,
# and () -> None for hide. Both are marshalled onto the Qt thread by the UI.
_show_cb: Optional[Callable[[str, str], None]] = None
_hide_cb: Optional[Callable[[], None]] = None
_log_cb:  Optional[Callable[[str], None]] = None


def bind(show, hide, log=None) -> None:
    """Wire this module to the HUD. Called once from main.py at startup."""
    global _show_cb, _hide_cb, _log_cb
    _show_cb, _hide_cb, _log_cb = show, hide, log


def _log(msg: str) -> None:
    if _log_cb:
        try:
            _log_cb(msg)
        except Exception:
            pass


def request(key: str, title: str, detail: str, run: Callable[[], str],
            fields: Optional[list] = None,
            run_edited: Optional[Callable[[dict], str]] = None) -> str:
    """Park an irreversible action behind the on-screen gate.

    With `fields` and `run_edited`, the banner also offers EDIT: the person can
    change those fields (an email's recipient, subject and text, say) before
    pressing CONFIRM, and `run_edited(values)` is called with what they typed.

    Returns the sentence the tool should hand back to the model — phrased as an
    instruction so the assistant asks the user out loud in their own language,
    rather than reading an English string verbatim."""
    global _pending

    if _show_cb is None:
        # No interface bound (headless, or a very early call). Refuse rather
        # than silently performing something irreversible.
        return (f"I cannot confirm '{title}' right now because the interface is "
                f"not available, so I have not done it.")

    editable = [dict(f) for f in fields] if (fields and run_edited) else None
    with _lock:
        _pending = _Pending(key=key, title=title, detail=detail,
                            run=run, at=time.monotonic(),
                            fields=editable, run_edited=run_edited if editable else None)

    try:
        _show_cb(title, detail)
    except Exception as e:
        with _lock:
            _pending = None
        return f"Could not ask for confirmation: {e}. Nothing was done."

    _log(f"SYS: Awaiting confirmation — {title}")
    return (
        f"[CONFIRMATION_PENDING] I have put a confirmation on screen for: {title}. "
        f"Say ONE short sentence in the user's own language telling them you need "
        f"them to confirm it on the HUD before you do it. Do not claim it is done."
    )


def pending_fields() -> list:
    """The editable fields of the waiting confirmation, or [] — read by the HUD
    when it builds the banner, so the (title, detail) signal stays unchanged."""
    with _lock:
        if _pending is None or not _pending.fields:
            return []
        return [dict(f) for f in _pending.fields]


def begin_edit() -> None:
    """The person pressed EDIT. Typing takes longer than reading, so the
    confirmation stops counting down while they edit."""
    with _lock:
        if _pending is not None:
            _pending.editing = True
            _pending.at = time.monotonic()


def resolve(accepted: bool, values: Optional[dict] = None) -> None:
    """Called by the UI when the user presses CONFIRM or CANCEL. `values` holds
    the edited fields when the person used EDIT.

    Runs the stored callable on a worker thread — this is invoked from the Qt
    thread, and shutting the machine down from inside a button handler would
    freeze the interface on its way out."""
    global _pending

    with _lock:
        p, _pending = _pending, None

    if _hide_cb:
        try:
            _hide_cb()
        except Exception:
            pass

    if p is None:
        return

    if not p.editing and time.monotonic() - p.at > TIMEOUT_SECONDS:
        _log(f"SYS: Confirmation expired — {p.title}")
        return

    if not accepted:
        _log(f"SYS: Cancelled — {p.title}")
        return

    edited = None
    if values and p.run_edited and p.fields:
        originals = {f["key"]: str(f.get("value", "")) for f in p.fields}
        cleaned = {k: str(values.get(k, originals[k])) for k in originals}
        if cleaned != originals:
            edited = cleaned

    def _worker():
        try:
            result = (p.run_edited(edited) if edited is not None else p.run()) or "Done."
            _log(f"SYS: Confirmed — {p.title}. {result}")
        except Exception as e:
            _log(f"ERR: {p.title} failed — {e}")

    threading.Thread(target=_worker, daemon=True,
                     name=f"confirm-{p.key}").start()


def pending_title() -> str:
    """'' when nothing is waiting. Lets an action avoid stacking two banners."""
    with _lock:
        if _pending is None:
            return ""
        if time.monotonic() - _pending.at > TIMEOUT_SECONDS:
            return ""
        return _pending.title
