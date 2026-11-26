# The hub: one Jarvis, everywhere (design for v2)

Goal: Jarvis is **one mind that is always on**, and every device — laptops, phone, a speaker in
the room — is a way to reach it. Not an operating system per device.

## What exists today (v1.7)
| Piece | State |
|---|---|
| Memory (incl. the two always-on boxes), personality, life profile | shared between PCs through the sync folder |
| Conversation handoff | the last turns follow you between devices (`core/handoff.py`) |
| Phone alerts and commands | ntfy topics, per-PC permissions, Wake-on-LAN |
| Phone dashboard | per-PC, over Tailscale |
| Tray icon, Ctrl+Alt+J, start at login | Windows |
| Local-model engine | `providers/` already speaks OpenAI-style servers (Ollama, LM Studio) |
| `core/cloud.py` | a *Linux server* body (systemd install, Telegram, jobs). **Not** connected to this fork's desktop app and not Windows-ready: a starting point, not a hub |

So today there are several Jarvises that share notes. The hub makes them one.

## Decisions (made)
* **The desktop sleeps, shuts down or is locked most of the day**, so it can't be the hub. The hub is a
  small **always-on Linux box** (see "Hardware"). The desktop becomes the *heavy worker*: the hub wakes
  it with Wake-on-LAN (already built) when a job needs the 5070, and lets it sleep again.
* **Voice: try several.** Gemini Live stays the default. The local pipeline already exists in this
  codebase (`providers/engine_pipeline.py`: Whisper in, any OpenAI-compatible model such as Ollama,
  Piper out), so trying a local voice is a settings change, and a fine-tuned voice model can be
  slotted in later. Judge by feel after living with each for a week.
* **Phone: a real Android assistant** built in Android Studio. Design in `ANDROID.md`.

## The architecture
```
 phone (assistant app) ─┐                    ┌─ memory, personality, schedules, notices
 laptops ───────────────┼─ Tailscale ─► HUB ─┼─ proactive checks, price watches, digests
 room node (mic+speaker)┘  (always-on box)   ├─ event bus → whichever device you are at
                              │              └─ Home Assistant (lights, AC, plugs)
                              └─ Wake-on-LAN ─► DESKTOP (5070): local model, big jobs, Claude Code
```
* **Voice stays on each client** (a real-time audio stream relayed through the hub adds delay). A client
  asks the hub for its context at connect (memory boxes, personality, recent conversation, pending
  notices) and reports turns and events back. This replaces the sync folder with something faster.
* **Background work runs on the hub once**, not "on the desktop only". Results go to the event bus and
  reach you the presence-aware way (spoken, a card, or a phone push).
* **Auth:** Tailscale (only your devices) plus a pairing code per device.

## Hardware
| Role | Pick | About |
|---|---|---|
| Hub (always on) | Raspberry Pi 5 8 GB + SSD, or an N100 mini PC | £90-160, 5-10 W. Same code runs on either. Prefer the mini PC if you may run a small local model on the hub itself |
| Room node | ESP32-S3-BOX-3, or Pi Zero 2 W + a mic-array HAT and a speaker | £40-70 per room. Runs the wake word on the device |
| Local model | the desktop's 5070 (12 GB: 7-14B models, quantised) | woken on demand by the hub |

## About the Echo
An Echo cannot be used as a raw always-on microphone and speaker for your own software: Amazon
doesn't expose the audio. What an Echo *can* do, and it's worth having:
* **"Alexa, ask Jarvis to ..."** — a custom Alexa skill forwards what you said to the hub and Alexa
  speaks the reply. Needs a public HTTPS address for the skill (Tailscale Funnel or a small
  tunnel). Good for "turn the PC on", "what's on today", "send a message".
* **Alexa routines** that trigger Jarvis jobs, and Jarvis controlling Echo-connected devices.

For a *real* always-on microphone use the room node above: your own wake word ("Hey Jarvis"), your own
voice, nothing sent to Amazon. The node speaks the Wyoming protocol (the Home Assistant standard), so
it also works with Home Assistant if you use it.

## Phases (each ships on its own and is useful alone)
1. **Hub service** on the always-on box: state API (memory, personality, handoff), event bus,
   pairing, run-at-boot. Clients keep working from a local copy when the hub is unreachable and re-sync.
   *Test: stop the hub mid-conversation; the laptop carries on and re-syncs.*
2. **Move background work to the hub**: schedules, proactive agents, price watches; hub wakes the
   desktop for heavy jobs (Claude Code, local model).
3. **Local model**: Ollama on the desktop as the first responder for text and agents; cloud for the
   hard questions. Try local voice here (Whisper + Piper, then fine-tuned models).
4. **The Android assistant** (`ANDROID.md`): default digital assistant, own wake word, calls and
   texts, control of other apps, AC through the IR blaster, handoff with the hub.
5. **Room nodes and the Alexa skill.**

Phase 4 can start in parallel with phase 1: the app talks to the hub's API, and until the hub
exists it can talk to a laptop's dashboard.
