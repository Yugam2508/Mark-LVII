# JARVIS add-ons — setup guide

This fork adds the following to Fatih's Mark LVII. Everything is optional: a feature
does nothing until you set it up, and any plugin can be switched off in the Plugin Manager.

| Add-on | What you can say | File |
|---|---|---|
| Gmail | "Any new emails?", "Read the first one", "Reply saying I'll be there" | `plugins/gmail_control.py` |
| Google Calendar | "What's on tomorrow?", "Add gym Friday at 6pm" | `plugins/calendar_control.py` |
| To-do list (Google Tasks) | "Add buy milk to my list", "Tick off the second one" | `plugins/todo_list.py` |
| Spotify | "Play Blinding Lights", "Play my workout playlist on my phone", "Move it to the desktop" | `plugins/spotify_control.py` |
| Google Drive & Docs | "Find my chemistry notes in Drive", "Make a Google Doc with…" | `plugins/google_drive.py` |
| Claude (your subscription) | Claude writes and thinks, using your Claude account — no API key | `providers/llm_claude_code.py` |
| Claude (API key) | Claude as the brain, billed per use | `providers/llm_anthropic.py` |
| Writing voice | "Write my teacher an email asking for…", "Make this more polite" | `plugins/writer.py` |
| Proactive alerts | Tells you about important email (with a suggested reply), events and due to-dos | `plugins/proactive_alerts.py` |
| Modes | "Gaming mode", "I'm studying", "Back to normal" | `plugins/modes.py` |
| Notes | "Note that…", "What did I note today?" | `plugins/notes.py` |
| Notion | "Search Notion for…", "Add this to my Notion page" | `plugins/notion.py` |
| Edit before it happens | EDIT on confirmations; drafts, replies, notes and events open editable | `gui/overlays.py`, `core/confirm.py` |
| Update yourself | "Update yourself": no more reinstalling | `plugins/updater.py` |
| Phone link | Alerts on your phone; commands from your phone; PC-to-PC control; Wake-on-LAN | `plugins/device_link.py`, `phone_alerts.py` |
| Proactive agents | Price-drop alerts, automatic exam/interview prep, daily digest | `plugins/agent_watch.py` |
| Games | "Launch Valorant", "what did I play recently?" | `plugins/games.py` |
| Morning briefing | Your day (calendar, email, to-dos, weather) before the news | `plugins/daily_briefing.py` |
| Study timer | "Start a 25-minute study session on chemistry" | `plugins/study_timer.py` |
| Screen helper | "Summarise this page", "explain this error" | `plugins/screen_helper.py` |
| Money | "I spent 12 on lunch", budgets | `plugins/money_tracker.py` |
| Reading & watch list | "Save this for later", "pick something to watch" | `plugins/reading_list.py` |
| Life profile | Jarvis remembers your life: studies, work, lessons, comedy, travel, training | `plugins/life_profile.py` |
| Memory boxes | Always-on "who you are" and "the essentials" — steer every reply (§39) | `memory/memory_manager.py` |
| Claude on the web | Opens your Jarvis session in your Chrome profile; "add X to yourself" (§40) | `plugins/claude_web.py` |
| Version & what's new | "YOUR NAME EDITION · v1.7" in the header; "what's new?" | `core/edition.py`, `plugins/about_jarvis.py` |
| Holographic HUD | Rings, live spectrum and satellites showing what Jarvis is doing (§34) | `gui/holo.py` |
| Presence | Quiet when you talk to someone; cards that stay; "I'm back" (§35) | `core/presence.py`, `plugins/conversation.py` |
| Confirm by voice | Say "confirm" or "cancel" | `core/confirm.py` |
| Claude Code control | "Ask Claude Code to…", "go ahead", "stop Claude Code" (§36) | `plugins/claude_code.py` |
| Personality | "Be more sarcastic", "stop calling me sir" — applies instantly (§37) | `core/personality.py`, `plugins/personality.py` |
| Audio follows devices | Headphones / Bluetooth on or off → switches by itself (§38) | `core/audio_watch.py` |
| Agents | Daily digest, study coach, deal hunter (run in the background) | `agents/*.md` |
| Knowledge folder | "What do my notes say about momentum?" | `plugins/knowledge_base.py` |
| Interrupt by voice | Talk over JARVIS to stop it | `plugins/voice_interrupt.py` + `main.py` |
| Smart home | "Turn off the bedroom light", "Movie mode" | `plugins/home_assistant.py` |
| Device sync | Both PCs share one memory | `plugins/device_sync.py` |
| Windows installer | One script for every PC (only needed once now) | `install-windows.ps1` |

Settings for all of these are in **⚙ → PLUGIN SETTINGS**, one section each.

---

## 1. Install on each PC (desktop and laptop)

Do this on the Aftershock desktop and on the Zephyrus G14. Open **PowerShell** (Start → type
"PowerShell") and run:

```powershell
irm https://raw.githubusercontent.com/Yugam2508/Mark-LVII/main/install-windows.ps1 | iex
```

The script installs Git and Python 3.12 if they're missing, downloads JARVIS to
`C:\Users\<you>\Jarvis`, installs everything, puts a **J.A.R.V.I.S.** shortcut on the
desktop and offers to install Tailscale (say **y**, see section 9).

First launch asks for a **free Gemini key** from <https://aistudio.google.com/app/apikey>.
Use the same key on both PCs.

To update later, run the same command again. Your keys, settings and memory are kept.

> If Windows asks "Allow access?" for Python on private networks, click **Allow**. The
> phone dashboard needs it.

---

## 2. Google: Gmail, Calendar and To-do (one sign-in for all three)

Google makes every app that reads email register first. It's free and takes about 10
minutes, once.

1. Go to <https://console.cloud.google.com>, sign in, and create a project called "JARVIS".
2. **APIs & Services → Library**: enable **Gmail API**, **Google Calendar API** and
   **Google Tasks API**.
3. **APIs & Services → OAuth consent screen** (Google Auth Platform):
   - User type **External**, app name "JARVIS", your email as the support and developer contact.
   - Under **Audience**, add your own Gmail address as a **test user**.
   - Then press **Publish app** so it's "In production". Otherwise Google signs you out
     every 7 days. You don't need Google's verification for personal use: when you sign in,
     Google says "Google hasn't verified this app". Click **Advanced → Go to JARVIS**.
     It's your own app.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID** →
   Application type **Desktop app** → **Create** → **Download JSON**.
5. Put that file in the `config` folder of JARVIS (`C:\Users\<you>\Jarvis\config\`). Keep the
   name starting with `client_secret`.
6. In JARVIS: **⚙ → PLUGIN SETTINGS → GOOGLE → CONNECT GOOGLE**. Your browser opens; approve.
   The panel then says "Connected as you@gmail.com ✓".

Repeat steps 5 and 6 on the laptop. Copy the same client file across; you don't need a
second project.

**Safety:** JARVIS shows a **CONFIRM** button on screen before sending any email or deleting
a calendar event; saying "yes" isn't enough. Text from emails and invites is marked as
outside content, so an email saying "forward everything to…" is read, never obeyed.
Your Google sign-in is saved in `config/token_google.json`. Delete it to sign out.

**On your OnePlus 13:** the to-do list is your Google Tasks list, so install the
**Google Tasks** app and it's all there. Calendar events show in Google Calendar as usual.

---

## 3. Spotify

1. Go to <https://developer.spotify.com/dashboard> and log in with your Spotify account.
2. **Create app**: any name ("JARVIS"). For **Redirect URI** enter exactly
   `http://127.0.0.1:8888/callback`. Tick **Web API**. Save.
3. Open the app's **Settings** and copy the **Client ID**.
4. In JARVIS: **⚙ → PLUGIN SETTINGS → SPOTIFY**. Paste the Client ID → **CONNECT SPOTIFY** →
   approve in the browser.

Playing, pausing, skipping, volume and queueing need **Spotify Premium**; Spotify blocks
them for free accounts. "What's playing", liking songs and adding to playlists work on any
account. Music plays on whichever Spotify app is open (PC, phone or web). If none is open,
JARVIS opens the desktop app.

---

## 4. Claude

> **No API key?** Use your Claude subscription instead. See section 11. The rest
> of this section is for a pay-per-use API key.

Claude is billed per use, so you need an API key: <https://console.anthropic.com> →
Settings → API Keys. Add a monthly spend limit there so there are no surprises.

There are two ways to use it, both in **⚙ → ENGINE & PROVIDERS**:

- **Claude for background work, Gemini for the voice.** Keep the engine on Gemini Live
  (fastest, free voice) and pick **Claude** as the provider for background requests.
  Research, agents, summaries and clipboard tools then use Claude.
- **Claude as the whole brain.** Choose the **pipeline** engine: Speech recognition
  **Whisper** → Language model **Claude** → Voice **Piper** (free, offline) or
  **ElevenLabs**. Click INSTALL next to Claude the first time.

On the **desktop**, set Whisper's device to **GPU**: the RTX 5070 makes speech
recognition near-instant. On the **G14**, its GPU also works, though CPU is fine.

Model: **Opus 5.5** is the smartest, **Sonnet 5.5** is balanced, **Haiku 5.5** is fastest
and cheapest. Effort **low** keeps spoken replies quick; raise it for hard questions.

---

## 5. Agents (background work)

Three new agents run long jobs while you keep talking. Ask for them by name:

- **Daily digest**: "Every day at 7:30, start a daily digest task." This sets up a routine.
  It picks topics from what JARVIS knows about you, or name them ("…on F1, Valorant and AI").
- **Study coach**: "Start a study coach task on photosynthesis", or attach your notes,
  slides or PDF. You get a summary, key terms, practice questions with answers and flashcards.
  Then say "quiz me on it".
- **Deal hunter**: "Find the best price for a 2TB NVMe SSD." You get a price table and a
  buy-now-or-wait verdict.

Reports are saved in the `reports` folder. To make your own agent, copy one of the `.md`
files in `agents/` and edit the text.

---

## 6. Knowledge folder

Put notes, PDFs, Word files, slides and text files in **OneDrive → JARVIS Knowledge**
(created on first use, or press INDEX NOW in **⚙ → PLUGIN SETTINGS → KNOWLEDGE FOLDER**).
Then ask "What do my notes say about…?" or "Check my documents: when is the coursework due?"

Because it's in OneDrive, both PCs see the same files, and you can drop a file in from the
OneDrive app on your phone. Scanned PDFs without real text can't be read; INDEX NOW lists them.
Everything is searched on your own PC; nothing is uploaded except the passages JARVIS
reads to answer.

---

## 7. Interrupt by voice

*(v1.6)* Jarvis now uses real echo cancellation — the same technique video calls use — to
hear you over its own voice, so just start talking and it stops, even on laptop speakers.
If it ever stops by itself (very loud speakers, lots of typing), set **careful** below.


It's **on**: just start talking while Jarvis is speaking and it stops. Turn it off or make
it *careful* in **⚙ → PLUGIN SETTINGS → VOICE INTERRUPT**, or by voice.

How well it works depends on your speakers. With headphones it's reliable.
On loud desk speakers, if JARVIS stops itself now and then, set it to **careful**. The
first fraction of a second of your interruption is used to detect you, so start with
"stop" or "wait".

---

## 8. Smart home

Uses **Home Assistant** (free, <https://www.home-assistant.io>), which works with Philips
Hue, Tuya/Smart Life, TP-Link Tapo/Kasa, Govee, IKEA, Xiaomi and most other brands. If you
don't have smart devices yet, skip this.

1. Install Home Assistant (a Raspberry Pi or a spare PC is simplest) and add your devices there.
2. In Home Assistant: click your profile → **Security** → **Long-lived access tokens** →
   **Create token**, and copy it.
3. In JARVIS: **⚙ → PLUGIN SETTINGS → HOME ASSISTANT**: the address (e.g.
   `http://homeassistant.local:8123`) and the token → **TEST**.

Say device names as they appear in Home Assistant ("desk lamp", "bedroom light").
Unlocking doors, opening the garage and disarming alarms always ask for on-screen
confirmation.

---

## 9. Using JARVIS on all your devices

**Desktop and G14: one memory.** On **both** PCs: **⚙ → PLUGIN SETTINGS → DEVICE SYNC** →
switch **ON** → leave the folder as suggested (`OneDrive\JARVIS Sync`) → **TEST & SYNC NOW**.
Make sure OneDrive is signed in with the same Microsoft account on both. What one PC learns
about you, the other knows within a minute or two. Both can be on at the same time.

Not synced, on purpose:

- **Keys and settings.** Each PC has its own microphone and speakers, so connect Google
  and Spotify on each.
- **Routines.** Set up the morning briefing and routines on **one** PC only (the desktop),
  or you'll hear them twice.

**OnePlus 13: remote control.**

1. Install **Tailscale** from the Play Store and sign in with the same account you used on
   the PCs. This lets the phone reach your PCs securely from anywhere, not just on home Wi-Fi.
2. Make sure Tailscale is **connected** on both (the phone shows a key icon in the status
   bar; the PC shows the Tailscale icon in the tray as connected).
3. On the PC, open the **phone dashboard** in JARVIS and scan the QR code with the phone.
   When the PC is on Tailscale, the QR code now uses its Tailscale address (`100.x.x.x`),
   so it works at home, at work and on mobile data. Under the code you'll see both
   addresses: **Anywhere (Tailscale)** and **Same Wi-Fi only**.
4. Add it to your home screen from the browser menu so it opens like an app.

**If the page doesn't load on the phone:**

- Is Tailscale on on the phone? Without it, only the "Same Wi-Fi only" address works.
- Is JARVIS running on that PC, and did you accept the Windows firewall prompt the first
  time you opened the QR code? If you said no, open the QR code again and accept it.
- Still nothing: in the Tailscale app on the phone, tap the PC and check it shows as
  connected. Then type `http://100.x.x.x:8000` (the PC's address from that screen) in Chrome.
- Work Wi-Fi often blocks phone-to-laptop traffic; Tailscale gets round that, the
  "Same Wi-Fi" address won't.

**To talk to JARVIS from the phone's microphone** the browser needs a secure (https) page.
Tailscale can give you one for free:

1. Go to **login.tailscale.com/admin/dns**, make sure **MagicDNS** is on, and press
   **Enable HTTPS** (once, for your whole account).
2. In JARVIS: ⚙ → PLUGIN SETTINGS → PHONE & DEVICES → switch on **Secure phone link
   through Tailscale** → SAVE.
3. Open the QR code again. It now points to `https://<pc-name>.<something>.ts.net` with a
   real certificate, so there's no warning and the phone's microphone works. If Tailscale
   says it needs permission, run `tailscale serve --bg 8000` once in a terminal opened
   as administrator.

Settings in the same place: **Phone dashboard QR code uses** = auto (Tailscale when it's
on), tailscale, or home wi-fi.

Your calendar, email and to-do list are already on the phone through Google's own apps,
and documents through OneDrive.

**Which PC should be the "main" JARVIS?** The desktop: it's on the most, has the most
power, and runs routines. The G14 is a full JARVIS too, sharing memory, for when you're
out.

---

---

## 11. Claude with your Claude subscription (no API key)

Jarvis can use the Claude account you already pay for, through **Claude Code**. Your
usage comes out of the same limits as your Claude chats.

1. Install Claude Code. In PowerShell:
   ```powershell
   irm https://claude.ai/install.ps1 | iex
   ```
2. Run `claude` once, log in with your Claude account, then close it.
3. In Jarvis: **⚙ → ENGINE & PROVIDERS** → pick **Claude (your subscription, via Claude
   Code)** as the provider for background requests → **TEST**.

Keep **Gemini Live** as the voice: Claude Code takes a second or more to start each
answer, which is fine for writing and research but too slow to talk back and forth.
Claude Code runs with all its tools switched off here, so it can only write text; it
can't touch your files.

## 12. Writing voice

Anything longer than a sentence (emails, messages, documents, captions) is written by
the best writer available: Claude through your subscription, then a Claude API key if
you have one, then Gemini.

**⚙ → PLUGIN SETTINGS → WRITING VOICE**:
- **How you write:** a few words, e.g. `casual, short sentences, no emojis, British spelling`.
- **Sign emails as:** your name.
- **TRY IT** writes a test message.

Say "write my teacher an email asking for an extension and put it in my drafts". The
draft goes into Gmail **Drafts**; nothing is sent from the writer.

## 13. Proactive alerts

Once Google is connected, every few minutes Jarvis:
- tells you about **important new email** (Gmail's important mark, or anyone on your VIP
  list), puts a **suggested reply** on screen, and sends it only if you say so and press
  CONFIRM;
- offers to **add dates from emails** to your calendar;
- **reminds you before events** (15 minutes by default), and once a day lists **to-dos
  that are due**.

Promotions and social mail are skipped, nothing is announced twice, and the first run
doesn't read out your old mail. Settings are in **⚙ → PLUGIN SETTINGS → PROACTIVE
ALERTS**: how often it checks, reminder time, VIP senders, and on/off switches. Say "check
my mail now" any time.

If both PCs are on, both will announce new mail. Turn proactive alerts off on the one you
use less, or keep the laptop in study or gaming mode while the desktop is on.

## 14. Modes

Say **"work mode"**, **"study mode"**, **"music mode"**, **"I'm watching a movie"**,
**"gaming mode"** or **"back to normal"**.

| Mode | What changes |
|---|---|
| Normal / Work | All alerts on; work keeps replies short and practical |
| Study | Only urgent alerts; routines stay quiet; the rest is summed up when you finish |
| Music | Only urgent alerts; very short replies |
| Watching | Silent unless spoken to; only urgent alerts |
| Gaming | Silent, nothing pops up on screen; only urgent alerts |

"Urgent" means mail from your VIP list and events about to start. When a quiet mode ends,
Jarvis sums up what came in meanwhile.

**Per device:** **⚙ → PLUGIN SETTINGS → MODES → Mode this computer starts in**. For
example, set the G14 to *work* and the desktop to *normal*. **Gaming mode switches on by
itself** when a game from Steam, Epic, Riot, Battle.net, EA or Ubisoft starts, and back
off when you close it. Add other games by their `.exe` name in the same section.

## 15. Spotify on a chosen device

"Play Blinding Lights **on my phone**", "move it to the **desktop**", "what devices are
there?". Spotify must be open on that device. Jarvis tells the laptop and desktop apart
by itself. If your devices have unusual names, add nicknames in **⚙ → PLUGIN SETTINGS →
SPOTIFY**, e.g. `desktop=DESKTOP-AB12, laptop=ROG-ZEPHYRUS`.

## 16. Google Drive and Docs

1. In Google Cloud, make sure **Google Drive API** and **Google Docs API** are enabled
   (APIs & Services → Library).
2. In Jarvis: **⚙ → PLUGIN SETTINGS → GOOGLE → CONNECT GOOGLE** once more, and allow the
   new Drive permissions. Gmail, Calendar and Tasks keep working whether or not you do this.

Then: "find my chemistry notes in Drive", "read the first one", "make a Google Doc with a
packing list for my trip". Jarvis can read all your files but can only change Docs it
created itself.

## 17. Notion

1. Go to <https://www.notion.so/profile/integrations> → **New integration** → name
   `JARVIS`, type **Internal** → **Save** → copy the **Internal Integration Secret**.
2. **⚙ → PLUGIN SETTINGS → NOTION**: paste it. Optionally paste the link of a page to
   use as the **home page**, where new pages and notes go. Press **TEST**.
3. In Notion, open each page Jarvis should see → **•••** → **Connections** → **JARVIS**.
   Sharing a parent page shares everything inside it.

Then: "search Notion for project ideas", "add 'buy a mic' to that page", "make a Notion
page called Trip plan".

## 18. Notes

"Note that the router password is on the fridge", "take a note: …" (rough dictation is
tidied into bullet points), "note down what we just talked about", "what did I note
today?", "did I note anything about the dentist?".

Notes go to **JARVIS Notes.md** in your knowledge folder by default, so they're on both PCs,
in the OneDrive app on your phone, and searchable with your other documents. To keep them in
Notion or a Google Doc instead: **⚙ → PLUGIN SETTINGS → NOTES**.

---

## 19. Editing before anything happens

You never have to ask Jarvis to redo a draft to change a word.

- **Confirmations have EDIT.** When Jarvis asks you to confirm sending an email or a reply,
  press **✎ EDIT** and the To, Subject and message become text boxes. Fix anything, then
  press **CONFIRM** and your version is sent. The confirmation doesn't time out while you're
  editing.
- **Drafts open editable.** Anything the writing voice writes appears in a panel you can
  type in:
  - emails: **SAVE TO DRAFTS** / **UPDATE DRAFT**, **SEND**, **COPY**;
  - other text: **SAVE AS NOTE**, **MAKE GOOGLE DOC**, **COPY**.
- **Suggested replies** (proactive alerts) open the same way: change the reply, then
  **SEND REPLY** or **SAVE AS DRAFT**.
- **Notes** open after saving. Fix a typo and press **SAVE CHANGES**.
- **Calendar events** Jarvis adds open with their title, time, length, place and notes.
  Change any of them and press **SAVE CHANGES**.

Pressing **SEND** in a panel is your own click, so it sends straight away without a second
confirmation. Anything Jarvis wants to send on its own still waits for CONFIRM.

---

## 20. Update yourself (no more reinstalling)

Say **"update yourself"** or press **⚙ → PLUGIN SETTINGS → UPDATES → UPDATE NOW**. Jarvis
downloads the latest version from your fork, installs any new packages, closes and
reopens itself. Your settings, keys and memory are untouched. Once a day it tells you when
an update is waiting; it can also install updates by itself at start-up.

If you ever edit Jarvis's files by hand, the update stops rather than overwriting them.

## 21. Your phone: alerts and commands (ntfy)

1. On the OnePlus, install **ntfy** from the Play Store.
2. On one PC: **⚙ → PLUGIN SETTINGS → PHONE & DEVICES → SEND TEST + SHOW TOPICS**. A test
   notification is sent, and the panel shows two names: the **alerts topic** and the
   **commands topic**.
3. In the ntfy app, tap **+** and subscribe to both, using exactly those names.
4. With **device sync** on, the other PC picks up the same names by itself. Otherwise
   copy them into the same fields there.

The topic names work like passwords; keep them to yourself. To use your own ntfy server
instead of the public one, fill in the server and token fields.

**Phone alerts** (⚙ → PHONE ALERTS): important email, "event in 15 minutes" and due
to-dos are pushed to the phone when you've been away from the PC for 10 minutes (or
always, or never). You can choose to show just "New important email" without sender
or subject. "Send this to my phone" works any time.

## 22. Control your PCs from your phone, and each other

In the ntfy app, open the **commands** topic and type or dictate a message (the
keyboard's microphone works):

| Message | What happens |
|---|---|
| `desktop: turn on and launch spotify and valorant` | The desktop is woken, then opens Spotify and starts VALORANT once it's up |
| `launch spotify and valorant` | Goes to the PC that answers untargeted commands (the desktop by default) |
| `desktop: play lofi beats on spotify` | Plays on the desktop |
| `laptop: lock` / `desktop: sleep` | Locks or sleeps that PC |
| `all: status` | Each PC replies: on, mode, game running, battery |

Replies arrive on your alerts topic. If a PC is off, its commands wait and run when it
starts (up to 3 hours old by default), and it tells your phone "Desktop is on". By
voice, PC to PC: "wake the desktop", "on the desktop launch Valorant", "what's my
desktop doing?".

**Getting "turn on the desktop" to work.** Wake-on-LAN, once, on the desktop:

1. In the BIOS, enable **Wake on LAN** (sometimes called "Power On By PCI-E").
2. Windows → **Device Manager** → your network adapter → **Properties**:
   - **Power Management**: tick *Allow this device to wake the computer* and *Only allow a
     magic packet*.
   - **Advanced**: set *Wake on Magic Packet* to **Enabled**.
3. Open Jarvis on the desktop once while the laptop is on, so the laptop learns its address.

A wake signal only travels inside your home network, so it has to come from a device
that's at home and awake. How to make "turn on" work when you're out:

- **Best: put the desktop to Sleep instead of shutting it down.** Jarvis stays running,
  so commands from your phone are picked up the moment it wakes. Set *Settings → Accounts →
  Sign-in options → If you've been away, when should Windows require you to sign in
  again* to **Never** if you want apps to open without typing your PIN.
- **A smart plug plus the BIOS setting "Restore on AC power loss: Power On":** with the
  plug's Home Assistant entity in *Wake the desktop with this smart plug*, any Jarvis can
  switch it.
- **Your router's remote Wake-on-LAN,** if it has one (many ASUS and TP-Link routers do).

After a full shutdown Windows waits at the sign-in screen, and Jarvis only starts once
you sign in. Automatic sign-in (Microsoft's free *Autologon* tool) avoids that, but then
anyone who can switch the desktop on can use it. Sleep is the safer choice.

## 23. Permissions: what Jarvis may do on its own

| Setting | Where | Default |
|---|---|---|
| Accept commands from the phone / other PC | PHONE & DEVICES | On |
| Open apps and games remotely | PHONE & DEVICES | On |
| Spotify remotely | PHONE & DEVICES | On |
| Lock / sleep remotely | PHONE & DEVICES | On |
| Shut down / restart remotely (60-second warning, cancellable) | PHONE & DEVICES | **Off** |
| Free-form remote requests handed to Jarvis | PHONE & DEVICES | **Off** |
| Ignore remote commands older than | PHONE & DEVICES | 3 hours |
| Proactive agents run on this PC | PROACTIVE AGENTS | Desktop only |
| Start prep for exams/interviews by itself | PROACTIVE AGENTS | Asks first |
| Ask before sending any email | GOOGLE | On |
| Proactive alerts / phone alerts | PROACTIVE ALERTS / PHONE ALERTS | On / when away |
| Install updates by itself | UPDATES | Off |

Remote commands can never press an on-screen CONFIRM, so sending email always needs you at
the PC.

## 24. Proactive agents

- **Price watches:** "tell me when the RTX 5080 drops below 800 pounds". It's checked
  every 12 hours; at your price you get an alert on screen and phone, and an offer of a
  full deal-hunter report. "What prices are you watching?", "stop watching number 1".
- **Exam and deadline prep:** each half hour Jarvis looks a few days ahead in your calendar
  for exams, tests, deadlines, interviews and presentations. It **asks** ("want me to make
  a study pack?") or, if you choose *auto*, just starts the study coach or a prep brief.
  "Prepare me for my upcoming exams" runs it now.
- **Daily digest:** set a time and the digest agent writes it every morning.

Only one PC runs these (⚙ → PROACTIVE AGENTS → *Run proactive agents on this PC*), so
nothing is done twice.

## 25. Games

"Launch Valorant", "start CS", "play Rocket League", "what games do I have?", "what did I
play recently?". Steam (every library drive), Epic, Riot and Battle.net games are found
by themselves. Starting a game switches on gaming mode. Discord messages work through the
built-in messaging: "message Sam on Discord: on in 5".

## 26. Morning briefing

The opening briefing now covers **your day first**: what's on your calendar today,
important unread email, to-dos due, the weather if it matters (set your city in ⚙ →
BRIEFING), price drops, and on weekends a pick from your reading list. The news comes
after. In gaming, watching or music mode it's one sentence. "What's my day like?" works
any time.

## 27. Study timer

"Start a 25-minute study session on chemistry", "study maths for 50 minutes, one round",
"how long's left?", "stop studying", "how much did I study this week?". Study mode is on
during the session. In breaks you get three quick questions from your own notes on that
subject (knowledge folder) if you want them.

## 28. Screen helper

- **"Summarise this page":** the page open in Chrome, Edge, Firefox, Brave or Opera.
- **"Explain this":** select text first, or copy it; good for error messages and code.
- **"Save this page for later":** adds it to your reading list.

It borrows the address bar for a moment and puts your clipboard back afterwards. Pages
behind a login can't be fetched; select the text and say "explain this" instead.

## 29. Money

"I spent 12 on lunch", "paid 9.99 for Spotify", "how much did I spend this month?",
"set my food budget to 150", "how am I doing on budgets?", "undo that". Everything goes
into a Google Sheet called **JARVIS Money** that you can open on your phone. Set your
currency and budgets in ⚙ → MONEY.

Enable the **Google Sheets API** in Google Cloud (APIs & Services → Library). If you haven't
pressed CONNECT GOOGLE since Drive was added, do that once as well.

## 30. Reading & watch list

"Add Dune to my watch list", "save this link to read later", "what's on my watch list?",
"pick something for tonight", "I've watched Dune". It's a list called **Reading &
Watching** in Google Tasks, so it's on your phone too.

---

## 31. Life profile: Jarvis remembers your life

Say **"set up my profile"** (or "get to know me") and Jarvis interviews you, one area
at a time: studies, work, music lessons, comedy and writing, travel, training. Skip
anything that doesn't apply and add your own areas. After that you don't need to say
"remember": when you mention your life ("had my guitar lesson, finally got the F barre
chord", "swam 2 km today", "I want to see Japan in spring") it's saved to the right area.

Each area keeps an **About**, **Goals** (with dates if you give one) and a dated **Log**.
Ask "what do you know about my IRONMAN training?", "what do you know about me?", or
"I did the Japan trip!" to tick off a goal. Goals with a date show up in the morning
briefing as a countdown.

Everything is in your OneDrive knowledge folder under **JARVIS Life** (one readable file
per area), so both PCs and your phone see it, and you can edit it yourself. A one-line
summary of each area is also in Jarvis's own memory, so it knows the basics from the
first word of every conversation.

## 32. Knowing it updated

The header reads **MARK LVII · YUGAM EDITION · v1.7** (your name, from first launch) and
the status bar says **EDITION · v1.7**. After each update a **What's new** panel opens
once; click the version in the header to see it again. Ask "what's new?" or "what can you
do?" and Jarvis answers from the same list.

---

## 33. Keeping up with Fatih's updates

Fatih releases new Marks as new repositories, so his updates don't arrive in this fork
automatically. When a new Mark comes out, ask Claude Code to move these add-ons onto it:
the plugins and agents are separate files, so it's mostly copying, plus the small change
in `main.py` for voice interrupt.

## 34. The holographic HUD

The centre of the window is now a holographic display (the **HUD** button in CONTROLS
cycles holographic → animated face → reactor core). What moves means something:

- the rings turn faster while Jarvis is thinking, and a radar sweep works the problem;
- the colour is the state: green listening, gold thinking, accent colour speaking;
- the ring of bars around the core is the real sound: your voice while it listens, its
  voice while it speaks;
- **satellites**: every tool it uses (SPOTIFY, GMAIL, CLAUDE CODE…), every panel it opens
  and every card it leaves flies out of the core as a labelled node, pulses while it's
  fresh, orbits, and fades after a few minutes. A glance tells you what it's been doing.

---

### The immersive layout (v1.6, the default)

The side panels are gone unless you want them: the holographic display fills the window
and things come to you.

- **Cards**: anything Jarvis shows (weather, an email, your calendar, search results, a
  finished job) slides out of the core as a card beside it and drifts away after a
  minute. Hover to keep it, **PIN** to keep it until you close it, **EXPAND** for the full
  text. Alerts that arrive while you're busy come as pinned cards.
- **Captions**: what you and Jarvis say, live, at the top; they fade after a few seconds.
- **Vitals**: CPU, memory, battery, mode and busy/away in one line, bottom left.
- **Command bar** under the display: type, MIC ON/OFF, STOP, and **◫ PANELS**.

**F2** or the ◫ button in the header switches between immersive and the classic panels
(systems, status, tasks, log); the choice is remembered.

---

## 35. Talking to someone else, and being away

Jarvis works out whether you're **free**, **busy** or **away**:

| You are | Because | What Jarvis does with news |
|---|---|---|
| free | at the PC, not busy | says it, and after finishing something suggests a next step |
| busy | you said so; you just spoke but not to it; another app (Discord, Zoom, Teams) is using the mic; gaming or watching mode | a **card that stays** on screen, top right, until you ✕ it |
| away | no keyboard or mouse for 10 minutes | the card **and** a phone notification |

Say **"I'm talking to someone"**, **"I'm on a call"** or **"give me ten minutes"** and it goes
quiet (with the wake word on it sleeps until "Hey Jarvis"). **"I'm back"** — or just being
free again — and it sums up what came in. If you start talking to someone without
saying so, it should notice from what you say and stay silent.

Settings: ⚙ → PLUGIN SETTINGS → **CONVERSATION & PRESENCE** (how long a pause lasts, when
you count as away, the welcome-back summary, voice confirm, following audio devices).

**Confirm by voice:** when a confirmation is on screen, say **"confirm"** / **"yes, send it"**
or **"cancel"** / **"no"**. Only your microphone counts; a command from the phone can't
confirm anything.

---

## 36. Claude Code from Jarvis

Jarvis can hand coding jobs to the Claude Code that's signed in on the PC (your Claude
subscription, no API key) and tell you when they're done.

- **"Ask Claude Code to add dark mode to my portfolio"** — starts a job in that project.
  By default it **plans first** and changes nothing; Jarvis reads you the gist.
- **"Go ahead"** — carries out the plan with file edits allowed (you confirm by voice or
  on screen first).
- **"Tell Claude to also update the README"** — a follow-up in the same Claude session.
- **"What's Claude Code doing?"**, **"stop Claude Code"**, **"open Claude Code in my
  thesis folder"** (an interactive window), **"which projects do you know?"**

Projects: folders directly inside `~/Projects`, `~/Code`, `~/source/repos` or
`~/Documents/GitHub` are found by name. Add others in ⚙ → PLUGIN SETTINGS → **CLAUDE CODE
CONTROL** (`site=C:\Code\portfolio; jarvis=C:\Users\you\Mark-LVII`), or say "add my
portfolio project at …".

Permissions: **plan** (read only), **edits** (edit files; shell commands only from the
list you allow, e.g. `git status, npm test, pytest`), **full** (anything — off unless you
switch it on, and always confirmed). Progress shows in the log and as a CLAUDE CODE
satellite; the result arrives the presence-aware way (spoken, card, or phone).

---

## 37. One personality, shaped by talking to it

Jarvis has one character: on your side, honest, curious, dry-humoured, steady. It knows your
life from its memory and life profile and uses it: it notices progress, remembers what
you were nervous about and asks how it went.

Change how it behaves by saying so, in your own words:

- "Be more sarcastic." / "Less chatty." / "Stop calling me sir, it's Yugam."
- "Talk with a slight British accent." / "Be more like a coach when I'm training."
- "What have I asked you to change?" / "Forget the sarcasm one." / "Go back to default."

A change applies from that moment, with no reconnect, and is remembered for every later
session. Voices themselves (Charon, Puck, Kore and so on) are chosen in ⚙ → Customize;
changing the voice rebuilds the connection, but the last turns of the conversation carry
over and Jarvis finishes its sentence first. It won't impersonate a real person or a film
character: Gemini can't copy anyone's voice, and Jarvis offers the qualities instead.

---

## 38. Audio that follows your devices

Turn your headphones on and Jarvis moves to them; turn them off and it goes back to the
speakers — no restart. It notices when Windows adds or removes an audio device, and when
the microphone stops sending sound or the speakers stop taking it, then reopens audio
on whatever is there (your chosen mic/speakers in ⚙ → audio when they're connected, the
Windows default otherwise). The log says "SYS: Audio connected: … — switching devices".
Switch it off in CONVERSATION & PRESENCE if you'd rather it didn't.

---

## 39. Memory boxes: what Jarvis always keeps in mind

Jarvis's memory has ordinary categories (identity, preferences, projects, people, wishes,
notes), of which only a recent slice rides in each conversation and the rest is looked up
on demand. Two boxes are different — they are **always in front of it, in full**:

- **WHO YOU ARE** (`core_self`): its character, its role with you, standing rules you've given.
  "You're my training partner and chief of staff, not a butler." "Never bring up work after 9pm."
- **THE ESSENTIALS** (`core_user`): what matters most about you, so it steers toward it:
  main goals, what drives you, how you want to be helped.
  "Finishing the IRONMAN 70.3 is my top goal." "Be direct, push me when I'm slacking."

Fill them by talking: "remember this always: …", "this is who you are to me: …", "that's
essential, pin it". Keep them short and few (about 1,500 characters each; the oldest
lines lead, newer ones past the limit are still remembered but ride in the ordinary
memory). "What's in your core memory?" and "forget …" work as for any memory. They sync
between your PCs like the rest of memory. Your personality tweaks ("be more sarcastic")
are separate and live in §37.

---

## 40. Claude on the web: your Jarvis session

Jarvis can open Claude in your own Chrome (already signed in), go to your Jarvis Claude Code
session and hand it requests — including "add this feature to yourself".

**One-time setup (2 minutes)**
1. On the laptop, open Chrome with your **yugamsmart** profile, go to
   **claude.ai/code** and open (or start) the session for Jarvis — name it
   "personal jarvis assistant" and point it at the repo `Yugam2508/Mark-LVII`. Leave it in front.
2. Say **"remember this as my Jarvis session"**. Jarvis copies the address from the browser
   bar and saves it (or paste it by hand in ⚙ → PLUGIN SETTINGS → **CLAUDE ON THE WEB**).
3. Check it: say **"check Claude on the web"** (or, in PowerShell,
   `.\.venv\Scripts\python.exe -m plugins.claude_web`). It says whether Chrome, the profile
   name `yugamsmart` (spelled as Chrome's profile menu shows it), the session address and the
   clipboard/keyboard pieces are all there, with a fix for anything that isn't.
4. Say **"open Claude"**: Chrome should open on that session.

**At work (Claude desktop app):** say **"use the desktop app"** (or set *Open Claude in* to
desktop). Jarvis then starts the Claude app the way Windows starts any app, brings its window
forward, pastes, and presses Enter on "send it". Open the Code tab and your Jarvis
session once yourself so it's the one showing; say **"use Chrome"** to switch back at home.

**Using it**
- "Open Claude" / "open my Jarvis session" — opens the page.
- "Add a pomodoro mode to yourself" / "give yourself the ability to …" — Jarvis writes a
  full request (what you want, the repo, the rules in AGENTS.md, tests, docs, a pull
  request) and shows it for **EDIT / CONFIRM** (say "confirm"). It then opens the page and
  **pastes** it — it does *not* send it.
- Read it, then say **"send it"** — the Claude window doesn't have to be in front. Jarvis
  brings that window forward itself and presses Enter. If it can't find a Claude window at all
  it refuses rather than press Enter somewhere else.
- When Claude says the pull request is ready, tell it **"merge it"** there, then tell Jarvis
  **"update yourself"**. New abilities arrive without reinstalling.
- "Tell Claude: …" pastes any message the same way.

For quick jobs on a project folder on this PC, "ask Claude Code to …" (§36) is faster; the
web session is for changes to Jarvis itself, since Claude there can open pull requests.

---

## 41. Notion in two minutes

Say **"set up Notion"**. Jarvis does what it can and tells you the next step; say it again
after each step:

1. It opens Notion's integrations page. Choose **New integration**, name it `JARVIS`, type
   *Internal*, pick your workspace, **Save**, then press **Copy** next to the *Internal
   Integration Secret* (starts `ntn_`).
2. Say **"set up Notion"** again. Jarvis takes the secret from the clipboard — you never say or
   type it, it isn't shown, and the clipboard is cleared afterwards.
3. In Notion make a page called **Jarvis**, press **•••** → **Connections** → add **JARVIS**
   (sharing a parent page shares everything inside it). Say "set up Notion" once more and it
   sets that page as the home for new notes.

Then: "add *buy a new mouse* to my Jarvis page", "search Notion for project ideas", "make a
Notion page called Trip plan". Notion pages are only visible to Jarvis once shared with the
connection.

---

## 42. In the system: tray, hotkey, handoff

- **Tray icon.** Closing the window now hides Jarvis to the notification area and it keeps
  listening (a bubble tells you once). Click the icon to show or hide it; right-click for mute,
  stop talking, layout and **Quit**. Turn off in CONVERSATION & PRESENCE → *Closing the window
  keeps Jarvis running in the tray*.
- **Ctrl+Alt+J** brings Jarvis to the front from any window (Windows; on other systems it works
  while Jarvis has focus). Start at login is ⚙ → CONTROLS → AUTO-START.
- **Handoff.** With device sync on, each Jarvis leaves its last few turns in the sync folder. Move
  to another device and it knows what you were just discussing; "where were we on the desktop?"
  pulls it on demand. Turns are kept for 30 minutes and overwritten.

The bigger plan — one always-on Jarvis that every device reaches — is in `HUB.md`.

---

## 43. When Claude Code or the phone link doesn't work

Both have a self-check that names the broken step and the fix. Run it first.

**Claude Code** — say "diagnose Claude Code", or in PowerShell:
```powershell
cd $env:USERPROFILE\Jarvis
.\.venv\Scripts\python.exe -m plugins.claude_code
```
Typical results: *not found* → `irm https://claude.ai/install.ps1 | iex`, then reopen
PowerShell and Jarvis; *not signed in* → run `claude` once and log in with the Claude
account; *knows no projects* → add `jarvis=C:\Users\<you>\Jarvis` in CLAUDE CODE CONTROL.

**Phone link** — with Jarvis running and Remote Control open, in PowerShell:
```powershell
cd $env:USERPROFILE\Jarvis
.\.venv\Scripts\python.exe -m core.tailnet
```
It checks Tailscale, that Jarvis's page is listening, that it answers on the Tailscale
address, the Windows network category, and the firewall rule, and prints the fix for the
first one that fails (the usual one: Windows treating Tailscale as a "Public" network).

---

## Credits and licence

Mark LVII is by FatihMakes, licensed CC BY-NC 4.0 (personal, non-commercial use). These
add-ons are written for this fork and follow the same licence.
