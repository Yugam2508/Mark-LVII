"""gui/tray.py — JARVIS in the notification area, so it lives with the system rather than
in a window you have to keep open.

    * closing the window hides it to the tray; Jarvis keeps listening (⚙ setting to turn off)
    * click the icon to show or hide it; right-click for mute, stop talking, layout, quit
    * Ctrl+Alt+J from any window brings it to the front (core/summon.py)
    * "Quit" and the updater really exit

Where the system has no tray (some Linux desktops, offscreen tests), closing quits as before.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayIntegration(QObject):
    summoned = pyqtSignal()          # emitted from the hotkey thread → shown on the GUI thread
    hotkey = pyqtSignal(str)         # other global chords ("interrupt", "mute"), handled on the GUI thread

    def __init__(self, window, assistant_name: str = "JARVIS"):
        super().__init__(window)
        self.win = window
        self.really_quit = False
        self._told = False
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray = None
        self.summoned.connect(self.show_window)
        self.hotkey.connect(self._on_hotkey)
        if not self.available:
            return
        icon_path = Path(__file__).resolve().parent.parent / "config" / "jarvis.ico"
        icon = QIcon(str(icon_path)) if icon_path.exists() else window.windowIcon()
        self.tray = QSystemTrayIcon(icon, window)
        self.tray.setToolTip(f"{assistant_name} — Ctrl+Alt+J to open")
        menu = QMenu()
        self._add(menu, f"Show {assistant_name}", self.show_window)
        self._add(menu, "Mute / unmute microphone", window._toggle_mute)
        self._add(menu, "Stop talking", window._do_interrupt)
        if hasattr(window, "_toggle_wake_word"):
            self._add(menu, "Wake word on / off", window._toggle_wake_word)
        self._add(menu, "Immersive / panels", window._toggle_layout)
        menu.addSeparator()
        # One click for the things people ask most, without opening the window: they go to Jarvis as if typed.
        quick = menu.addMenu("Quick")
        for label, said in (("Run diagnostics", "run diagnostics"),
                            ("What are you working on?", "what are you working on?"),
                            ("Stop everything running", "stop everything that's running in the background"),
                            ("Take a screenshot", "take a screenshot"),
                            ("Back up Jarvis now", "back up Jarvis"),
                            ("What did I miss?", "what did I miss?")):
            self._add(quick, label, lambda s=said: self._say(s))
        menu.addSeparator()
        self._add(menu, "Quit", self.quit)
        self.tray.setContextMenu(menu)
        self._menu = menu
        self.tray.activated.connect(self._clicked)
        self.tray.messageClicked.connect(self.show_window)
        self.tray.show()
        QApplication.instance().setQuitOnLastWindowClosed(False)

    def _add(self, menu, text, fn):
        a = QAction(text, menu)
        a.triggered.connect(lambda _=False: fn())
        menu.addAction(a)

    def _on_hotkey(self, name: str) -> None:
        if name == "interrupt":
            self.win._do_interrupt()
        elif name == "mute":
            self.win._toggle_mute()

    def _say(self, text: str) -> None:
        fn = getattr(self.win, "on_text_command", None)
        if fn:
            import threading
            threading.Thread(target=fn, args=(text,), daemon=True).start()

    def notify_confirm(self, title: str) -> None:
        """A confirmation went up while the window is hidden: say so from the tray (click to open)."""
        if self.tray is None:
            return
        self.tray.showMessage("Jarvis needs your OK",
                              f"{title}. Say \"confirm\" or \"cancel\", or click here to see it.",
                              QSystemTrayIcon.MessageIcon.Warning, 12000)

    def _clicked(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.win.isVisible() and not self.win.isMinimized():
                self.win.hide()
            else:
                self.show_window()

    def show_window(self) -> None:
        w = self.win
        w.showNormal()
        w.raise_()
        w.activateWindow()

    def wants_hide_on_close(self) -> bool:
        if self.really_quit or not self.available or self.tray is None:
            return False
        try:
            from memory.config_manager import get_plugin_setting
            return bool(get_plugin_setting("conversation", "close_to_tray", True)
                        or get_plugin_setting("conversation", "hub_mode", False))
        except Exception:
            return True

    def hid(self) -> None:
        if not self._told and self.tray is not None:
            self._told = True
            self.tray.showMessage("JARVIS is still here",
                                  "It keeps listening in the background. Ctrl+Alt+J brings it back; "
                                  "right-click the icon to quit.",
                                  QSystemTrayIcon.MessageIcon.Information, 5000)

    def quit(self) -> None:
        self.really_quit = True
        self.win.close()
        QApplication.instance().quit()
