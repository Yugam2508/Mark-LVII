# Planned additions and open items

A running list of what we want to add or still need to do. Newest ideas go at the
bottom of their section; finished items move to **Done** with the date.

## To build

- [ ] **Spotify: choose the device.** "Play this on my phone" / "move it to the
      laptop" — pick a Spotify Connect device by name instead of only the active one
      or this PC. (`plugins/spotify_control.py`)

## To set up / test

- [ ] **Voice test on the G14** — wake word, "what time is it", "open Notepad",
      microphone choice in ⚙ → audio. (Typed commands are being tested first.)
- [ ] **Connect the add-ons on the G14** — Spotify, Google (Gmail, Calendar, Tasks),
      device sync, knowledge folder; Claude and Home Assistant optional.
- [ ] **Tailscale for the OnePlus 13** — Tailscale on phone + PCs, then the phone
      dashboard over the Tailscale address (ADDONS.md §9).
- [ ] **Install on the desktop** (Aftershock, 9800X3D + RTX 5070) once the PyQt6 pin
      is on `main`; set Whisper to GPU if using the pipeline engine.
- [ ] **Interrupt by voice** — try with headphones and with speakers; pick normal or
      careful.

## Known issues

- PyQt6 6.12 would not load on the G14 ("DLL load failed while importing QtWidgets:
  The specified procedure could not be found"), even with the latest Visual C++
  runtime and MiKTeX's Qt removed from PATH. 6.9 works; requirements are pinned
  below 6.10. Worth retrying newer versions later.

## Done

- 2026-11-24 — Gmail, Calendar, to-do (Google Tasks), Spotify, Claude provider,
  agents (daily digest, study coach, deal hunter), knowledge folder, voice
  interrupt, Home Assistant, device sync, Windows installer, ADDONS.md.
- 2026-11-24 — Installed on the G14; fixed the PyQt6 crash by pinning to 6.9.
- 2026-11-24 — Installer no longer stops when Git, Python or Tailscale is already
  installed (winget's "already installed" codes count as success).
