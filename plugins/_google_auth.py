"""
plugins/_google_auth.py — one Google sign-in shared by the Gmail and Calendar plugins.

A file starting with "_" is a helper, not a skill: the plugin loader skips it and
the plugins beside it import it.

HOW SIGN-IN WORKS
    Google only lets an app read your mail or calendar after you approve it in a
    browser. That needs an "OAuth client", which you create once, for free, in the
    Google Cloud Console (the plugin settings panel links the steps):

      1. The client file you download from Google ("client_secret_....json") goes
         in the `config/` folder, or its path goes in ⚙ → PLUGIN SETTINGS.
      2. Pressing CONNECT GOOGLE opens your browser; you approve once.
      3. The approval is saved as `config/token_google.json` and refreshed by
         itself from then on. Delete that file to sign out.

    Both files are covered by .gitignore (`**/client_secret*.json`,
    `**/token*.json`), so a fork or a pull request cannot publish them.

ONE APPROVAL FOR ALL THE GOOGLE PLUGINS
    The scopes below cover Calendar events, Gmail (read, label, draft and send) and
    Google Tasks (the to-do list), so connecting once enables gmail_control,
    calendar_control and todo_list. `gmail.modify` is the narrowest Gmail
    scope that can also send; it cannot permanently delete mail.

WHY THE GOOGLE LIBRARIES ARE IMPORTED INSIDE FUNCTIONS
    Plugin discovery executes every file in plugins/ at every launch. Importing
    googleapiclient at module scope would add its import time to every start-up
    for people who never use Gmail. They load on first use instead.
"""
from __future__ import annotations

import threading
from pathlib import Path

from memory.config_manager import CONFIG_DIR, get_plugin_setting

NAMESPACE = "google"
TOKEN_FILE = CONFIG_DIR / "token_google.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/tasks",   # todo_list — Google Tasks syncs to the phone
    "https://www.googleapis.com/auth/drive.readonly",   # google_drive — find and read your files
    "https://www.googleapis.com/auth/drive.file",       # google_drive — create Docs (only its own)
]

# What each API needs, so a sign-in made before Drive was added keeps working for
# Gmail/Calendar/Tasks and only Drive asks for a reconnect.
NEEDS = {
    "gmail": ["https://www.googleapis.com/auth/gmail.modify"],
    "calendar": ["https://www.googleapis.com/auth/calendar.events"],
    "tasks": ["https://www.googleapis.com/auth/tasks"],
    "drive": ["https://www.googleapis.com/auth/drive.readonly",
              "https://www.googleapis.com/auth/drive.file"],
    "docs": ["https://www.googleapis.com/auth/drive.file"],
}
RECONNECT = ("Your Google sign-in is from before this feature was added. Open ⚙ → PLUGIN "
             "SETTINGS → GOOGLE and press CONNECT GOOGLE once more to allow it.")

SETUP_STEPS = (
    "Google is not connected. Open ⚙ → PLUGIN SETTINGS → GOOGLE and press "
    "CONNECT GOOGLE. The first time, you need a free OAuth client file from "
    "console.cloud.google.com (see the Google section of the readme)."
)

# googleapiclient service objects are not thread-safe, and tools run on worker
# threads; only the credential refresh is shared, so only it is locked.
_lock = threading.Lock()


def libraries_installed() -> bool:
    import importlib.util
    return all(importlib.util.find_spec(m) is not None
               for m in ("googleapiclient", "google_auth_oauthlib"))


def find_client_secret() -> Path | None:
    """The OAuth client file: the path set in settings, else one in config/."""
    configured = str(get_plugin_setting(NAMESPACE, "client_secret_path", "") or "").strip()
    if configured:
        p = Path(configured).expanduser()
        return p if p.is_file() else None
    found = sorted(CONFIG_DIR.glob("client_secret*.json"))
    return found[0] if found else None


def load_credentials():
    """Valid credentials, refreshed if needed — or None when not connected."""
    if not libraries_installed() or not TOKEN_FILE.is_file():
        return None
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    with _lock:
        try:
            # Without `scopes`: the token keeps exactly what was granted. Passing the
            # full list would ask Google for scopes this sign-in never had on the next
            # refresh, which fails and would log Gmail out too.
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
        except (ValueError, OSError):
            return None
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                return None  # revoked or expired for good: the user must reconnect
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            return creds
    return None


def has_access(api: str) -> bool:
    """True when the saved sign-in includes what `api` needs."""
    creds = load_credentials()
    if creds is None:
        return False
    granted = set(creds.scopes or [])
    return all(s in granted for s in NEEDS.get(api, []))


def service(api: str, version: str):
    """A fresh API client, or None when Google is not connected."""
    creds = load_credentials()
    if creds is None:
        return None
    from googleapiclient.discovery import build
    return build(api, version, credentials=creds, cache_discovery=False)


def connect(values: dict | None = None) -> tuple[bool, str]:
    """The CONNECT GOOGLE button: opens the browser for the one-time approval.

    Runs on the settings panel's worker thread, never the Qt thread, so blocking
    on the browser round-trip is fine."""
    if not libraries_installed():
        return False, ("Missing libraries. Run: pip install google-api-python-client "
                       "google-auth-oauthlib")
    if values and str(values.get("client_secret_path") or "").strip():
        secret = Path(str(values["client_secret_path"]).strip()).expanduser()
        if not secret.is_file():
            return False, f"No file at {secret}"
    else:
        secret = find_client_secret()
    if secret is None:
        return False, ("No OAuth client file. Download it from Google Cloud Console "
                       "and put it in the config folder (see readme).")

    from google_auth_oauthlib.flow import InstalledAppFlow
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300,
                                      authorization_prompt_message="",
                                      success_message="JARVIS is connected to Google. "
                                                      "You can close this tab.")
    except Exception as e:  # browser closed, timeout, bad client file
        return False, f"Google sign-in did not finish: {e}"
    if not creds or not creds.valid:
        return False, "Google sign-in did not finish."

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    # Check it really works before saying so.
    try:
        from googleapiclient.discovery import build
        profile = build("gmail", "v1", credentials=creds,
                        cache_discovery=False).users().getProfile(userId="me").execute()
        return True, f"Connected as {profile.get('emailAddress', 'your Google account')} ✓"
    except Exception as e:
        return False, f"Signed in, but the test call failed: {e}"


def disconnect() -> None:
    TOKEN_FILE.unlink(missing_ok=True)


PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "GOOGLE (GMAIL, CALENDAR, TASKS, DRIVE)",
    "fields": [
        {
            "key": "client_secret_path",
            "label": "OAuth client file (leave empty to use config/client_secret*.json)",
            "type": "text",
            "placeholder": "C:/Users/you/Downloads/client_secret_123.json",
        },
        {
            "key": "send_requires_confirm",
            "label": "Ask me on screen before sending any email",
            "type": "toggle",
            "default": True,
        },
    ],
    "action": {"label": "CONNECT GOOGLE", "run": connect},
}
