# What to try after installing

Work down the list on the G14 first, then the desktop. Each line is **what to do** →
**what should happen**. Tick it off, or note what went wrong in PLANNED.md under
*Known issues* (or tell Claude Code — paste the log lines from the COMMUNICATIONS panel).

Update first: say **"update yourself"**, or run the installer once more. After the
restart the header should read **v1.5** and the What's new panel should open.

---

## 1. Basics (5 minutes)

- [ ] "What time is it?" → answers out loud; a satellite appears around the core.
- [ ] Talk over it mid-answer → it stops and listens (voice interrupt).
- [ ] Press the **HUD** button three times → holographic → face → reactor core → holographic.
- [ ] Watch the holo HUD while it thinks (gold sweep), listens (green) and speaks (bars move).

## 2. Talking to someone else

- [ ] Turn to someone in the room and talk normally for a minute without saying "Jarvis"
      → it should stay silent. If it answers, note what you said.
- [ ] "I'm talking to someone" → a three-word acknowledgement, then quiet.
- [ ] While paused, send yourself an email marked important → a card appears top right
      and stays; nothing is spoken.
- [ ] "I'm back" → it sums up what came in and asks what's first.
- [ ] Join a Discord/Teams call → anything new should come as a card, not speech.
- [ ] Leave the laptop for 10+ minutes with something running (e.g. a Claude Code job)
      → a card **and** a phone notification when it finishes.

## 3. Confirm by voice

- [ ] "Email <a friend> saying I'll be late" → confirmation appears → say **"confirm"**
      → sent. Repeat and say **"cancel"** → not sent.
- [ ] Press EDIT, change a word, then say "confirm" → nothing happens while editing
      (by design); press CONFIRM.

## 4. Claude Code

Set up once: ⚙ → PLUGIN SETTINGS → CLAUDE CODE CONTROL → add a project
(e.g. `jarvis=C:\Users\<you>\Mark-LVII`) and the commands it may run (`git status, git diff`).

- [ ] "Ask Claude Code to explain how the wake word works in my jarvis project"
      → "on it", a CLAUDE CODE satellite, progress in the log, then a spoken summary.
- [ ] "Ask Claude Code to add a comment at the top of README in jarvis" → it plans →
      "go ahead" → confirm → done, with the file named in the card.
- [ ] "What's Claude Code doing?" during a job; "stop Claude Code".
- [ ] "Open Claude Code in jarvis" → a terminal window opens there.

## 5. Voices

- [ ] "Switch to the Irish persona" → it says it's switching, then speaks with an accent.
- [ ] Try classic, tactical, coach, mentor, desi. Pick a favourite.
- [ ] Custom: VOICE PERSONA settings → custom, voice Gacrux, "Scottish accent, dry
      humour" → APPLY NOW.
- [ ] Customize → pick a plain voice → persona turns off.

## 6. Audio devices

- [ ] Start Jarvis on laptop speakers, then turn on Bluetooth headphones → within a few
      seconds the log says "Audio connected: … — switching devices" and it speaks in
      the headphones.
- [ ] Turn the headphones off mid-conversation → back to the speakers, still remembers
      what you were talking about.
- [ ] Plug/unplug a USB headset the same way.

## 7. Phone over Tailscale

- [ ] Tailscale **on** on the phone and the PC → Remote Control → the QR code shows the
      `100.x` address → scan → the dashboard opens, on Wi-Fi and on mobile data.
- [ ] Optional secure link (ADDONS.md §9): enable HTTPS in the Tailscale admin, switch on
      "Secure phone link through Tailscale" → QR shows `https://….ts.net` → the phone
      mic button works.

## 8. Things from earlier versions still worth a run

- [ ] Morning briefing (tomorrow morning), proactive email alerts with suggested replies.
- [ ] Spotify on a chosen device; "play my liked songs on the desktop".
- [ ] "Launch Valorant" (switches to gaming mode → Jarvis goes quiet → cards instead).
- [ ] Study timer: "start a 25 minute study session on chemistry".
- [ ] Life profile: "remember I swam 2 km today for IRONMAN training" → "how's my
      IRONMAN training going?"
- [ ] Phone → "turn on my home PC and open Spotify" (desktop at home, Wake-on-LAN).

---

# What to add next (suggestions)

Roughly in order of how much difference they'd make day to day. Say which ones you want
and they go into PLANNED.md.

1. **Only answer your voice.** A voice fingerprint, so Jarvis ignores other people in the
   room and the TV — the strongest fix for "talking to someone else".
2. **Training coach for the 70.3.** Pull workouts from Strava/Garmin, weekly volume per
   sport, taper countdown, weather-aware "swim or run today?" in the morning briefing.
3. **Practice partner for guitar and singing.** Practice log and streaks, a metronome and
   tuner on screen, "quiz me on the chords for…", reminders before lessons.
4. **Comedy notebook.** Capture a bit by voice anywhere (phone too), tag and rate jokes,
   build a set list, track open-mic dates.
5. **Travel goals.** Flight price watches for trips on your list, passport/visa
   reminders, a countdown and packing list per trip.
6. **Messages.** Read and reply to WhatsApp/Discord by voice with the same
   confirm-and-edit flow as email.
7. **Focus guard.** In study/work mode, warn or block distracting sites and apps, and
   log what pulled you away.
8. **Night review.** A two-minute evening check-in: what got done, what's tomorrow,
   anything to remember — saved to the life profile.
9. **Find my files.** "Find the PDF my history teacher sent last week" across Downloads,
   OneDrive and Gmail attachments.
10. **Offline brain on the desktop.** A local model on the RTX 5070 as fallback when the
    internet or Gemini is down.
11. **Leaving-work routine.** One phrase on the phone: wake the desktop, start Spotify,
    warm up a game, set "home" mode.
12. **Backups.** Nightly copy of settings and memory to OneDrive, so a reinstall restores
    everything.
