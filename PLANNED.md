# Planned additions and open items

A running list of what we want to add or still need to do. Newest ideas go at the
bottom of their section; finished items move to **Done** with the date.

## To build

- [ ] *(nothing queued — add ideas here)*

## To set up / test

- [ ] **Go through TESTING.md for v1.5** — holo HUD, talking to someone else, voice
      confirm, Claude Code control, personas, audio device switching, phone over Tailscale.
- [ ] **Phone over Tailscale** — QR code now uses the 100.x address; for the phone mic,
      enable HTTPS in the Tailscale admin and switch on the secure link (ADDONS.md §9).

- [ ] **Voice test on the G14** — wake word, "what time is it", "open Notepad",
      microphone choice in ⚙ → audio. (Typed commands are being tested first.)
- [ ] **Try the new add-ons on the G14** — Claude Code is installed and logged in; pick
      it in ⚙ → ENGINE & PROVIDERS (ADDONS.md §11), set the writing voice (§12), check proactive alerts (§13) and modes (§14),
      reconnect Google for Drive (§16), Notion (§17), notes (§18). Spotify connected but
      not yet tested (device choice §15). Home Assistant only if there are smart devices.
- [ ] **Phone link** — ntfy app on the OnePlus, subscribe to both topics (ADDONS.md §21);
      Wake-on-LAN on the desktop and "sleep instead of shut down" (§22). Tailscale is now
      only needed for the full phone dashboard (§9).
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

- 2026-11-27 — v1.5: holographic HUD with satellites; presence (free / busy / away),
  cards that stay, welcome-back summary, silence when you talk to someone else; confirm
  by voice; Claude Code control (plan / go ahead / follow up / stop / open); voice
  personas; audio follows headphones and Bluetooth; phone QR over Tailscale with an
  optional HTTPS link. Suggestions for what's next are at the end of TESTING.md.

- 2026-11-26 — v1.4: life profile (areas with about/goals/log in OneDrive, summaries in
  Jarvis's memory, interview set-up, goal countdowns in the briefing); version label,
  What's new panel and "what's new?" answered from the changelog.

- 2026-11-25 — Voice interrupt fixed: the echo detector failed on the microphone's
  2-D audio block (frames × channels) and silently answered "not the user", so talking
  over Jarvis never worked. Now flattened first; interrupt is on by default.

- 2026-11-25 — Update yourself; phone link via ntfy (phone alerts when away, commands
  from the phone, PC-to-PC control, Wake-on-LAN or smart-plug wake, queued commands for
  a PC that is off, per-PC permissions); proactive agents (price watches, exam/interview
  prep, daily digest); games launcher; the day in the morning briefing; study timer;
  screen helper; money tracker; reading & watch list.

- 2026-11-24 — Edit before it happens: EDIT on the confirmation banner (email To /
  Subject / message, timeout paused while editing), and an editable panel for writer
  drafts (SAVE/UPDATE DRAFT, SEND, COPY, SAVE AS NOTE, MAKE GOOGLE DOC), suggested replies
  (SEND REPLY, SAVE AS DRAFT), notes (SAVE CHANGES) and new calendar events (SAVE CHANGES).

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
