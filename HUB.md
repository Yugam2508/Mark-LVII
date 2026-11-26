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

## The architecture
```
 phone ─┐                          ┌─ memory, personality, schedules, notices
 laptop ┼── Tailscale ──►  HUB  ───┼─ agents / background jobs (Claude Code, research, digests)
 room  ─┘  (voice stays        │   ├─ proactive checks (mail, calendar, price watches)
  node      on the client)     │   └─ local model (RTX 5070) for most questions
                               └─ event bus: "task done", "email arrived" → delivered to whichever
                                  device you are at (presence-aware, as in v1.5)
```
* **The hub is the desktop**, always on (sleep is fine with Wake-on-LAN). A small FastAPI service
  started at login. It owns the state; clients hold nothing precious.
* **Voice stays on each client.** Gemini Live is a real-time audio stream; relaying it through the
  hub adds delay. A client asks the hub for its context at connect (memory boxes, personality,
  recent conversation, pending notices) and reports turns and events back. This replaces the sync
  folder with something faster and conflict-free.
* **Background work moves to the hub**: schedules, proactive agents and Claude Code jobs run there
  once, instead of "only on the desktop" by a setting. Results go to the event bus.
* **Auth:** Tailscale (only your devices can reach it) plus a pairing code per device, as `core/cloud.py`
  already does.

## Phases (each ships on its own and is useful alone)
1. **Hub service on the desktop.** State API (memory, personality, handoff), event bus, run-at-login.
   Clients keep working offline from their local copy and sync when the hub is reachable.
   *Test: kill the hub mid-conversation; the laptop carries on and re-syncs.*
2. **Move background work to the hub:** agents, proactive checks, price watches, Claude Code jobs.
3. **Local model on the hub** (Ollama on the 5070) as the first responder for text and agents;
   Gemini/Claude for the hard questions. No quota, nothing leaves the house for routine things.
4. **Phone as a real client:** first the dashboard as an installable app with push notifications;
   then an Android app registered as the *default assistant* (long-press power → Jarvis).
   Needs Android Studio and a device to test on — the one phase that must be built on your machine.
5. **Room nodes:** a Raspberry Pi with a mic array and a speaker, wake word on the device, audio to
   the hub's voice gateway (the hub opens the Live session for nodes that can't). *Hardware: about
   £60 per room.*

## Decisions needed from you before phase 1
* Is the desktop on (or asleep with WoL) most days? If not, a small always-on box (a mini PC or Pi)
  makes a better hub and the desktop becomes a very strong client.
* Is Gemini Live staying the voice, or do you want local speech (Whisper + a local voice) on the
  hub? Local speech removes Google from the loop but sounds less natural and costs the GPU.
* Phone: is an Android app worth the Android Studio setup, or is the installable web app enough
  for now?
