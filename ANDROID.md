# Jarvis on Android: an assistant that is part of the phone

Goal: the OnePlus 13 behaves as if Jarvis were built into it. Long-press power (or the assistant gesture)
opens Jarvis; saying "Hey Jarvis" works with the screen off; it can call, text, open and drive other
apps, run the AC from the IR blaster, and carry on a conversation started on a PC.

## You don't need root for most of it
Rooting is allowed, but it costs more than it gives: banking and wallet apps and Google Pay can refuse a
rooted phone (Play Integrity), OnePlus updates get awkward, and almost everything below works without it.
The few things that need more than a normal app can be granted over ADB (or **Shizuku**, which gives an
app ADB-level power through wireless debugging), which keeps the phone intact. Plan: no root; revisit only if
a specific wall appears.

## What each wish needs
| You want | How | Notes |
|---|---|---|
| Long-press power opens Jarvis | App implements `VoiceInteractionService` + `VoiceInteractionSession`; you choose it in Settings → Apps → Default apps → Digital assistant app | The standard assistant role. Works without root |
| "Hey Jarvis" with the screen off | Own always-on **foreground service** running an on-device wake word (openWakeWord/Porcupine) | **The hard part.** Google's own "Hey Google" is privileged, so third-party apps run their own. Android 14+ restricts starting a microphone service from the background; the assistant role and a few ADB-granted permissions are the way round it. I'd prototype this first |
| Make calls, send texts | `CALL_PHONE`, `SEND_SMS` runtime permissions (sideloaded, so no Play Store restrictions) | Reads contacts by name; confirm-before-send as on the PC |
| Read and answer messages | `NotificationListenerService` + reply actions | Needs your one-time grant in Settings |
| Control other apps | `AccessibilityService`: read the screen and tap, type, scroll in any app | Powerful and fragile (apps change); the closest thing to "does it for you" |
| Open apps, set alarms, timers, navigation | Standard intents | Reliable |
| AC through the IR blaster | `ConsumerIrManager` (the OnePlus 13 has an IR blaster; check yours with any IR app) | It transmits only: you need your AC's codes (found from a database by model, or learned once with a cheap IR learner). Also exposed as a hub device so the room node and Alexa can use it |
| Conversation handoff | App is a client of the hub (or a laptop meanwhile) and pulls recent turns | Same mechanism as `core/handoff.py` |
| Talk to Jarvis | Gemini Live audio stream from the app, or the hub's voice gateway | Same personality, memory boxes and tools as the PC |

## Status
**Steps 1 and part of 3 are written** (`android/`, with its own README): pairing, conversation
screen, assistant registration; and the phone doing things when the PC asks — contacts, calls, texts,
find-my-phone, status — through a foreground link service that restarts after a reboot. It compiles
against the real Android 15 framework and its parsing logic is unit-tested; it has not yet been run on
a phone. Still to come: wake word (step 2), notifications and the IR blaster, control of other apps.

### Cab fares (Mark LXII)
"Cheapest cab to X" (`plugins/cab_fares.py` on the PC, `FareCheck.kt` + `FareParse.kt` on the phone). Grab, Gojek,
TADA and Zig have no public fare API, and deep links that prefill a destination are undocumented for most of them
and need coordinates, so the phone drives each app through the accessibility service the way you would: fresh
launch → "Where to?" → types the destination → taps the best-matching suggestion → reads every price on the fares
screen. Prices are the one thing these apps always render as text, so parsing starts from a price and looks back
for the ride's name; that survives redesigns better than view ids. It taps only words from short allow-lists,
never anything matching book/order/request/pay, and nothing at all once a price shows. Trade-offs: it is personal
use of your own signed-in apps, on request only, but their terms forbid automated access in general terms; a
check takes 15–30 s an app and the screen is taken over meanwhile; an app update can break one app's flow (each
failure returns the trace and the words on screen so the lists can be fixed).

## Build plan (Android Studio, Kotlin)
1. **Skeleton + assistant role** — opens on long-press power, shows the holo display, text and push-to-talk
   voice to a laptop's dashboard. *Done when: long-press power opens it and "what time is it" works.*
2. **Wake word in a foreground service** — measure battery and whether Android keeps it alive. *Done
   when: "Hey Jarvis" works with the screen off for a day.*
3. **Phone abilities** — calls, texts, contacts, alarms, IR, notifications.
4. **Accessibility control of other apps** — start with two you use daily.
5. **Hub client and handoff.**

The Android work is done on your laptop, in Android Studio, with the phone on USB or wireless debugging.
I write the Kotlin and the build files here; you build and run it, and paste back what the phone does.
That loop is slower than the PC side, so each step above is small enough to verify in one sitting.
