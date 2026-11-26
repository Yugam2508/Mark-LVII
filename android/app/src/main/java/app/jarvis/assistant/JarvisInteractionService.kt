package app.jarvis.assistant

import android.service.voice.VoiceInteractionService

/**
 * What makes Jarvis selectable as the phone's assistant
 * (Settings → Apps → Default apps → Digital assistant app).
 * Step 2 starts the always-on wake word from here.
 */
class JarvisInteractionService : VoiceInteractionService()
