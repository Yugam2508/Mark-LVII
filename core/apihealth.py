"""Turn a failed connection into one plain sentence the user can act on.

Before this, only a bad key and a dead network were ever shown on screen. Quota,
billing, a blocked key, a region block or Google being overloaded went to the
console only, so Jarvis just sat there looking frozen."""
from __future__ import annotations

import time

# (words that must appear (lowercase), kind, message). First match wins.
_RULES = (
    (("api key not valid", "api_key_invalid", "1007"), "key",
     "Your Gemini API key was rejected as invalid. Re-enter it in settings."),
    (("api key expired", "key expired"), "key",
     "Your Gemini API key has expired. Create a new one and enter it in settings."),
    (("billing", "payment required", "402"), "billing",
     "Google says billing is the problem. Check the billing status of the project the key belongs to."),
    (("resource_exhausted", "quota", "429", "rate limit", "too many requests"), "quota",
     "You've hit the Gemini usage limit (free-tier quota or rate limit). It usually resets "
     "within a minute or by tomorrow; adding billing to the key lifts it."),
    (("permission_denied", "403", "forbidden", "has been suspended", "blocked"), "blocked",
     "Google is refusing this key (permission denied, blocked or suspended). Check it in "
     "Google AI Studio, or make a new key."),
    (("location is not supported", "user location", "not available in your country"), "region",
     "Gemini isn't available from this location. A VPN may be needed."),
    (("unavailable", "503", "overloaded", "internal", "500", "deadline"), "overloaded",
     "Google's servers are overloaded or down right now. This is not your key; Jarvis keeps retrying."),
    (("not_found", "404", "is not found", "not supported for"), "model",
     "This model isn't available to your key. Jarvis will try another."),
    (("timeouterror", "timed out", "getaddrinfo", "cannot connect", "connectionrefused",
      "oserror", "name resolution"), "network",
     "Can't reach Google: check the internet connection or VPN."),
)

_last: dict = {"kind": "", "at": 0.0}


def diagnose(err: str) -> tuple[str, str]:
    """(kind, sentence) for a connection error; ('other', ...) when unrecognised."""
    low = (err or "").lower()
    for words, kind, msg in _RULES:
        if any(w in low for w in words):
            return kind, msg
    short = (err or "unknown error").strip().splitlines()[0][:140]
    return "other", f"The connection failed: {short}"


def should_announce(kind: str, every: float = 120.0) -> bool:
    """Say it once per kind, then at most every two minutes, so a retry loop doesn't spam."""
    now = time.time()
    if kind != _last["kind"] or now - _last["at"] >= every:
        _last["kind"], _last["at"] = kind, now
        return True
    return False


def reset() -> None:
    _last["kind"], _last["at"] = "", 0.0
