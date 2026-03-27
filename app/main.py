#!/usr/bin/env python3
"""DeskMate — AI-powered desktop companion.

PySide6 + QWebEngineView edition.
Run: /usr/bin/python3 app/main.py
"""

import asyncio
import signal
import sys
from pathlib import Path

# Allow Ctrl+C to kill the app (Qt's event loop swallows SIGINT by default)
signal.signal(signal.SIGINT, signal.SIG_DFL)

from loguru import logger
from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from src.lib.commands import load_cached_commands, parse_commands_response, save_cached_commands
from src.lib.idle import IdleAnimationManager
from src.lib.parse import parse_buttons, parse_emotion, strip_all_tags
from src.lib.quake_terminal import QuakeTerminalManager
from src.lib.settings import AppStateManager, SettingsManager
from src.lib.skin import SkinLoader
from src.windows.bubble import BubbleWindow
from src.windows.chat_input import ChatInputWindow
from src.windows.ghost import GhostWindow
from src.windows.settings import SettingsWindow
from src.windows.skin_picker import SkinPickerWindow

APP_DIR = Path(__file__).resolve().parent
SKINS_DIR = APP_DIR / "skins"


class DeskMate:
    """Main orchestrator — coordinates all windows and the gateway client."""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("deskmate")
        self._app.setDesktopFileName("deskmate")  # Sets Wayland app_id
        self._app.setQuitOnLastWindowClosed(False)

        # Settings
        self._settings_mgr = SettingsManager()
        self._settings = self._settings_mgr.load()
        logger.info(f"Settings loaded from {self._settings_mgr._path}")

        # Transient state (window positions, etc.)
        self._state_mgr = AppStateManager()
        self._state = self._state_mgr.load()

        # Skin
        self._skin_loader = SkinLoader(SKINS_DIR)
        try:
            self._skin = self._skin_loader.load_skin(self._settings.current_skin_id)
        except FileNotFoundError:
            logger.warning(
                f"Skin '{self._settings.current_skin_id}' not found, falling back to 'default'"
            )
            self._skin = self._skin_loader.load_skin("default")
            self._settings.current_skin_id = "default"
        logger.info(f"Skin loaded: {self._skin.name} ({len(self._skin.emotions)} emotions)")

        # Windows
        self._ghost = GhostWindow()
        self._bubble = BubbleWindow()
        self._input = ChatInputWindow()
        self._settings_win = SettingsWindow()
        self._skin_picker = SkinPickerWindow(self._skin_loader)

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

        # Quake terminal
        self._quake = QuakeTerminalManager()
        self._quake.toggled.connect(self._on_quake_toggled)
        self._quake.toggle_requested.connect(self._toggle_quake_terminal)
        self._quake.setup_signal_handler()

        # Idle animation
        self._idle_manager = IdleAnimationManager(self._app)
        self._idle_manager.set_skin(self._skin)
        self._idle_manager.idle_override.connect(self._ghost.set_idle_override)
        self._idle_manager.idle_cleared.connect(self._ghost.clear_idle_override)

        # Gateway client (lazy — connected when settings have a URL)
        self._gateway = None
        self._gateway_task: asyncio.Task | None = None

        # Silent /commands fetch state
        self._silent_fetch_run_id: str | None = None
        self._command_response_buffer: str = ""

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
        self._ghost.clicked.connect(self._toggle_chat_input)
        self._ghost.position_changed.connect(self._on_ghost_moved)
        self._ghost.context_menu_requested.connect(self._show_ghost_context_menu)
        self._ghost.expression_changed.connect(lambda expr: logger.info(f"Expression: {expr}"))

        # Chat input signals
        self._input.message_sent.connect(self._on_chat_send)
        self._input.dismissed.connect(self._input.hide_input)

        # Bubble signals
        self._bubble.action.connect(self._on_bubble_action)

        # Settings signals
        self._settings_win.settings_saved.connect(self._on_settings_saved)

        # Skin picker signals
        self._skin_picker.skin_selected.connect(self._on_skin_selected)

    def _setup_shortcuts(self):
        # Enter/Return opens chat input (on ghost window)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self._ghost).activated.connect(
            self._toggle_chat_input
        )
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self._ghost).activated.connect(
            self._toggle_chat_input
        )

    def _build_context_menu(self) -> QMenu:
        menu = QMenu()
        menu.addAction("Show/Hide", self._toggle_ghost)
        menu.addAction("Toggle Terminal", self._toggle_quake_terminal)
        menu.addAction("Change Skin", self._show_skin_picker)
        menu.addAction("Settings", self._show_settings)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        return menu

    def _setup_tray(self):
        icon_path = APP_DIR / "icon.png"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = QIcon.fromTheme("application-default-icon")

        self._tray = QSystemTrayIcon(icon, self._app)
        self._tray.setContextMenu(self._build_context_menu())
        self._tray.setToolTip("DeskMate")
        self._tray.show()

    def _show_ghost_context_menu(self, pos: QPoint):
        menu = self._build_context_menu()
        menu.exec(pos)

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
        x = ghost_pos.x() + bounds["centerX"] - self._input.width() // 2
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

    def _toggle_chat_input(self):
        if self._input.isVisible():
            self._input.hide_input()
            return
        self._reposition_input()
        self._input.show_input(self._input.pos())
        self._input.set_connection_status("connected" if self._gateway else "disconnected")

    def _on_chat_send(self, text: str):
        self._input.hide_input()
        logger.info(f"User message: {text[:80]}")

        # User interaction — reset idle countdown
        self._idle_manager.reset()

        # Debug cheat codes — bypass gateway entirely
        cmd = text.strip().lower()
        if cmd == "ack":
            self._show_local_bubble("ACK")
            logger.info("Debug: ack")
            return
        if cmd == "emo":
            import random

            expressions = list(self._ghost._emotion_files.keys())
            expr = random.choice(expressions)
            self._ghost.set_expression(expr)
            self._show_local_bubble(f"emotion test → {expr}")
            logger.info(f"Debug: random expression -> {expr}")
            return
        if cmd == "md":
            self._debug_stream_markdown()
            return

        if not self._gateway:
            self._show_local_bubble(
                f"Not connected to gateway. Configure in settings.\n\nYou said: {text}"
            )
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
        asyncio.run_coroutine_threadsafe(self._send_chat(text), self._loop)

    async def _send_chat(self, text: str):
        from src.gateway.chat import ChatSession

        session = ChatSession(self._gateway)
        try:
            run_id = await session.send("main", text)
            logger.info(f"Chat sent, run_id={run_id}")
        except Exception as e:
            logger.error(f"Chat send failed: {e}")
            self._on_chat_error(str(e))

    def _on_chat_event(self, event):
        """Called from gateway event callback (may be from async thread)."""
        state = event.get("state", "")
        run_id = event.get("runId")
        message = event.get("message")

        # Intercept events from the silent /commands fetch — don't show in bubble
        if self._silent_fetch_run_id and run_id == self._silent_fetch_run_id:
            if state == "delta" and message:
                for block in message.get("content", []):
                    if block.get("type") == "text" and block.get("text"):
                        self._command_response_buffer += block["text"]
            elif state == "final":
                commands = parse_commands_response(self._command_response_buffer)
                if commands:
                    save_cached_commands(self._settings_mgr._config_dir, commands)
                    self._input.set_commands(commands)
                    logger.info(f"Slash commands fetched and cached ({len(commands)} commands)")
                self._silent_fetch_run_id = None
                self._command_response_buffer = ""
            elif state in ("error", "aborted"):
                logger.warning(f"Silent /commands fetch {state}")
                self._silent_fetch_run_id = None
                self._command_response_buffer = ""
            return

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

        # Restart idle countdown when chat returns to idle and bubble is not visible
        if self._chat_state == "idle" and not self._bubble.is_bubble_visible():
            self._idle_manager.start()

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

    def _debug_stream_markdown(self):
        """Stream sample markdown into the bubble, simulating gateway streaming."""
        sample = (
            "# Hello from Markdown!\n\n"
            "Here's some **bold**, *italic*, and `inline code`.\n\n"
            "## A code block\n\n"
            "```python\n"
            "def greet(name: str) -> str:\n"
            '    """Say hello with style."""\n'
            '    return f"Hello, {name}!"\n\n'
            "for i in range(3):\n"
            '    print(greet("World"))\n'
            "```\n\n"
            "## A list\n\n"
            "- First item\n"
            "- Second item with **emphasis**\n"
            "- Third item\n\n"
            "> This is a blockquote. It should look nice.\n\n"
            "| Header 1 | Header 2 |\n"
            "|----------|----------|\n"
            "| Cell A   | Cell B   |\n"
            "| Cell C   | Cell D   |\n\n"
            "And a [link](https://example.com) for good measure."
        )

        self._ghost.set_expression("thinking")
        self._bubble_counter += 1
        item_id = f"debug-md-{self._bubble_counter}"
        self._bubble.start_streaming(item_id, "")

        if not self._bubble.is_bubble_visible():
            self._reposition_bubble()
            self._bubble.show_bubble()

        # Stream ~10 chars at a time, ~30ms apart
        self._md_stream_pos = 0
        self._md_stream_sample = sample
        self._md_stream_id = item_id

        def _tick():
            self._md_stream_pos = min(self._md_stream_pos + 10, len(self._md_stream_sample))
            partial = self._md_stream_sample[: self._md_stream_pos]
            self._bubble.update_text(self._md_stream_id, partial)
            if self._md_stream_pos >= len(self._md_stream_sample):
                self._md_timer.stop()
                self._bubble.finalize(self._md_stream_id)
                self._ghost.set_expression("neutral")
                logger.info("Debug: md streaming complete")

        self._md_timer = QTimer()
        self._md_timer.setInterval(30)
        self._md_timer.timeout.connect(_tick)
        self._md_timer.start()
        logger.info("Debug: md streaming started")

    # ------------------------------------------------------------------
    # Bubble actions
    # ------------------------------------------------------------------

    def _on_bubble_action(self, action: str, item_id: str, message: str):
        if action == "dismiss":
            self._bubble.dismiss(item_id)
        elif action == "pin":
            self._bubble.pin(item_id)
        elif action == "button-click" and message:
            logger.info(f"Button clicked: {message}")
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
        logger.info(f"Gateway connecting to {self._settings.gateway_url}")

    def _fetch_slash_commands(self) -> None:
        """Check cache then silently send /commands to gateway if stale."""
        cached = load_cached_commands(self._settings_mgr._config_dir)
        if cached is not None:
            self._input.set_commands(cached)
            logger.info(f"Slash commands loaded from cache ({len(cached)} commands)")
            return

        if not self._gateway:
            return

        logger.info("Fetching slash commands from gateway")
        asyncio.run_coroutine_threadsafe(self._send_commands_fetch(), self._loop)

    async def _send_commands_fetch(self) -> None:
        from src.gateway.chat import ChatSession

        session = ChatSession(self._gateway)
        run_id = await session.send("main", "/commands")
        logger.debug(f"Silent /commands fetch run_id={run_id}")
        # Marshal back to Qt main thread to set the run_id
        QTimer.singleShot(0, lambda: setattr(self, "_silent_fetch_run_id", run_id))

    def _on_gateway_event(self, event):
        """Called from async thread — marshal to Qt main thread."""
        if event.event == "chat" and event.payload:
            payload = event.payload
            # Use QTimer.singleShot to marshal to main thread
            QTimer.singleShot(0, lambda: self._on_chat_event(payload))

    def _on_gateway_status(self, status: str):
        logger.info(f"Gateway status: {status}")
        QTimer.singleShot(0, lambda: self._input.set_connection_status(status))
        if status == "connected":
            QTimer.singleShot(0, self._fetch_slash_commands)

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

    def _toggle_quake_terminal(self):
        self._quake.toggle(self._settings.quake_terminal)

    def _on_quake_toggled(self, visible: bool):
        logger.info(f"Quake terminal {'shown' if visible else 'hidden'}")

    def _toggle_ghost(self):
        if self._ghost.isVisible():
            self._ghost.hide()
            self._bubble.hide_bubble()
            self._input.hide_input()
        else:
            self._ghost.show()

    def _show_skin_picker(self):
        skins = self._skin_loader.list_skins()
        self._skin_picker.show_picker(skins, self._settings.current_skin_id)
        # Position near ghost window
        ghost_pos = self._ghost.pos()
        ghost_w = self._ghost.width()
        picker_w = self._skin_picker.width()
        x = ghost_pos.x() + ghost_w // 2 - picker_w // 2
        y = ghost_pos.y() - self._skin_picker.height() - 10
        screen = self._app.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            x = max(sg.left(), min(x, sg.right() - picker_w))
            y = max(sg.top(), min(y, sg.bottom() - self._skin_picker.height()))
        self._skin_picker.move(x, y)

    def _on_skin_selected(self, skin_id: str):
        logger.info(f"Switching skin to: {skin_id}")
        try:
            new_skin = self._skin_loader.load_skin(skin_id)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load skin '{skin_id}': {e}")
            return
        self._skin = new_skin
        emotions_map = self._load_emotions_map(new_skin)
        self._ghost.set_skin(emotions_map, new_skin.path)
        self._settings.current_skin_id = skin_id
        try:
            self._settings_mgr.update(current_skin_id=skin_id)
        except Exception as e:
            logger.warning(f"Failed to save skin setting: {e}")
        logger.info(f"Skin switched to: {new_skin.name}")

    def _show_settings(self):
        available_skins = [d.name for d in SKINS_DIR.iterdir() if d.is_dir()]
        available_skins.sort()

        # Position near the ghost
        ghost_pos = self._ghost.pos()
        x = ghost_pos.x() - self._settings_win.width() - 10
        y = ghost_pos.y()
        # Keep on screen
        screen = self._app.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            if x < sg.left():
                x = ghost_pos.x() + self._ghost.width() + 10
            if y + self._settings_win.height() > sg.bottom():
                y = sg.bottom() - self._settings_win.height()
        self._settings_win.move(x, y)

        self._settings_win.show_settings(self._settings, available_skins)

    def _on_settings_saved(self, updated: dict) -> None:
        old_url = self._settings.gateway_url
        for key, value in updated.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        try:
            self._settings_mgr.update(**updated)
        except Exception as e:
            logger.warning(f"Failed to persist settings: {e}")

        # Apply ghost height immediately
        self._ghost.set_height(self._settings.ghost_height_pixels)

        # Reconnect gateway if URL changed
        if updated.get("gateway_url", old_url) != old_url:
            logger.info("Gateway URL changed — reconnecting")
            if self._gateway:
                self._gateway.stop()
                self._gateway = None
                self._gateway_task = None
            self._connect_gateway()

    def _quit(self):
        # Save ghost position
        x, y = self._ghost.save_position()
        logger.info(f"Saving ghost position: ({x}, {y})")
        try:
            self._state_mgr.update(ghost_x=x, ghost_y=y)
            logger.info("Ghost position saved to state.yaml")
        except Exception as e:
            logger.warning(f"Failed to save position: {e}")

        if self._gateway:
            self._loop.run_until_complete(self._gateway.stop())

        self._quake.cleanup()
        self._async_timer.stop()
        self._app.quit()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _is_position_visible(self, x: float, y: float) -> bool:
        """Check if (x, y) is within any connected screen's geometry."""
        for screen in self._app.screens():
            geom = screen.availableGeometry()
            # Consider visible if the point is within the screen bounds (with some margin)
            if (
                geom.left() - 100 <= x <= geom.right() + 100
                and geom.top() - 100 <= y <= geom.bottom() + 100
            ):
                logger.info(f"Position ({x}, {y}) is on screen {screen.name()} ({geom})")
                return True
        screens = [(s.name(), s.availableGeometry()) for s in self._app.screens()]
        logger.warning(f"Position ({x}, {y}) is off-screen. Available screens: {screens}")
        return False

    def _default_ghost_position(self):
        """Move ghost to default position (bottom-right of primary screen)."""
        screen = self._app.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            x = sg.right() - self._ghost.width() - 50
            y = sg.center().y() - self._ghost.height() // 2
            logger.info(f"Using default ghost position: ({x}, {y}) on {screen.name()}")
            self._ghost.restore_position(float(x), float(y))

    def _restore_ghost_position(self):
        """Restore ghost position after the window is visible (needed for swaymsg)."""
        x, y = self._state.ghost_x, self._state.ghost_y
        logger.info(f"Restoring ghost position: saved=({x}, {y})")
        if (x or y) and self._is_position_visible(x, y):
            self._ghost.restore_position(x, y)
            logger.info(f"Ghost position restored to ({x}, {y})")
        else:
            logger.info("Saved position unusable, falling back to default")
            self._default_ghost_position()

    def run(self) -> int:
        self._ghost.show()

        # Restore position after show — swaymsg needs the window to be visible first
        QTimer.singleShot(100, self._restore_ghost_position)

        # Start idle animation cycle
        self._idle_manager.start()

        logger.info("=" * 50)
        logger.info("DeskMate (PySide6) started")
        logger.info(f"Skin: {self._skin.name} | Expressions: {self._skin.emotions}")
        logger.info(f"Gateway: {self._settings.gateway_url or '(not configured)'}")
        logger.info("Click character or press Enter to chat")
        logger.info("=" * 50)

        # Start async integration
        self._start_async_loop()

        return self._app.exec()


def main():
    sys.exit(DeskMate().run())


if __name__ == "__main__":
    main()
