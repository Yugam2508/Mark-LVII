"""
plugins/spotify_control.py — Spotify by voice, through the Spotify Web API.

    "Play Blinding Lights"                    action=play  query="Blinding Lights"
    "Play some Arctic Monkeys"                action=play  query="Arctic Monkeys" kind=artist
    "Play my workout playlist"                action=play  query=workout kind=my_playlist
    "Pause" / "Resume" / "Next" / "Previous"  action=pause | resume | next | previous
    "What's playing?"                         action=now_playing
    "Turn Spotify up to 70"                   action=volume volume=70
    "Shuffle on"                              action=shuffle on=true
    "Like this song"                          action=like
    "Add this to my chill playlist"           action=add_to_playlist playlist=chill
    "Queue Bohemian Rhapsody"                 action=queue query="Bohemian Rhapsody"

SETUP (once, free) — the readme's Spotify section has the clicks:
    1. Create an app at developer.spotify.com/dashboard with the redirect URI
       http://127.0.0.1:8888/callback and tick "Web API".
    2. Paste its Client ID in ⚙ → PLUGIN SETTINGS → SPOTIFY and press CONNECT.
    Sign-in uses PKCE, so there is no client secret to store. Tokens are kept in
    config/token_spotify.json (git-ignored) and refreshed by themselves.

LIMITS SPOTIFY SETS, NOT THIS FILE
    Controlling playback (play, pause, skip, volume, queue) needs Spotify Premium.
    On a free account the API answers 403 PREMIUM_REQUIRED and this plugin says so;
    "what's playing", liking songs and adding to playlists still work.
    Playback goes to an open Spotify app (desktop, phone or web player). If none is
    open, the desktop app is launched and the plugin waits a few seconds for it.

The media keys in computer_settings still work for plain play/pause without any of
this; this plugin is for choosing WHAT plays.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser

from core import outcome
from memory.config_manager import CONFIG_DIR, get_plugin_setting

NAMESPACE = "spotify"
TOKEN_FILE = CONFIG_DIR / "token_spotify.json"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
API = "https://api.spotify.com/v1"
ACCOUNTS = "https://accounts.spotify.com"
SCOPES = " ".join([
    "user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing",
    "playlist-read-private", "playlist-modify-private", "playlist-modify-public",
    "user-library-read", "user-library-modify",
])
NOT_CONNECTED = ("Spotify is not connected. Open ⚙ → PLUGIN SETTINGS → SPOTIFY, paste your "
                 "Client ID and press CONNECT SPOTIFY (see the Spotify section of ADDONS.md).")

_token_lock = threading.Lock()


# ── sign-in (PKCE) ────────────────────────────────────────────────────────────

def _client_id(values: dict | None = None) -> str:
    if values and str(values.get("client_id") or "").strip():
        return str(values["client_id"]).strip()
    return str(get_plugin_setting(NAMESPACE, "client_id", "") or "").strip()


def _save_tokens(tok: dict) -> None:
    tok = dict(tok)
    tok["expires_at"] = time.time() + int(tok.get("expires_in", 3600)) - 60
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tok, indent=2), encoding="utf-8")


def _wait_for_code(state: str, timeout: float = 300) -> str | None:
    """Serve one request on the redirect URI and return the ?code= it carries."""
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (name required by BaseHTTPRequestHandler)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            ok = q.get("state", [""])[0] == state and "code" in q
            if ok:
                result["code"] = q["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = ("JARVIS is connected to Spotify. You can close this tab." if ok else
                   "Spotify sign-in did not finish: " + q.get("error", ["unknown"])[0])
            self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

        def log_message(self, *_):
            pass

    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler)
    server.timeout = 2
    deadline = time.time() + timeout
    try:
        while "code" not in result and time.time() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    return result.get("code")


def connect(values: dict | None = None) -> tuple[bool, str]:
    """The CONNECT SPOTIFY button. Runs on the settings panel's worker thread."""
    import requests

    cid = _client_id(values)
    if not cid:
        return False, "Paste your Spotify app's Client ID first."
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(16)
    url = f"{ACCOUNTS}/authorize?" + urllib.parse.urlencode({
        "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT_URI,
        "scope": SCOPES, "state": state, "code_challenge_method": "S256",
        "code_challenge": challenge,
    })
    try:
        waiter_result: dict = {}
        waiter = threading.Thread(target=lambda: waiter_result.update(code=_wait_for_code(state)))
        waiter.start()
        time.sleep(0.3)  # let the local server bind before the browser can redirect to it
        webbrowser.open(url)
        waiter.join()
    except OSError as e:
        return False, f"Could not listen on port {REDIRECT_PORT}: {e}"
    code = waiter_result.get("code")
    if not code:
        return False, "Spotify sign-in did not finish (closed or timed out)."

    r = requests.post(f"{ACCOUNTS}/api/token", timeout=15, data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "client_id": cid, "code_verifier": verifier})
    if r.status_code != 200:
        return False, f"Spotify refused the sign-in: {r.text[:200]}"
    _save_tokens(r.json())
    me = _api("GET", "/me")
    if isinstance(me, dict) and me.get("id"):
        plan = me.get("product", "?")
        note = "" if plan == "premium" else " (playback control needs Premium)"
        return True, f"Connected as {me.get('display_name') or me['id']} — {plan}{note} ✓"
    return False, "Signed in, but the test call failed."


def _access_token() -> str | None:
    import requests
    with _token_lock:
        if not TOKEN_FILE.is_file():
            return None
        try:
            tok = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if time.time() < tok.get("expires_at", 0):
            return tok.get("access_token")
        cid = _client_id()
        if not (cid and tok.get("refresh_token")):
            return None
        r = requests.post(f"{ACCOUNTS}/api/token", timeout=15, data={
            "grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
            "client_id": cid})
        if r.status_code != 200:
            return None
        new = r.json()
        new.setdefault("refresh_token", tok["refresh_token"])  # Spotify may not rotate it
        _save_tokens(new)
        return new["access_token"]


class SpotifyError(Exception):
    def __init__(self, status: int, reason: str, message: str):
        super().__init__(message)
        self.status, self.reason = status, reason


def _api(method: str, path: str, params: dict | None = None, body: dict | None = None):
    import requests
    token = _access_token()
    if token is None:
        raise SpotifyError(401, "NOT_CONNECTED", NOT_CONNECTED)
    r = requests.request(method, API + path, params=params, json=body, timeout=15,
                         headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 429:
        raise SpotifyError(429, "RATE_LIMITED", "Spotify is rate limiting; try again shortly")
    if r.status_code >= 400:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        raise SpotifyError(r.status_code, str(err.get("reason") or ""),
                           str(err.get("message") or r.text[:200]))
    if r.status_code == 204 or not r.content:
        return None
    return r.json()


# ── playback helpers ──────────────────────────────────────────────────────────

def _devices() -> list[dict]:
    return (_api("GET", "/me/player/devices") or {}).get("devices", [])


def _ensure_device(player) -> str | None:
    """An available device id, launching the desktop app if nothing is open."""
    devs = _devices()
    if not devs:
        try:
            from actions.open_app import open_app
            open_app({"app_name": "spotify"}, player=player)
        except Exception:
            pass
        for _ in range(10):  # the desktop app takes a few seconds to register
            time.sleep(1.5)
            devs = _devices()
            if devs:
                break
    if not devs:
        return None
    active = [d for d in devs if d.get("is_active")]
    computer = [d for d in devs if d.get("type") == "Computer"]
    return (active or computer or devs)[0]["id"]


class DeviceNotFound(Exception):
    def __init__(self, question: str):
        super().__init__(question)
        self.question = question


def _aliases() -> dict[str, str]:
    """Nicknames from settings: "desktop=DESKTOP-AB12, laptop=ROG-G14"."""
    raw = str(get_plugin_setting(NAMESPACE, "device_aliases", "") or "")
    out = {}
    for pair in raw.split(","):
        k, sep, v = pair.partition("=")
        if sep and k.strip() and v.strip():
            out[k.strip().lower()] = v.strip().lower()
    return out


def resolve_device(spec: str, player=None) -> dict:
    """The Spotify Connect device a spoken name means. Raises DeviceNotFound with a
    question to ask when it is not clear."""
    import platform
    want = (spec or "").strip().lower()
    want = _aliases().get(want, want)
    devs = _devices()
    here = platform.node().lower()
    if want in ("here", "this computer", "this pc", "this laptop", "computer here") or (
            want and want in here):
        mine = [d for d in devs if d.get("name", "").lower() == here]
        if not mine:
            # The app on this computer is closed: open it and wait for it to appear.
            _ensure_device(player)
            devs = _devices()
            mine = [d for d in devs if d.get("name", "").lower() == here] or \
                [d for d in devs if d.get("type") == "Computer"]
        if mine:
            return mine[0]
    exact = [d for d in devs if d.get("name", "").lower() == want]
    if exact:
        return exact[0]
    named = [d for d in devs if want and want in d.get("name", "").lower()]
    if len(named) == 1:
        return named[0]
    kinds = {"phone": "Smartphone", "mobile": "Smartphone", "oneplus": "Smartphone",
             "tablet": "Tablet", "tv": "TV", "speaker": "Speaker", "laptop": "Computer",
             "desktop": "Computer", "pc": "Computer", "computer": "Computer"}
    kind = next((t for w, t in kinds.items() if w in want), None)
    typed = [d for d in devs if kind and d.get("type") == kind]
    if len(typed) == 1:
        return typed[0]
    if kind == "Computer" and len(typed) > 1 and ("laptop" in want or "desktop" in want):
        # Two computers and no nickname: this one has a battery if it is the laptop.
        try:
            import psutil
            on_laptop = psutil.sensors_battery() is not None
        except Exception:
            on_laptop = None
        if on_laptop is not None:
            this_one = ("laptop" in want) == on_laptop
            pick = [d for d in typed if (d.get("name", "").lower() == here) == this_one]
            if len(pick) == 1:
                return pick[0]
    names = ", ".join(d.get("name", "?") for d in (typed or named or devs)) or "none"
    if not devs:
        raise DeviceNotFound("No Spotify app is open on any device. Open Spotify on the "
                             "device you want, then ask again.")
    raise DeviceNotFound(f"Which device? Spotify can see: {names}.")


def _playback(method: str, path: str, player, params=None, body=None, device_id=None):
    """A player command, retried once on a device when none was active."""
    if device_id:
        return _api(method, path, params={**(params or {}), "device_id": device_id}, body=body)
    try:
        return _api(method, path, params=params, body=body)
    except SpotifyError as e:
        if e.status != 404:  # 404 = NO_ACTIVE_DEVICE
            raise
    device = _ensure_device(player)
    if device is None:
        raise SpotifyError(404, "NO_ACTIVE_DEVICE",
                           "no Spotify app is open on any device; open Spotify and try again")
    return _api(method, path, params={**(params or {}), "device_id": device}, body=body)


def _now_playing() -> dict | None:
    data = _api("GET", "/me/player/currently-playing")
    return (data or {}).get("item")


def _describe(item: dict) -> str:
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    return f"{item.get('name', '?')} — {artists}" if artists else item.get("name", "?")


def _find_my_playlist(name: str) -> dict | None:
    name = name.lower().strip()
    best = None
    url_params = {"limit": 50, "offset": 0}
    for _ in range(4):  # up to 200 playlists
        page = _api("GET", "/me/playlists", params=url_params) or {}
        for pl in page.get("items", []) or []:
            if not pl:
                continue
            title = (pl.get("name") or "").lower()
            if title == name:
                return pl
            if best is None and name in title:
                best = pl
        if not page.get("next"):
            break
        url_params["offset"] += 50
    return best


def _show(player, text: str) -> None:
    if player:
        try:
            player.show_content("SPOTIFY", text)
        except Exception:
            pass


# ── actions ───────────────────────────────────────────────────────────────────

def _play(p, player) -> str:
    query = (p.get("query") or "").strip()
    kind = (p.get("kind") or "track").lower()
    dev = resolve_device(p["device"], player) if p.get("device") else None
    did = dev["id"] if dev else None
    where = dev.get("name") if dev else None
    if not query:
        if dev:
            _api("PUT", "/me/player", body={"device_ids": [did], "play": True})
        else:
            _playback("PUT", "/me/player/play", player)
        return outcome.done("spotify_resume", device=where)

    if kind == "my_playlist":
        pl = _find_my_playlist(query)
        if pl is None:
            return outcome.failed("spotify_play", "none of your playlists has that name",
                                  query=query)
        _playback("PUT", "/me/player/play", player, body={"context_uri": pl["uri"]},
                  device_id=did)
        _show(player, f"▶ Playlist: {pl['name']}" + (f"  ·  on {where}" if where else ""))
        return outcome.done("spotify_play", kind="your playlist", device=where) + "\n" + \
            outcome.untrusted("spotify", f"Playlist: {pl['name']}")

    if kind not in ("track", "artist", "album", "playlist"):
        kind = "track"
    res = _api("GET", "/search", params={"q": query, "type": kind, "limit": 1})
    items = (res or {}).get(kind + "s", {}).get("items", [])
    items = [i for i in items if i]
    if not items:
        return outcome.failed("spotify_play", f"Spotify found no {kind} for that", query=query)
    item = items[0]
    body = {"uris": [item["uri"]]} if kind == "track" else {"context_uri": item["uri"]}
    _playback("PUT", "/me/player/play", player, body=body, device_id=did)
    label = _describe(item) if kind in ("track", "album") else item.get("name", "?")
    _show(player, f"▶ {kind.title()}: {label}" + (f"  ·  on {where}" if where else ""))
    return outcome.done("spotify_play", kind=kind, device=where) + "\n" + \
        outcome.untrusted("spotify", f"Now playing {kind}: {label}")


def _simple(path: str, method: str, action: str):
    def handler(p, player) -> str:
        _playback(method, path, player)
        return outcome.done(action)
    return handler


def _now(p, player) -> str:
    item = _now_playing()
    if not item:
        return outcome.done("spotify_now_playing", playing=False)
    text = _describe(item)
    _show(player, f"♪ {text}")
    return outcome.done("spotify_now_playing", playing=True) + "\n" + \
        outcome.untrusted("spotify", f"Now playing: {text}")


def _volume(p, player) -> str:
    try:
        v = max(0, min(100, int(p.get("volume"))))
    except (TypeError, ValueError):
        return outcome.ask("spotify_volume", "What volume, from 0 to 100?")
    _playback("PUT", "/me/player/volume", player, params={"volume_percent": v})
    return outcome.done("spotify_volume", volume=v)


def _shuffle(p, player) -> str:
    on = p.get("on")
    on = True if on is None else bool(on)
    _playback("PUT", "/me/player/shuffle", player, params={"state": "true" if on else "false"})
    return outcome.done("spotify_shuffle", shuffle=on)


def _like(p, player) -> str:
    item = _now_playing()
    if not item:
        return outcome.failed("spotify_like", "nothing is playing right now")
    _api("PUT", "/me/tracks", params={"ids": item["id"]})
    return outcome.done("spotify_like") + "\n" + outcome.untrusted("spotify", _describe(item))


def _add_to_playlist(p, player) -> str:
    name = (p.get("playlist") or "").strip()
    if not name:
        return outcome.ask("spotify_add_to_playlist", "Which playlist should I add it to?")
    item = _now_playing()
    if not item:
        return outcome.failed("spotify_add_to_playlist", "nothing is playing right now")
    pl = _find_my_playlist(name)
    if pl is None:
        return outcome.failed("spotify_add_to_playlist", "none of your playlists has that name",
                              playlist=name)
    _api("POST", f"/playlists/{pl['id']}/tracks", body={"uris": [item["uri"]]})
    return outcome.done("spotify_add_to_playlist") + "\n" + \
        outcome.untrusted("spotify", f"Added {_describe(item)} to playlist {pl['name']}")


def _queue(p, player) -> str:
    query = (p.get("query") or "").strip()
    if not query:
        return outcome.ask("spotify_queue", "Which song should I queue?")
    res = _api("GET", "/search", params={"q": query, "type": "track", "limit": 1})
    items = [i for i in (res or {}).get("tracks", {}).get("items", []) if i]
    if not items:
        return outcome.failed("spotify_queue", "Spotify found no song for that", query=query)
    _playback("POST", "/me/player/queue", player, params={"uri": items[0]["uri"]})
    return outcome.done("spotify_queue") + "\n" + \
        outcome.untrusted("spotify", f"Queued: {_describe(items[0])}")


def _devices_action(p, player) -> str:
    devs = _devices()
    if not devs:
        return outcome.done("spotify_devices", count=0,
                            note="no Spotify app is open on any device")
    lines = [f"{d.get('name')} ({d.get('type')}){' — playing now' if d.get('is_active') else ''}"
             for d in devs]
    _show(player, "Devices:\n" + "\n".join(lines))
    return outcome.done("spotify_devices", count=len(devs)) + "\n" + \
        outcome.untrusted("spotify", "\n".join(lines))


def _transfer(p, player) -> str:
    if not p.get("device"):
        return outcome.ask("spotify_transfer", "Which device should I move the music to?")
    dev = resolve_device(p["device"], player)
    _api("PUT", "/me/player", body={"device_ids": [dev["id"]], "play": True})
    _show(player, f"▶ Moved to {dev.get('name')}")
    return outcome.done("spotify_transfer", device=dev.get("name"))


_ACTIONS = {
    "play": _play,
    "pause": _simple("/me/player/pause", "PUT", "spotify_pause"),
    "resume": _simple("/me/player/play", "PUT", "spotify_resume"),
    "next": _simple("/me/player/next", "POST", "spotify_next"),
    "previous": _simple("/me/player/previous", "POST", "spotify_previous"),
    "now_playing": _now,
    "volume": _volume,
    "shuffle": _shuffle,
    "like": _like,
    "add_to_playlist": _add_to_playlist,
    "queue": _queue,
    "devices": _devices_action,
    "transfer": _transfer,
}

PLUGIN = {
    "name": "spotify_control",
    "description": (
        "Controls Spotify: play a specific song, artist, album, public playlist or one "
        "of the user's own playlists, on a chosen device (phone, laptop, desktop) if "
        "asked; move playback to another device; list devices; pause, resume, skip, "
        "previous; what is playing; "
        "Spotify volume; shuffle; like the current song; add it to a playlist; queue a "
        "song. Use whenever the user mentions Spotify or asks to play music by name and "
        "has not asked for YouTube. For system volume use computer_settings instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": list(_ACTIONS)},
            "query": {
                "type": "STRING",
                "description": "For play/queue: what to search, e.g. 'Blinding Lights The Weeknd'",
            },
            "kind": {
                "type": "STRING",
                "enum": ["track", "artist", "album", "playlist", "my_playlist"],
                "description": "For play: what the query names. my_playlist = one of the "
                               "user's own playlists. Default track.",
            },
            "volume": {"type": "INTEGER", "description": "For volume: 0-100"},
            "on": {"type": "BOOLEAN", "description": "For shuffle: true or false"},
            "playlist": {"type": "STRING", "description": "For add_to_playlist: playlist name"},
            "device": {"type": "STRING",
                       "description": "For play/transfer: where to play — 'phone', 'laptop', "
                                      "'desktop', 'here', or a device name. Leave empty to "
                                      "keep playing where it is."},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Spotify: play/pause/next/now_playing/volume/like/queue.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "SPOTIFY",
    "fields": [
        {"key": "client_id", "label": "Client ID from developer.spotify.com/dashboard",
         "type": "text", "placeholder": "32 letters and numbers"},
        {"key": "device_aliases", "label": "Device nicknames (optional)", "type": "text",
         "placeholder": "desktop=DESKTOP-AB12, laptop=ROG-ZEPHYRUS"},
    ],
    "action": {"label": "CONNECT SPOTIFY", "run": connect},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "").lower()
    handler = _ACTIONS.get(action)
    if handler is None:
        return outcome.failed("spotify", f"unknown action {action}")
    try:
        return handler(parameters, player)
    except DeviceNotFound as e:
        return outcome.ask(f"spotify_{action}", e.question)
    except SpotifyError as e:
        if e.reason == "NOT_CONNECTED":
            return outcome.failed(f"spotify_{action}", NOT_CONNECTED)
        if e.reason == "PREMIUM_REQUIRED" or (e.status == 403 and "premium" in str(e).lower()):
            return outcome.failed(f"spotify_{action}", "Spotify only allows controlling "
                                  "playback with a Premium account")
        return outcome.failed(f"spotify_{action}", f"Spotify error: {e}")
    except Exception as e:  # network errors and anything unexpected — never raise
        return outcome.failed(f"spotify_{action}", f"Spotify error: {e}")
