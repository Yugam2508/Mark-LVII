"""
core/audio_watch.py — follow headphones, headsets and Bluetooth as they come and go.

THE PROBLEM
    The audio library (PortAudio, via sounddevice) reads the list of devices once,
    when it starts. Turn off a Bluetooth headset and JARVIS keeps writing to a
    device that no longer exists — silence, or a stream that hangs. Plug one in
    and JARVIS never sees it, even when Windows makes it the default. Only a
    restart fixed either.

WHAT THIS DOES
    A background thread notices that the devices changed, two ways:
      * Windows keeps a list of active audio endpoints in the registry
        (MMDevices). A set that changes = something was connected or removed.
        Read every two seconds; cheap, no audio API involved.
      * The streams themselves: the microphone stops delivering audio, or a
        write to the speakers has been stuck for seconds. That catches drivers
        that die without telling Windows, on any OS.
    Then, after a short settle (Bluetooth announces itself in stages), it asks
    the assistant to rebuild its session — keeping the conversation — and
    `reinit_if_needed()`, called just before the new audio streams open,
    restarts PortAudio so it sees the devices that exist NOW.

    Device choice after that is the existing rule in core/audio_devices.py: the
    mic and speakers you picked if they are present, otherwise the system
    default — which on Windows is normally the headset you just connected. When
    your picked device comes back, the next change switches back to it.

Settings: ⚙ → PLUGIN SETTINGS → CONVERSATION & PRESENCE ("Follow audio devices").
"""
from __future__ import annotations

import sys
import threading
import time

_lock = threading.Lock()
_needs_reinit = False
_last_switch = 0.0
_state = {"endpoints": None, "changed_at": 0.0, "reason": "", "started": False}
SETTLE_SECONDS = 2.5
MIC_SILENT_SECONDS = 4.0
WRITE_STUCK_SECONDS = 4.0
MIN_GAP_SECONDS = 8.0          # never rebuild more often than this


def enabled() -> bool:
    try:
        from memory.config_manager import get_plugin_setting
        return bool(get_plugin_setting("conversation", "follow_audio", True))
    except Exception:
        return True


def endpoints() -> frozenset | None:
    """Active audio endpoints as {(direction, name)}; None where it can't be read."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None
    out = set()
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio"
    name_key = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"     # PKEY_Device_FriendlyName
    for direction in ("Render", "Capture"):
        try:
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{direction}")
        except OSError:
            continue
        i = 0
        while True:
            try:
                guid = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, guid) as k:
                    if winreg.QueryValueEx(k, "DeviceState")[0] != 1:     # 1 = active
                        continue
                name = guid
                try:
                    with winreg.OpenKey(root, guid + r"\Properties") as pk:
                        name = str(winreg.QueryValueEx(pk, name_key)[0])
                except OSError:
                    pass
                out.add((direction, name))
            except OSError:
                continue
    return frozenset(out)


def describe_change(old: frozenset, new: frozenset) -> str:
    added = sorted(n for d, n in new - old)
    gone = sorted(n for d, n in old - new)
    parts = []
    if added:
        parts.append("connected: " + ", ".join(dict.fromkeys(added)))
    if gone:
        parts.append("disconnected: " + ", ".join(dict.fromkeys(gone)))
    return "; ".join(parts) or "audio devices changed"


def flag(reason: str) -> None:
    """Something is wrong with the current audio devices; rebuild once things settle."""
    with _lock:
        if not _state["changed_at"]:
            _state["changed_at"] = time.time()
        _state["reason"] = reason


def reinit_if_needed() -> bool:
    """Call with NO audio streams open (between sessions). Restarts PortAudio so
    its device list is current. True when it did."""
    global _needs_reinit
    with _lock:
        if not _needs_reinit:
            return False
        _needs_reinit = False
    try:
        import sounddevice as sd
        sd._terminate()
        sd._initialize()
    except Exception as e:
        print(f"[Audio] could not refresh the device list: {e}")
        return False
    try:
        from core import audio_devices
        audio_devices.list_devices("input", refresh=True)
    except Exception:
        pass
    print("[Audio] device list refreshed")
    return True


def _health(a) -> str:
    """'' when the streams look alive, else why not."""
    now = time.monotonic()
    mic_open = getattr(a, "_mic_open_at", 0.0)
    last_cb = getattr(a, "_mic_last_cb", 0.0)
    if mic_open and now - mic_open > MIC_SILENT_SECONDS and now - last_cb > MIC_SILENT_SECONDS:
        return "the microphone stopped sending audio"
    w = getattr(a, "_spk_write_started", 0.0)
    if w and now - w > WRITE_STUCK_SECONDS:
        return "the speakers stopped taking audio"
    return ""


def _loop() -> None:
    global _needs_reinit, _last_switch
    time.sleep(15)       # let the first session settle
    while True:
        time.sleep(2.0)
        try:
            if not enabled():
                continue
            from core import addons
            a = addons.assistant()
            now_set = endpoints()
            if now_set is not None:
                old = _state["endpoints"]
                _state["endpoints"] = now_set
                if old is not None and now_set != old:
                    flag(describe_change(old, now_set))
            if a is not None:
                why = _health(a)
                if why:
                    flag(why)
            with _lock:
                pending = _state["changed_at"]
                reason = _state["reason"]
            if not pending or time.time() - pending < SETTLE_SECONDS:
                continue
            if time.time() - _last_switch < MIN_GAP_SECONDS:
                continue
            with _lock:
                _state["changed_at"] = 0.0
                _needs_reinit = True
            _last_switch = time.time()
            if a is not None and hasattr(a, "request_reconnect"):
                print(f"[Audio] {reason} — reopening audio")
                try:
                    a.ui.write_log(f"SYS: Audio {reason} — switching devices.")
                except Exception:
                    pass
                # Mark the streams as reset so the health check doesn't fire
                # again before the new ones open.
                a._mic_open_at = 0.0
                a._spk_write_started = 0.0
                a.request_reconnect(keep_context=True, reason="audio device")
        except Exception as e:
            print(f"[Audio] watch: {e}")


def start() -> None:
    if _state["started"]:
        return
    _state["started"] = True
    _state["endpoints"] = endpoints()
    threading.Thread(target=_loop, name="audio_watch", daemon=True).start()
