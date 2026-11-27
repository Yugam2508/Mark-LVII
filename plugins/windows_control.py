"""
plugins/windows_control.py — the windows on your screens, by voice.

    "Switch to Chrome" / "bring up Spotify"                 focus
    "Snap VS Code to the left" / "put this on the right"    snap left|right|top|bottom|full
    "Move Spotify to my other screen"                       other_screen
    "Minimise everything" / "show the desktop"              minimize_all
    "Maximise this" / "minimise Discord" / "restore it"     maximize / minimize / restore
    "Close Notepad"                                         close (politely: the app can still ask to save)
    "What windows are open?"                                list

Windows only (user32 through ctypes, no extra packages). "this" / "it" means the window in front.
The window logic (which window a name means, where a snapped window goes) is plain Python and tested;
the Windows calls are kept in one small class.
"""
from __future__ import annotations

import re
import sys

from core import outcome

WINDOWS = sys.platform.startswith("win")
_IGNORE = re.compile(r"^(program manager|settings|microsoft text input application|windows input experience|"
                     r"nvidia geforce overlay|task switching|start|search)$", re.I)


def match(name: str, windows: list[tuple[int, str]]) -> tuple[int, str] | None:
    """The window a spoken name means: exact title, then a word match in the title (app names
    usually come last: 'Inbox — Gmail — Google Chrome'), the shortest title winning ties."""
    q = (name or "").strip().lower()
    if not q:
        return None
    cands = [(h, t) for h, t in windows if t and not _IGNORE.match(t.strip())]
    exact = [w for w in cands if w[1].lower() == q]
    if exact:
        return exact[0]
    words = [w for w in re.findall(r"\w+", q) if len(w) > 1]
    scored = []
    for h, t in cands:
        low = t.lower().strip()
        if low.endswith(q):                  # "… - Google Chrome": the app's own name comes last
            scored.append((0, len(t), h, t))
        elif low.startswith(q):
            scored.append((1, len(t), h, t))
        elif q in low:
            scored.append((2, len(t), h, t))
        elif words and all(w in low for w in words):
            scored.append((3, len(t), h, t))
    if not scored:
        return None
    scored.sort()
    return scored[0][2], scored[0][3]


def snap_rect(area: tuple[int, int, int, int], where: str) -> tuple[int, int, int, int]:
    """(x, y, w, h) inside a monitor's work area (left, top, right, bottom) for a snap position."""
    l, t, r, b = area
    w, h = r - l, b - t
    return {
        "left": (l, t, w // 2, h), "right": (l + w // 2, t, w - w // 2, h),
        "top": (l, t, w, h // 2), "bottom": (l, t + h // 2, w, h - h // 2),
        "full": (l, t, w, h),
    }.get(where, (l, t, w, h))


class _Win:
    """The few user32 calls needed. Only built on Windows."""
    SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE = 6, 3, 9
    WM_CLOSE = 0x0010

    def __init__(self):
        import ctypes
        import ctypes.wintypes as wt
        self.c, self.wt = ctypes, wt
        self.u = ctypes.windll.user32
        self.u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]

    def list(self) -> list[tuple[int, str]]:
        out = []
        c, wt = self.c, self.wt
        proto = c.WINFUNCTYPE(c.c_bool, wt.HWND, wt.LPARAM)

        def each(hwnd, _):
            if self.u.IsWindowVisible(hwnd):
                n = self.u.GetWindowTextLengthW(hwnd)
                if n:
                    buf = c.create_unicode_buffer(n + 1)
                    self.u.GetWindowTextW(hwnd, buf, n + 1)
                    out.append((int(hwnd), buf.value))
            return True
        self.u.EnumWindows(proto(each), 0)
        return out

    def front(self) -> tuple[int, str]:
        h = self.u.GetForegroundWindow()
        n = self.u.GetWindowTextLengthW(h)
        buf = self.c.create_unicode_buffer(n + 1)
        self.u.GetWindowTextW(h, buf, n + 1)
        return int(h), buf.value

    def show(self, h: int, how: int) -> None:
        self.u.ShowWindow(h, how)

    def focus(self, h: int) -> None:
        if self.u.IsIconic(h):
            self.u.ShowWindow(h, self.SW_RESTORE)
        self.u.SetForegroundWindow(h)

    def close(self, h: int) -> None:
        self.u.PostMessageW(h, self.WM_CLOSE, 0, 0)

    def monitors(self) -> list[tuple[int, int, int, int]]:
        """Work areas (left, top, right, bottom) of every monitor."""
        c, wt = self.c, self.wt
        areas = []

        class MONITORINFO(c.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]
        proto = c.WINFUNCTYPE(c.c_bool, wt.HMONITOR, wt.HDC, c.POINTER(wt.RECT), wt.LPARAM)

        def each(hmon, _hdc, _rect, _):
            mi = MONITORINFO()
            mi.cbSize = c.sizeof(MONITORINFO)
            self.u.GetMonitorInfoW(hmon, c.byref(mi))
            r = mi.rcWork
            areas.append((r.left, r.top, r.right, r.bottom))
            return True
        self.u.EnumDisplayMonitors(0, 0, proto(each), 0)
        return areas

    def rect(self, h: int) -> tuple[int, int, int, int]:
        r = self.wt.RECT()
        self.u.GetWindowRect(h, self.c.byref(r))
        return r.left, r.top, r.right, r.bottom

    def place(self, h: int, x: int, y: int, w: int, ht: int) -> None:
        self.show(h, self.SW_RESTORE)
        self.u.SetWindowPos(h, 0, x, y, w, ht, 0x0040)          # SWP_SHOWWINDOW


_win = None


def win():
    global _win
    if _win is None:
        _win = _Win()
    return _win


def _target(name: str):
    w = win()
    if (name or "").strip().lower() in ("", "this", "it", "that", "current", "the window"):
        return w.front()
    return match(name, w.list())


def monitor_of(rect: tuple[int, int, int, int], areas: list[tuple[int, int, int, int]]) -> int:
    cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    for i, (l, t, r, b) in enumerate(areas):
        if l <= cx < r and t <= cy < b:
            return i
    return 0


PLUGIN = {
    "name": "windows_control",
    "description": (
        "Arranges the windows on this PC's screens: focus (bring an app's window to the front: 'switch to "
        "Chrome'), snap a window left / right / top / bottom / full, move it to the other screen, maximize, "
        "minimize, restore, close (politely — the app can still ask to save), minimize_all ('show the desktop'), "
        "list the open windows. name = words of the app or window title, or 'this' for the window in front."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["focus", "snap", "other_screen", "maximize", "minimize", "restore",
                                                  "close", "minimize_all", "list"]},
            "name": {"type": "STRING", "description": "The app or window, e.g. 'Spotify', 'VS Code', or 'this'"},
            "where": {"type": "STRING", "enum": ["left", "right", "top", "bottom", "full"], "description": "For snap"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Windows: focus, snap, other screen, max/min, close, show desktop.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    name = str(parameters.get("name") or "")
    if not WINDOWS and _win is None:
        return outcome.failed("windows_control", "window control is built for Windows")
    try:
        w = win()
        if action == "list":
            titles = [t for _, t in w.list() if not _IGNORE.match(t.strip())]
            return outcome.done("windows", count=len(titles)) + "\n" + outcome.untrusted("windows", "\n".join(titles[:30]))
        if action == "minimize_all":
            for h, t in w.list():
                if not _IGNORE.match(t.strip()):
                    w.show(h, _Win.SW_MINIMIZE)
            return outcome.done("minimize_all")
        hit = _target(name)
        if not hit:
            return outcome.failed(f"window_{action}", f"no open window matches {name}")
        h, title = hit
        if action == "focus":
            w.focus(h)
        elif action == "maximize":
            w.show(h, _Win.SW_MAXIMIZE)
        elif action == "minimize":
            w.show(h, _Win.SW_MINIMIZE)
        elif action == "restore":
            w.show(h, _Win.SW_RESTORE)
        elif action == "close":
            w.close(h)
        elif action in ("snap", "other_screen"):
            areas = w.monitors() or [(0, 0, 1920, 1040)]
            cur = monitor_of(w.rect(h), areas)
            if action == "other_screen":
                if len(areas) < 2:
                    return outcome.failed("window_other_screen", "there's only one screen")
                area = areas[(cur + 1) % len(areas)]
                where = "full"
            else:
                area = areas[cur]
                where = str(parameters.get("where") or "left")
            x, y, ww, hh = snap_rect(area, where)
            w.place(h, x, y, ww, hh)
            w.focus(h)
        else:
            return outcome.failed("windows_control", f"unknown action {action}")
        return outcome.done(f"window_{action}", window=title[:60])
    except Exception as e:
        return outcome.failed(f"window_{action}", str(e)[:160])
