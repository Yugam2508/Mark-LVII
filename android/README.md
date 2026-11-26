# Jarvis for Android (step 1: the assistant skeleton)

An Android app that connects to your Jarvis PC over Tailscale, shows the holographic display, takes
typed or spoken requests, shows and reads the replies, and registers as the phone's **default
digital assistant** so long-press power opens it. Design and later steps: `../ANDROID.md`.

## What it does now
- Pairs with a PC (address + the key from **Remote Control**), and remembers the phone.
- Conversation screen: holo display, live log, type or tap **MIC** (Android's speech recogniser).
- Replies appear on the phone and are read aloud on the phone.
- Registers as an assistant: Settings → Apps → Default apps → **Digital assistant app** → Jarvis.
  Long-press power (or your assist gesture) then opens it over whatever you're doing and starts listening.

## What it does *not* do yet (so you aren't surprised)
- **No wake word** (step 2) — you invoke it by long-press power or by opening the app.
- **The PC still speaks the answer too**, because the request is handled by the Jarvis on the PC.
  Mute the PC's speakers, or say it's fine; step 5 (the hub) fixes this properly.
- No calls, texts, other-app control or IR yet (steps 3-4).
- The PC has to be on and running Jarvis (the hub removes that).

## Build and run (about 10 minutes)
1. Update Jarvis on the PC (**v1.8** adds the pairing endpoint this app uses).
2. Open Android Studio → **Open** → choose this `android` folder. Let Gradle sync; accept any SDK
   download prompts (Android 15 / API 35). If it offers to update the Android Gradle Plugin, accept.
3. On the OnePlus: Settings → About → tap **Build number** 7 times → Developer options → **USB
   debugging** (or **Wireless debugging**). Connect it and pick it in Android Studio's device list.
4. Press **Run ▶**. The app opens on the connect screen.
5. Tailscale **on** on the phone. On the PC press **Remote Control** in Jarvis. In the app type the PC's
   address (`100.x.x.x:8000`, the one under the QR code) and the 8-character key, or paste the whole
   QR link into the address box. **CONNECT**.
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
