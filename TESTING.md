# What to try after installing

Work down the list on the G14 first, then the desktop. Each line is **what to do** →
**what should happen**. Tick it off, or note what went wrong in PLANNED.md under
*Known issues* (or tell Claude Code — paste the log lines from the COMMUNICATIONS panel).

Update first: say **"update yourself"**, or run the installer once more. After the
restart the header should read **MARK LXI** and the What's new panel should open.

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

## 5. Personality

- [ ] "Be more sarcastic" → it answers in a few words, already sarcastic, **without
      disconnecting**. Keep talking: it should remember what you were just discussing.
- [ ] "Stop calling me sir, call me Yugam" → it does, from then on.
- [ ] "What have I asked you to change?" → it lists them. "Forget the first one" → gone.
- [ ] Restart Jarvis → the tweaks are still there.
- [ ] Customize → pick another voice → it finishes its sentence, reconnects, and carries
      on the conversation without greeting you again.
- [ ] Over a few days: does it feel like someone who knows you? Tell it what's off
      ("too much advice", "ask me how training went") and it adjusts.

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

## 7b. The Android app (`android/`)

Build and install it first: `android/README.md` has the steps (about 10 minutes in Android Studio).

- [ ] Tailscale on → in the app type the PC's `100.x.x.x:8000` address, **no key** → **CONNECT** →
      the PC log says "Paired: <phone name>".
- [ ] Restart Jarvis on the PC → the app reconnects by itself, no new pairing.
- [ ] With "My own Tailscale devices can connect without a key" switched off → CONNECT asks for a key
      from Remote Control; a key can be used only once.
- [ ] Close and reopen the app → it logs straight back in without a key.
- [ ] Open the app → it starts listening by itself (a "Jarvis is listening" notification). Just talk: the
      answer plays on the PHONE in the same voice as the PC, and the PC stays silent.
- [ ] Talk over Jarvis while it's speaking → it stops and listens (if it hears itself, tap ⋮ → Permissions &
      setup → turn "Talk over Jarvis" off).
- [ ] Put on Bluetooth headphones → Jarvis's voice moves to them; take them off → back to the loudspeaker.
- [ ] Open the app → under the orb it says "Say “Hey Jarvis” — or tap the orb". Say "Hey Jarvis, what time is it?"
      → a chime and a buzz, and it answers the whole question. Keep talking → it keeps answering. Stay quiet ~45 s →
      back to "Say “Hey Jarvis”". Talk without the phrase → nothing happens (it's for you only after the phrase).
- [ ] Tap the orb → it listens without the phrase. Long-press it → back to waiting.
- [ ] ⋮ → Permissions & setup → turn the wake word off → everything you say goes to Jarvis again.
- [ ] Leave the phone listening in a quiet room for 10 minutes → Settings → Network → Data usage for Jarvis barely
      moves. Then talk → it answers as before. If it misses quiet words, turn "Save mobile data" off in ⋮.
- [ ] Close the app, lock the screen, talk → it still answers (the notification stays).
- [ ] Ask for something that shows a card on the PC (the weather, your calendar) → it also appears in the phone log.
- [ ] Press **Stop listening** in the notification → the PC speaks again.
- [ ] Settings → Apps → Default apps → Digital assistant app → **Jarvis** → long-press power
      from another app → the panel opens over it and starts listening.
- [ ] Allow the permission prompts (Microphone, Contacts, Phone, SMS, Call log, Location, Notifications). A quiet
      "Jarvis is linked to your PC" notification appears, and the PC log says "Phone linked".
- [ ] Tap ⋮ → Permissions & setup → every line you care about shows ✓ (tap a ✗ to fix it). Allow "Battery: not
      restricted", or OnePlus may close the link in the background.
- [ ] Say to Jarvis on the PC: "what's my phone's battery?" → it answers from the phone.
- [ ] "Find my phone" (with the app closed) → rings loudly for 30 s; opening the app stops it.
- [ ] "Call <a contact>" → a confirmation on the PC → say "confirm" → the phone dials. Say
      "cancel" the next time → nothing happens. Try a name that matches two contacts → it asks which.
- [ ] "Text <yourself or a friend> hello from Jarvis" → shown for edit/confirm → the text arrives.
- [ ] Restart the phone → the link notification comes back by itself (open the app once to start listening again:
      Android doesn't let an app open the microphone by itself after a restart).
- [ ] Not built yet, so don't expect them: a wake word on the phone, the AC through the IR blaster, and controlling
      other apps beyond WhatsApp's Send button.

## 7c. Deeper thinking

- [ ] Copy an OpenAI key, say "add this OpenAI key" → it confirms how many keys and which model.
- [ ] Ordinary questions, commands and chat → answered by Jarvis itself; it should NOT go to the stronger model.
- [ ] Ask something and then say "think harder about that" (or "are you sure?" / "second opinion") → it says
      it's getting the stronger model, then a card appears and it summarises the answer, naming the model.
- [ ] Optional: PLUGIN SETTINGS → DEEP THINKING → switch on "Let Jarvis go to the stronger model on its own" →
      only genuinely hard, high-stakes questions trigger it.
- [ ] If it fails, the card names the real reason (out of credit, rate limit, model not available, Claude not
      signed in) and it waits five minutes before trying again.
- [ ] "Use Claude for deep thinking", ask again → the card says Claude. "Use OpenAI" → back.
- [ ] "How much deep thinking have I used today?" → calls and tokens per model.

## 7d. Seeing inside the computer

- [ ] Start a game or video, then "what's using my GPU?" → a list with GPU % and video memory per program.
- [ ] "What's eating my memory?" / "is Chrome running?" / "what's using port 8000?".
- [ ] "Where is <a file you know>?" (wait a couple of minutes after the update for the first index) →
      a numbered list; "show me the first one in Explorer" → Explorer opens on it.
- [ ] "What's taking up space on C:?" → biggest folders with sizes.
- [ ] Make a junk file; "delete it" → asks to confirm → Recycle Bin; "undo" → back. Say "cancel" once to check.
- [ ] "Delete C:\Windows" or your user folder → refused.
- [ ] "Close Notepad" (open one) → confirm → closed.
- [ ] "Allow Claude Code to run commands" → confirm. Then "ask Claude Code to find what's using space on D:
      and propose what's safe to clean" → a plan → read it → "go ahead" → confirm → it runs.

## 7e. Doing things on the PC and phone

- [ ] "Turn Bluetooth off", then "on" (Windows). "What Bluetooth devices do I have?" lists paired ones.
- [ ] "Install VLC" → confirmation naming the winget package → "confirm" → installed. "Uninstall it" likewise.
- [ ] "Run ipconfig" → shows the command → confirm → output summarised. "Format my D drive" → refused.
- [ ] "Organise my Downloads" → says how many files go where → confirm → sorted into Images, Documents…
      "Undo the tidy-up" → back where they were.
- [ ] "Open youtube.com", "search for best pizza near me" → opens in the PC browser.
- [ ] "Play my liked songs" (optionally "on my phone") → plays shuffled. Spotify's Jam can't be started by
      apps, so Jarvis should say that rather than pretend.
- [ ] Phone, menu → "Let Jarvis open apps and sites" → switch it on. Then "open Spotify on my phone",
      "open example.com on my phone", "turn the phone's volume to 40", "flashlight on", "set a 5 minute timer
      on my phone", "pause the music on my phone", "navigate to <place>".
- [ ] "WhatsApp <a friend> hi from Jarvis" → shows the message → "confirm" → WhatsApp opens the right chat and
      sends (it says it can't verify delivery; check the chat). An unknown name → it asks for the number
      once and remembers it. WhatsApp Desktop must be installed and signed in.
- [ ] "WhatsApp <a friend> hi, from my phone" → the chat opens on the phone with the text typed. Phone menu →
      "Let Jarvis tap Send in WhatsApp" → switch Jarvis on in Accessibility → repeat: Send is pressed for you.
- [ ] Phone menu → "Let Jarvis read notifications" → switch Jarvis on (Android may warn; that is normal) and
      allow Call log when asked. Have a friend WhatsApp you: Jarvis announces it (a card if you're busy).
- [ ] "Any WhatsApp messages?" → lists them. "Reply to <them>: on my way" → shown to edit/confirm → "confirm" →
      it arrives in the chat. "Clear that notification" → gone from the phone. "Did anyone call?" → the call log.
- [ ] ⚙ → PLUGIN SETTINGS → PHONE MESSAGES → switch announcements off → new messages are no longer announced,
      but "any messages?" still works.
- [ ] "Shut down the PC in 10 minutes" → confirm → scheduled; "cancel the shutdown" → cancelled. "Clean my temp files".
- [ ] Copy a link on the PC, "send that to my phone" → a notification on the phone; tap it → the link opens.
- [ ] "Where's my phone?" → a map link (allow Location when the app asks). "Turn on Do Not Disturb on my phone".
- [ ] "Open Bluetooth settings on my phone" → the page opens (Android won't let any app flip it silently).

## 7f. Notes, dictation and self-check

- [ ] Say "run a self-check" → a card lists Screenshot / Notes folder / Dictation / Notion / Phone link / API keys
      with OK or FAIL and the reason. Send me any FAIL lines.
- [ ] "Take dictation, it's my feature list" → Jarvis says nothing more. Talk for a minute or two. A new file
      appears in the knowledge folder under Dictations, growing as you speak.
- [ ] "End dictation" → Jarvis says how many words were kept and whether they reached your notes. The notes
      entry holds all of it, not a summary.
- [ ] "Tidy up that dictation and save it" → clean bullet points in the notes.
- [ ] With Notion as the notes backend and a long dictation (100+ lines) → all of it is on the Notion page.
- [ ] Restart Jarvis, then ask "what did I tell you earlier about <something from before>?" → it searches the
      conversation log and answers from it (the log is in the Jarvis folder under memory\conversations).
- [ ] "Take a screenshot" → a PNG appears in Pictures\Screenshots and Jarvis says where.
- [ ] "Add 'test from Jarvis' to my <page name> page in Notion" → it lands on that page without asking for a number.
- [ ] Ask Jarvis to "note that the sky is blue" → it says it saved only after the tool reports it; check the note exists.

## 7g. PC care, backups, and the phone's new bits

- [ ] "What Wi-Fi am I on?", "what networks are around?", "what's the Wi-Fi password?" (shown on screen).
- [ ] "Are there app updates?" → a list. "Update all my apps" → confirm → when it finishes Jarvis says how it went.
- [ ] "How full is the Recycle Bin?" → "empty it" → confirm. "Run a speed test" → it answers ~15 s later.
- [ ] "How's my battery health?" (laptop) → percent, health and cycles. "What's my IP?" → local, Tailscale, public.
- [ ] "Back up Jarvis" → a zip in OneDrive\JARVIS Backups. Open it: memory and conversations inside, keys blanked.
- [ ] Phone: tap ⋮ (top right) → Permissions & setup. Fix every ✗ you want; the battery line matters on OnePlus.
- [ ] Phone: in Chrome, Share → "Jarvis (to my PC)" → the page opens on the PC and the link is on the clipboard.
- [ ] "What did <someone> text me?" → reads the texts from them.
- [ ] Confirm any action (a WhatsApp, an install) → Jarvis says afterwards whether it worked.
- [ ] "Take a screenshot" → a PNG in Pictures\Screenshots (no snipping overlay). "Snip a region" → the overlay.
- [ ] Start a study session, open YouTube for a minute → Jarvis nudges you once. Close it → quiet again.
- [ ] "Set an alarm for 7:15 on my phone" → it's in the Clock app. With Accessibility on: "take a screenshot on my
      phone" (in the gallery), "lock my phone".

## 7i. Iron Man bits

- [ ] "Create a night protocol: lock the PC, phone on Do Not Disturb, set an alarm for 7" → saved, shown on screen.
      "Initiate night protocol" → the panel says INITIATED and the steps happen one after another.
- [ ] "Run diagnostics" → a DIAGNOSTICS panel with ●/▲/■ per line; Jarvis mentions only what needs attention.
- [ ] Start "update all my apps" (confirm), then "what are you working on?" → it's listed. "Run a speed test", then
      "stop that" → stopped. "Cancel the install" → it says it can't be stopped half-way.
- [ ] While Jarvis talks, say "wait" → it stops and says nothing. "Go on" → it carries on where it stopped.
- [ ] Phone: tap the orb while Jarvis is talking → silence at once, and it listens.
- [ ] Away from the PC, ask through the phone: "text Aarav I'm on my way" → the phone shows "Jarvis needs your OK"
      with CONFIRM / CANCEL (in the app, and as a notification) → CONFIRM → the text goes; the PC banner closes.
- [ ] Have someone call your phone while you're at the PC → Jarvis says who's calling. "Decline it" → it stops
      ringing. Next time "answer it" → the call connects on the phone.
- [ ] With a few panels up: "close that", "close the weather", "pin the calendar", "expand the email",
      "clear the screen", "full screen", "switch to panels" — each happens.

## 7j. Driving it

- [ ] Right-click the tray icon → Quick → Run diagnostics / What are you working on? → Jarvis answers.
- [ ] Hide Jarvis in the tray, ask for something that needs confirming (from the phone) → a Windows notification says
      "Jarvis needs your OK"; click it → the window opens on the banner.
- [ ] Phone: pull down Quick Settings → edit → add the Jarvis tile. Tap it → listening off; tap again → the app opens
      listening. The listening notification has Mute and Stop; tapping it opens the app.
- [ ] Turn Tailscale off on the phone → the app says "Tailscale looks off — tap here"; tap → Tailscale opens.

## 7k. Mark LXI

- [ ] Phone, Accessibility on (⋮ → Permissions & setup): open Settings on the phone, then "what's on my phone
      screen?" → Jarvis reads it. "Tap Wi-Fi" → it opens. "Scroll down", "go back", "go home".
- [ ] Open a chat, "type hello there" → typed in the box. "Tap send" → it asks you to confirm first.
- [ ] "Switch to Chrome", "snap this to the left", "move Spotify to my other screen", "minimise everything",
      "close Notepad" (with unsaved text it asks you to save, as usual).
- [ ] "What's the weather?" → an answer, not a browser tab; "will it rain this afternoon?"; "weather in Paris tomorrow".
- [ ] "Show me my day" → a TODAY panel with calendar, to-dos, weather, study, jobs and phone battery.
- [ ] Copy three things, then "what did I copy?" → a numbered list. "Copy the link again" → it's back on the clipboard.

## 7h. The PC as the hub

- [ ] Say "this PC is my hub" → it says what's still needed (plug in, AUTO-START). Press AUTO-START.
- [ ] "Hub status" → hub mode on, phones linked, the Tailscale address, holding awake, starts at login.
- [ ] Leave the PC plugged in and idle for an hour (screen off is fine) → the phone still connects and answers.
- [ ] Reboot the PC → Jarvis comes back in the tray by itself and the phone relinks without touching anything.
- [ ] Unplug it → the log/status says it can sleep again (it only stays awake on mains power).

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
