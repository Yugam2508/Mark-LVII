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
| Agents | Daily digest, study coach, deal hunter (run in the background) | `agents/*.md` |
| Knowledge folder | "What do my notes say about momentum?" | `plugins/knowledge_base.py` |
| Interrupt by voice | Talk over JARVIS to stop it | `plugins/voice_interrupt.py` + `main.py` |
| Smart home | "Turn off the bedroom light", "Movie mode" | `plugins/home_assistant.py` |
| Device sync | Both PCs share one memory | `plugins/device_sync.py` |
| Windows installer | One script for every PC | `install-windows.ps1` |

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

**⚙ → PLUGIN SETTINGS → VOICE INTERRUPT → ON**, or just say "let me interrupt you".
Then talk over JARVIS and it stops.

It's off by default because it depends on your speakers. With headphones it's reliable.
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
2. On the PC, open the **phone dashboard** in JARVIS and scan the QR code with the phone.
   Away from home, replace the address in the link with the PC's Tailscale address
   (`100.x.x.x`, shown in the Tailscale app), keeping the port number after the colon.
3. Add it to your home screen from the browser menu so it opens like an app.

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

## 19. Keeping up with Fatih's updates

Fatih releases new Marks as new repositories, so his updates don't arrive in this fork
automatically. When a new Mark comes out, ask Claude Code to move these add-ons onto it:
the plugins and agents are separate files, so it's mostly copying, plus the small change
in `main.py` for voice interrupt.

## Credits and licence

Mark LVII is by FatihMakes, licensed CC BY-NC 4.0 (personal, non-commercial use). These
add-ons are written for this fork and follow the same licence.
