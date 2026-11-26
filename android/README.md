# Jarvis for Android

An Android app that connects to your Jarvis PC over Tailscale, shows the holographic display, takes
typed or spoken requests, shows and reads the replies, and registers as the phone's **default
digital assistant** so long-press power opens it. Design and later steps: `../ANDROID.md`.

## The phone is Jarvis's microphone and speaker
One Jarvis, not two. While the app is paired and listening:
- **Your microphone is open all the time** (no button), using the phone's own echo cancellation, so you
  can talk over Jarvis just as on the PC. A quiet "Jarvis is listening" notification (with a Stop button)
  keeps it going when the app is closed or the screen is off.
- **Jarvis's voice plays on the phone**: the same voice and accent as the PC, because it is the PC's
  Jarvis (same brain, memory, personality and tools). The PC mutes its own speakers and microphone while
  the phone is doing this, so only one device answers.
- **What Jarvis shows on the PC** (calendar, weather, results, alerts) also appears in the phone's log.
- **"Hey Jarvis"**: with the wake word on (the default), nothing you say reaches Jarvis until the PC hears
  "Hey Jarvis" in it — then a chime and a buzz, and the conversation flows until it's quiet for a while.
  Tap the orb to talk without the phrase, tap it while Jarvis speaks to cut it off, long-press to send it
  back to waiting. The line under the orb always says what it's doing.
- **Only speech is sent** (with a moment either side), so listening all day costs little mobile data.
- **⋮ (top right) → Permissions & setup** is where every switch lives (phones have no menu key): a tick or a
  cross for each permission with one tap to fix it, *Always listening*, *Wake word*, *Chime*, *Save mobile
  data*, *Talk over Jarvis*, and *Forget this PC*. If Jarvis seems to hear itself, turn *Talk over Jarvis* off.
- The listening notification has **Mute** and **Stop listening**; tap it to open the app. Add the **Jarvis
  tile** to Quick Settings (pull down twice → edit) to switch listening on and off from anywhere.
- Android only lets a listening service start while the app is open: after a phone restart the link
  comes back by itself, but open the app once to start listening again.

## What it does now
- Pairs with a PC (address + the key from **Remote Control**), and remembers the phone.
- Conversation screen: the living orb, the conversation (long-press to copy it), a box to type in, and a
  bar with **CONFIRM / CANCEL** when something you asked for needs your OK (also as a lock-screen notification).
- **Share → Jarvis (to my PC)** from any app: text goes on the PC clipboard, links open on the PC.
- Replies are Jarvis's own voice, played on the phone (see above), and shown as text.
- Registers as an assistant: Settings → Apps → Default apps → **Digital assistant app** → Jarvis.
  Long-press power (or your assist gesture) then opens it over whatever you're doing and starts listening.

## The phone as a limb (PC → phone)
Once paired, a small notification "Jarvis is linked to your PC" keeps the link alive (it restarts
after a reboot). Then you can say to Jarvis **on the PC**: "call Mum", "text Aarav that I'm running
late", "find my phone", "what's my phone's battery?". The PC asks you to confirm every call and text
(say "confirm"). The first time, the app asks for Contacts, Phone, SMS and Notifications permissions:
allow them, or those actions say they lack permission.

## So the app never asks for the address
Put your PC's Tailscale address in a one-line file and rebuild; the app then connects by itself the
first time it opens (no typing, and no key when the phone is on the same Tailscale account). The file
is git-ignored, so your address stays out of the public repository. In PowerShell (adjust the folder if
yours differs):

    New-Item -ItemType Directory -Force "$env:USERPROFILE\Jarvis\android\app\src\main\assets" | Out-Null
    Set-Content -NoNewline "$env:USERPROFILE\Jarvis\android\app\src\main\assets\default_address.txt" "100.89.195.89:8000"

Then **Run ▶** in Android Studio again. (Use your PC's name from the Tailscale app, e.g.
`yugam.tail4e090e.ts.net:8000`, if you'd rather not depend on the number.)

## Staying connected
The PC remembers paired phones across restarts, and the app reconnects by itself with backoff. It
keeps the link while the PC is on, awake and running Jarvis (Jarvis keeps a mains-powered PC awake
while a phone is connected). If the app says "The PC no longer knows this phone", press Remote
Control on the PC and enter the new key: the address is kept.

## More it can do (asked on the PC or through the phone)
Read and reply to WhatsApp/Telegram/Messages notifications, read your texts and call log, announce a ringing
call ("answer it" / "decline it"), open apps and links, Bluetooth/Wi-Fi pages, volume, flashlight, timers and
alarms, media keys, navigation, where the phone is, Do Not Disturb, and — with the optional accessibility
switch — press WhatsApp's Send, take a screenshot, lock the phone. Each needs the matching line in
⋮ → Permissions & setup to show ✓.

## What it does *not* do yet (so you aren't surprised)
- The AC through the IR blaster (needs the AC's make and model), and controlling other apps beyond the above.
- The PC has to be on and running Jarvis (hub mode keeps it that way).

## Build and run (about 10 minutes)
1. Update Jarvis on the PC (**v1.8** adds the pairing endpoint this app uses).
2. Open Android Studio → **Open** → choose this `android` folder (it includes the Gradle wrapper, which
   downloads Gradle 8.9 on first sync). Let Gradle sync; accept any SDK
   download prompts (Android 15 / API 35). If it offers to update the Android Gradle Plugin, accept.
3. On the OnePlus: Settings → About → tap **Build number** 7 times → Developer options → **USB
   debugging** (or **Wireless debugging**). Connect it and pick it in Android Studio's device list.
4. Press **Run ▶**. The app opens on the connect screen.
5. Tailscale **on** on the phone. In the app type the PC's Tailscale address (`100.x.x.x:8000`) and press
   **CONNECT**. No key is needed when the phone is on the same Tailscale account as the PC. If the PC
   asks for one (another account, or that setting is off), press **Remote Control** in Jarvis and type
   the 8-character key shown there, or paste the whole QR link into the address box.
6. Say or type "what time is it". Check the log fills in and the phone speaks.
7. Make it the assistant: Settings → Apps → Default apps → **Digital assistant app** → **Jarvis** (the
   app's menu key also opens a shortcut to this). Allow the microphone when asked. Then long-press power.

## If something doesn't work
Paste me what you see. Useful: the red lines in Android Studio's **Build** and **Logcat** (filter
`app.jarvis`) tabs, and what the PC log says after pressing CONNECT. Likely first-run snags: a Gradle/AGP
version nudge (accept the update), Jarvis not listed as an assistant (the phone needs
`BIND_VOICE_INTERACTION` services to be installed and the app opened once), and the microphone permission.

## Checked without a phone
The Kotlin compiles against the real Android 15 framework and `ProtocolTest` (address and message
parsing) passes on a plain JVM. The Gradle build, the screens and the assistant registration have
**not** been run: that needs Android Studio and your phone.
