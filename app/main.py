#!/usr/bin/env python3
"""DeskMate — AI-powered desktop companion.

PySide6 + QWebEngineView edition.
Run: /usr/bin/python3 app/main.py
"""

import asyncio
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon

from src.lib.settings import SettingsManager
from src.lib.skin import SkinLoader
from src.lib.parse import parse_emotion, parse_buttons, strip_all_tags
from src.windows.ghost import GhostWindow
from src.windows.bubble import BubbleWindow
from src.windows.chat_input import ChatInputWindow

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s.%(msecs)03d] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("deskmate")

APP_DIR = Path(__file__).resolve().parent
SKINS_DIR = APP_DIR / "skins"


class DeskMate:
    """Main orchestrator — coordinates all windows and the gateway client."""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("deskmate")
        self._app.setQuitOnLastWindowClosed(False)

        # Settings
        self._settings_mgr = SettingsManager()
        self._settings = self._settings_mgr.load()
        logger.info("Settings loaded from %s", self._settings_mgr._path)

        # Skin
        self._skin_loader = SkinLoader(SKINS_DIR)
        try:
            self._skin = self._skin_loader.load_skin(self._settings.current_skin_id)
        except FileNotFoundError:
            logger.warning("Skin '%s' not found, falling back to 'default'", self._settings.current_skin_id)
            self._skin = self._skin_loader.load_skin("default")
            self._settings.current_skin_id = "default"
        logger.info("Skin loaded: %s (%d emotions)", self._skin.name, len(self._skin.emotions))

        # Windows
        self._ghost = GhostWindow()
        self._bubble = BubbleWindow()
        self._input = ChatInputWindow()

        # Load skin into ghost — need the emotion->files mapping from manifest
        emotions_map = self._load_emotions_map(self._skin)
        self._ghost.set_skin(emotions_map, self._skin.path)
        self._ghost.set_height(self._settings.ghost_height_pixels)

        # Chat state
        self._chat_state = "idle"  # idle | sending | streaming
        self._current_response = ""
        self._current_emotion = "neutral"
        self._active_bubble_id: str | None = None
        self._bubble_counter = 0

        # Gateway client (lazy — connected when settings have a URL)
        self._gateway = None
        self._gateway_task: asyncio.Task | None = None

        # Async integration: use QTimer to pump asyncio
        self._loop = asyncio.new_event_loop()
        self._async_timer = QTimer()
        self._async_timer.setInterval(16)  # ~60fps
        self._async_timer.timeout.connect(self._pump_asyncio)

        self._setup_connections()
        self._setup_shortcuts()
        self._setup_tray()

    def _load_emotions_map(self, skin: object) -> dict[str, list[str]]:
        """Read the manifest to get the emotion -> [files] mapping."""
        import yaml
        manifest_path = skin.path / "manifest.yaml"
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
        emotions_raw = data.get("emotions", {})
        # Normalize: ensure values are lists
        result = {}
        for emotion, files in emotions_raw.items():
            if isinstance(files, str):
                result[emotion] = [files]
            elif isinstance(files, list):
                result[emotion] = [str(f) for f in files]
            else:
                result[emotion] = [str(files)]
        return result

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _setup_connections(self):
        # Ghost signals
        self._ghost.clicked.connect(self._show_chat_input)
        self._ghost.position_changed.connect(self._on_ghost_moved)
        self._ghost.expression_changed.connect(
            lambda expr: logger.info("Expression: %s", expr)
        )

        # Chat input signals
        self._input.message_sent.connect(self._on_chat_send)
        self._input.dismissed.connect(self._input.hide_input)

        # Bubble signals
        self._bubble.action.connect(self._on_bubble_action)

    def _setup_shortcuts(self):
        # Enter/Return opens chat input (on ghost window)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self._ghost).activated.connect(
            self._show_chat_input
        )
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self._ghost).activated.connect(
            self._show_chat_input
        )

    def _setup_tray(self):
        icon_path = APP_DIR / "icon.png"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = QIcon.fromTheme("application-default-icon")

        self._tray = QSystemTrayIcon(icon, self._app)

        menu = QMenu()
        menu.addAction("Show/Hide", self._toggle_ghost)
        menu.addAction("Settings", self._show_settings)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)

        self._tray.setContextMenu(menu)
        self._tray.setToolTip("DeskMate")
        self._tray.show()

    # ------------------------------------------------------------------
    # Window positioning
    # ------------------------------------------------------------------

    def _reposition_bubble(self):
        ghost_pos = self._ghost.pos()
        ghost_size = QSize(self._ghost.width(), self._ghost.height())
        placement = None
        if self._skin and self._skin.bubble_placement:
            bp = self._skin.bubble_placement
            placement = {"x": bp.x, "y": bp.y, "origin": bp.origin}
        self._bubble.reposition(ghost_pos, ghost_size, placement)

    def _reposition_input(self):
        ghost_pos = self._ghost.pos()
        bounds = self._ghost.image_bounds()

        # Position below the ghost
        x = ghost_pos.x() + bounds["center_x"] - self._input.width() // 2
        y = ghost_pos.y() + bounds["bottom"] + 10

        self._input.move(x, y)

    def _on_ghost_moved(self, pos: QPoint):
        if self._bubble.is_bubble_visible():
            self._reposition_bubble()
        if self._input.isVisible():
            self._reposition_input()

    # ------------------------------------------------------------------
    # Chat flow
    # ------------------------------------------------------------------

    def _show_chat_input(self):
        self._reposition_input()
        self._input.show_input(self._input.pos())
        self._input.set_connection_status(
            "connected" if self._gateway else "disconnected"
        )

    def _on_chat_send(self, text: str):
        self._input.hide_input()
        logger.info("User message: %s", text[:80])

        if not self._gateway:
            self._show_local_bubble(f"Not connected to gateway. Configure in settings.\n\nYou said: {text}")
            return

        self._chat_state = "sending"
        self._current_response = ""

        # Start streaming bubble
        self._bubble_counter += 1
        self._active_bubble_id = f"msg-{self._bubble_counter}"
        self._bubble.start_streaming(self._active_bubble_id, "")

        if not self._bubble.is_bubble_visible():
            self._reposition_bubble()
            self._bubble.show_bubble()

        # Send via gateway
        asyncio.run_coroutine_threadsafe(
            self._send_chat(text), self._loop
        )

    async def _send_chat(self, text: str):
        from src.gateway.chat import ChatSession
        session = ChatSession(self._gateway)
        try:
            run_id = await session.send("main", text)
            logger.info("Chat sent, run_id=%s", run_id)
        except Exception as e:
            logger.error("Chat send failed: %s", e)
            self._on_chat_error(str(e))

    def _on_chat_event(self, event):
        """Called from gateway event callback (may be from async thread)."""
        state = event.get("state", "")
        message = event.get("message")

        if state == "delta" and message:
            content_blocks = message.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text" and block.get("text"):
                    self._current_response += block["text"]

            self._chat_state = "streaming"

            # Parse emotion from accumulated text
            emotion = parse_emotion(self._current_response)
            if emotion != self._current_emotion:
                self._current_emotion = emotion
                self._ghost.set_expression(emotion)

            # Update bubble with stripped text
            display_text = strip_all_tags(self._current_response)
            if self._active_bubble_id:
                self._bubble.update_text(self._active_bubble_id, display_text)

        elif state == "final":
            self._chat_state = "idle"
            display_text = strip_all_tags(self._current_response)

            if self._active_bubble_id:
                self._bubble.update_text(self._active_bubble_id, display_text)
                self._bubble.finalize(self._active_bubble_id)

                # Extract buttons
                buttons = parse_buttons(self._current_response)
                if buttons:
                    self._bubble.set_buttons(self._active_bubble_id, buttons)

            self._active_bubble_id = None
            self._current_response = ""

        elif state == "error":
            error_msg = event.get("error_message", "Unknown error")
            self._on_chat_error(error_msg)

        elif state == "aborted":
            self._chat_state = "idle"
            if self._active_bubble_id:
                self._bubble.finalize(self._active_bubble_id)
            self._active_bubble_id = None

    def _on_chat_error(self, error: str):
        self._chat_state = "idle"
        if self._active_bubble_id:
            self._bubble.update_text(self._active_bubble_id, f"Error: {error}")
            self._bubble.finalize(self._active_bubble_id)
        self._active_bubble_id = None

    def _show_local_bubble(self, text: str):
        """Show a local message (not from gateway)."""
        self._bubble_counter += 1
        item_id = f"local-{self._bubble_counter}"
        self._bubble.start_streaming(item_id, text)
        self._bubble.finalize(item_id)

        if not self._bubble.is_bubble_visible():
            self._reposition_bubble()
            self._bubble.show_bubble()

    # ------------------------------------------------------------------
    # Bubble actions
    # ------------------------------------------------------------------

    def _on_bubble_action(self, action: str, item_id: str, message: str):
        if action == "dismiss":
            self._bubble.dismiss(item_id)
        elif action == "pin":
            self._bubble.pin(item_id)
        elif action == "button-click" and message:
            logger.info("Button clicked: %s", message)
            self._on_chat_send(message)

    # ------------------------------------------------------------------
    # Gateway connection
    # ------------------------------------------------------------------

    def _connect_gateway(self):
        if not self._settings.gateway_url:
            logger.info("No gateway URL configured")
            return

        from src.gateway.client import GatewayClient

        self._gateway = GatewayClient()
        self._gateway.on_event = self._on_gateway_event
        self._gateway.on_status_change = self._on_gateway_status

        self._gateway_task = asyncio.run_coroutine_threadsafe(
            self._gateway.start(
                self._settings.gateway_url,
                self._settings.gateway_token or None,
                self._settings_mgr._config_dir,
            ),
            self._loop,
        )
        logger.info("Gateway connecting to %s", self._settings.gateway_url)

    def _on_gateway_event(self, event):
        """Called from async thread — marshal to Qt main thread."""
        if event.event == "chat" and event.payload:
            # Use QTimer.singleShot to marshal to main thread
            QTimer.singleShot(0, lambda: self._on_chat_event(event.payload))

    def _on_gateway_status(self, status: str):
        logger.info("Gateway status: %s", status)
        QTimer.singleShot(0, lambda: self._input.set_connection_status(status))

    # ------------------------------------------------------------------
    # Asyncio integration
    # ------------------------------------------------------------------

    def _pump_asyncio(self):
        """Run pending asyncio callbacks without blocking Qt."""
        self._loop.call_soon(self._loop.stop)
        self._loop.run_forever()

    def _start_async_loop(self):
        """Start the asyncio pump and connect to gateway if configured."""
        self._async_timer.start()
        if self._settings.gateway_url:
            self._connect_gateway()

    # ------------------------------------------------------------------
    # Misc actions
    # ------------------------------------------------------------------

    def _toggle_ghost(self):
        if self._ghost.isVisible():
            self._ghost.hide()
            self._bubble.hide_bubble()
            self._input.hide_input()
        else:
            self._ghost.show()

    def _show_settings(self):
        # TODO: Settings window
        logger.info("Settings window not yet implemented")

    def _quit(self):
        # Save ghost position
        x, y = self._ghost.save_position()
        self._settings.ghost_x = x
        self._settings.ghost_y = y
        try:
            self._settings_mgr.update(ghost_x=x, ghost_y=y)
        except Exception as e:
            logger.warning("Failed to save position: %s", e)

        if self._gateway:
            self._gateway.stop()

        self._async_timer.stop()
        self._app.quit()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> int:
        # Restore ghost position
        if self._settings.ghost_x or self._settings.ghost_y:
            self._ghost.restore_position(self._settings.ghost_x, self._settings.ghost_y)
        else:
            screen = self._app.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                self._ghost.move(
                    sg.right() - self._ghost.width() - 50,
                    sg.center().y() - self._ghost.height() // 2,
                )

        self._ghost.show()

        logger.info("=" * 50)
        logger.info("DeskMate (PySide6) started")
        logger.info("Skin: %s | Expressions: %s", self._skin.name, self._skin.emotions)
        logger.info("Gateway: %s", self._settings.gateway_url or "(not configured)")
        logger.info("Click character or press Enter to chat")
        logger.info("=" * 50)

        # Start async integration
        self._start_async_loop()

        return self._app.exec()


def main():
    sys.exit(DeskMate().run())


if __name__ == "__main__":
    main()
