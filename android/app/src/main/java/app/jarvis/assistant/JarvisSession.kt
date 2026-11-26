package app.jarvis.assistant

import android.content.Context
import android.os.Bundle
import android.view.View
import android.service.voice.VoiceInteractionSession

/** The overlay that appears over whatever you are doing when you invoke the assistant. */
class JarvisSession(context: Context) : VoiceInteractionSession(context) {
    private var panel: ConversationPanel? = null

    override fun onCreateContentView(): View {
        val p = ConversationPanel(context, listenOnShow = true)
        panel = p
        return p
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        panel?.startListening()
    }

    override fun onHide() {
        panel?.stopAll()
        super.onHide()
    }
}
