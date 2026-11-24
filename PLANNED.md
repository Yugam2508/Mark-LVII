# Planned additions and open items

A running list of what we want to add or still need to do. Newest ideas go at the
bottom of their section; finished items move to **Done** with the date.

## To build

- [ ] **Spotify: choose the device.** "Play this on my phone" / "move it to the
      laptop" — pick a Spotify Connect device by name instead of only the active one
      or this PC. (`plugins/spotify_control.py`)
- [ ] **Notion.** Read, search and add to Notion pages and databases by voice.
- [ ] **Note-taking.** Quick voice notes ("note that…", "take notes on this meeting")
      saved somewhere you can find on every device (Notion, Google Docs or the
      knowledge folder), plus reading them back.
- [ ] **Google Drive and Docs.** Find, read and create Drive files and Google Docs.
      The APIs are already enabled in the JARVIS Google Cloud project; the sign-in
      needs the Drive/Docs scopes added (`plugins/_google_auth.py`), which means
      reconnecting Google once.
- [ ] **A proper writing voice.** Emails, documents and notes written well and in
      your style. Route writing to a stronger model than the voice model (e.g. Claude
      through `core.gemini`'s provider setting), with a short style guide.
- [ ] **Proactive assistant.** Jarvis speaks up without being asked:
      - **New email:** checks Gmail every few minutes, tells you about mail that
        matters (skips newsletters/promotions; learns who is important) and offers a
        suggested reply you can send, edit or ignore. Sending still needs CONFIRM.
      - **Calendar from email:** spots dates in emails (meetings, deadlines,
        bookings) and offers to add them to the calendar.
      - **Reminders:** a heads-up before calendar events (with travel time when
        there's a location) and before to-do due dates.
      - Respects quiet hours, doesn't repeat itself, and shows a notice on screen
        when you're away from the PC.
      Builds on the existing routine engine / proactive check-ins
      (`core/routines`, `actions/proactive.py`) and `player.request_say`.
- [ ] **Modes.** Switch by voice ("work mode", "gaming mode") or automatically, with
      a different default mode per device. Each mode decides what Jarvis does and how
      much it interrupts. First ideas:
      - **Work:** proactive email/calendar on, concise replies, focus on to-dos.
      - **Study:** notifications held back, knowledge folder and study coach ready,
        optional pomodoro timer.
      - **Music:** Spotify first, short replies, no chatter.
      - **Watching something:** silent unless spoken to; notices only for urgent things.
      - **Gaming:** quiet, no screen pop-ups over the game, hardware alerts only for
        real problems; could switch on by itself when a game is running.
      Per-device defaults, e.g. G14 → work/study, desktop → gaming/music. Ties in with
      quiet hours and the proactive assistant above.

## To set up / test

- [ ] **Voice test on the G14** — wake word, "what time is it", "open Notepad",
      microphone choice in ⚙ → audio. (Typed commands are being tested first.)
- [ ] **Connect the add-ons on the G14** — Spotify connected (not yet tested);
      device sync, knowledge folder next; Claude and Home Assistant optional.
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

- 2026-11-24 — Google connected on the G14 (published consent screen, PRIVACY.md);
  calendar and email listing work against the real account.

- 2026-11-24 — Gmail, Calendar, to-do (Google Tasks), Spotify, Claude provider,
  agents (daily digest, study coach, deal hunter), knowledge folder, voice
  interrupt, Home Assistant, device sync, Windows installer, ADDONS.md.
- 2026-11-24 — Installed on the G14; fixed the PyQt6 crash by pinning to 6.9.
- 2026-11-24 — Installer no longer stops when Git, Python or Tailscale is already
  installed (winget's "already installed" codes count as success).
