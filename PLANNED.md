# Planned additions and open items

A running list of what we want to add or still need to do. Newest ideas go at the
bottom of their section; finished items move to **Done** with the date.

## To build

- [ ] **Edit before confirming.** The on-screen confirmation only offers CONFIRM or
      CANCEL. Add an **EDIT** button that opens the text in an editable box — email
      drafts and replies (To / Subject / body), suggested replies from proactive alerts,
      notes, calendar events (title / time / place), Notion and Docs content — so you
      can fix a word and then confirm, without asking Jarvis to redo it. Also make the
      draft panels (DRAFT, NOTE SAVED, NEW EMAIL) clickable to edit, with SAVE / SEND.
      Needs a small change to the HUD (`gui/`, `core/confirm.py` passing editable
      fields through to the action).

## To set up / test

- [ ] **Voice test on the G14** — wake word, "what time is it", "open Notepad",
      microphone choice in ⚙ → audio. (Typed commands are being tested first.)
- [ ] **Try the new add-ons on the G14** — Claude Code is installed and logged in; pick
      it in ⚙ → ENGINE & PROVIDERS (ADDONS.md §11), set the writing voice (§12), check proactive alerts (§13) and modes (§14),
      reconnect Google for Drive (§16), Notion (§17), notes (§18). Spotify connected but
      not yet tested (device choice §15). Home Assistant only if there are smart devices.
- [ ] **Tailscale for the OnePlus 13** — Tailscale on phone + PCs, then the phone
      dashboard over the Tailscale address (ADDONS.md §9).
- [ ] **Install on the desktop** (Aftershock, 9800X3D + RTX 5070) — the PyQt6 pin is
      on `main` now; set Whisper to GPU if using the pipeline engine.
- [ ] **Interrupt by voice** — try with headphones and with speakers; pick normal or
      careful.

## Known issues

- PyQt6 6.12 would not load on the G14 ("DLL load failed while importing QtWidgets:
  The specified procedure could not be found"), even with the latest Visual C++
  runtime and MiKTeX's Qt removed from PATH. 6.9 works; requirements are pinned
  below 6.10. Worth retrying newer versions later.

## Done

- 2026-11-24 — Claude through your subscription (Claude Code, no API key), writing
  voice, proactive alerts (email + suggested replies, calendar from email, reminders,
  due to-dos), modes (work/study/music/watching/gaming, per-device default, automatic
  gaming mode), Spotify device choice, Google Drive & Docs, Notion, notes.
- 2026-11-24 — Device sync and knowledge folder set up on the G14.

- 2026-11-24 — Google connected on the G14 (published consent screen, PRIVACY.md);
  calendar and email listing work against the real account.

- 2026-11-24 — Gmail, Calendar, to-do (Google Tasks), Spotify, Claude provider,
  agents (daily digest, study coach, deal hunter), knowledge folder, voice
  interrupt, Home Assistant, device sync, Windows installer, ADDONS.md.
- 2026-11-24 — Installed on the G14; fixed the PyQt6 crash by pinning to 6.9.
- 2026-11-24 — Installer no longer stops when Git, Python or Tailscale is already
  installed (winget's "already installed" codes count as success).
