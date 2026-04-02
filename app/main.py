#!/usr/bin/env python3
"""DeskMate — AI-powered desktop companion.

PySide6 + QWebEngineView edition.
Run: /usr/bin/python3 app/main.py
"""

import asyncio
import ctypes
import ctypes.util
import os
import random
import signal
import sys
import threading
from pathlib import Path

import setproctitle
import yaml
from loguru import logger

# Log to file so we can see what happened after a DE crash
# logger.add(Path.home() / "deskmate.log", rotation="1 MB", retention=3)

# PySide6 ships its own Qt plugins which may lack the system IME plugin (e.g.
# fcitx5).  Prepend the system Qt6 plugin path so the compositor's input method
# is available.  Must happen before QApplication is created.
_SYS_QT6_PLUGINS = Path("/usr/lib/qt6/plugins")
if _SYS_QT6_PLUGINS.is_dir():
    existing = os.environ.get("QT_PLUGIN_PATH", "")
    os.environ["QT_PLUGIN_PATH"] = str(_SYS_QT6_PLUGINS) + (f":{existing}" if existing else "")
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from src.gateway.chat import ChatSession
from src.gateway.client import GatewayClient
from src.lib.commands import load_cached_commands, parse_commands_response, save_cached_commands
from src.lib.compositor import compositor
from src.lib.idle import IdleAnimationManager
from src.lib.parse import parse_buttons, parse_emotion, strip_all_tags
from src.lib.quake_terminal import QuakeTerminalManager
from src.lib.settings import AppStateManager, SettingsManager
from src.lib.skin import SkinLoader, UiPlacement
from src.lib.window_position import ScreenMargins, ScreenRect, calc_anchor, calc_window_position
from src.windows.bubble import BubbleWindow
from src.windows.chat_input import ChatInputWindow
from src.windows.get_skins import GetSkinsWindow
from src.windows.ghost import GhostWindow
from src.windows.settings import SettingsWindow
from src.windows.skin_picker import SkinPickerWindow

# Allow Ctrl+C to kill the app (Qt's event loop swallows SIGINT by default)
signal.signal(signal.SIGINT, signal.SIG_DFL)


APP_DIR = Path(__file__).resolve().parent
SKINS_DIR = APP_DIR / "skins"


class DeskMate:
    """Main orchestrator — coordinates all windows and the gateway client."""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("deskmate")
        self._app.setDesktopFileName("deskmate")  # Sets Wayland app_id
        self._app.setQuitOnLastWindowClosed(False)
        self._app.aboutToQuit.connect(self._cleanup)

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
        self._get_skins_win = GetSkinsWindow(self._skin_loader)

        # Load skin into ghost — need the emotion->files mapping from manifest
        emotions_map = self._load_emotions_map(self._skin)
        self._ghost.set_skin(emotions_map, self._skin.path)
        self._apply_ghost_size()

        # Chat state
        self._chat_state = "idle"  # idle | sending | streaming
        self._current_response = ""
        self._current_emotion = "neutral"
        self._active_bubble_id: str | None = None
        self._bubble_counter = 0
        self._bubble_visible_before_hide = False

        # Quake terminal
        self._quake = QuakeTerminalManager()
        self._quake.toggled.connect(self._on_quake_toggled)
        self._quake.toggle_requested.connect(self._toggle_quake_terminal)
        self._quake.setup_signal_handler()

        # SIGUSR2 → toggle ghost visibility
        if hasattr(signal, "SIGUSR2"):
            self._sigusr2_event = threading.Event()
            signal.signal(signal.SIGUSR2, lambda *_: self._sigusr2_event.set())
            self._sigusr2_timer = QTimer()
            self._sigusr2_timer.setInterval(100)
            self._sigusr2_timer.timeout.connect(self._check_sigusr2)
            self._sigusr2_timer.start()
            logger.info("SIGUSR2 handler registered (pkill -USR2 -x python3 to toggle ghost)")

        # Idle animation
        self._idle_manager = IdleAnimationManager(self._app)
        self._idle_manager.set_skin(self._skin)
        self._idle_manager.set_interval(self._settings.idle_interval_seconds)
        self._idle_manager.idle_override.connect(self._ghost.set_idle_override)
        self._idle_manager.idle_cleared.connect(self._ghost.clear_idle_override)

        # Gateway client (lazy — connected when settings have a URL)
        self._gateway = None
        self._gateway_task: asyncio.Task | None = None

        # Silent /commands fetch state
        self._silent_fetch_run_id: str | None = None
        self._command_response_buffer: str = ""
        self._slash_commands_fetch_in_flight = False

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
        self._ghost.window_mapped.connect(self._restore_ghost_position)
        self._ghost.context_menu_requested.connect(self._show_ghost_context_menu)
        self._ghost.dismiss_requested.connect(self._bubble._dismiss_oldest)
        self._ghost.pin_requested.connect(self._bubble._pin_newest)
        self._ghost.expression_changed.connect(lambda expr: logger.info(f"Expression: {expr}"))
        self._ghost.terminal_toggle_requested.connect(self._toggle_quake_terminal)

        # Chat input signals
        self._input.message_sent.connect(self._on_chat_send)
        self._input.dismissed.connect(self._input.hide_input)
        self._input.terminal_toggle_requested.connect(self._toggle_quake_terminal)
        self._input.window_mapped.connect(self._reposition_input)

        # Bubble signals
        self._bubble.action.connect(self._on_bubble_action)
        self._bubble.all_dismissed.connect(lambda: self._ghost.set_expression("neutral"))
        self._bubble.content_sized.connect(lambda _h: self._reposition_bubble())
        self._bubble.window_mapped.connect(self._reposition_bubble)

        # Settings signals
        self._settings_win.settings_saved.connect(self._on_settings_saved)

        # Skin picker signals
        self._skin_picker.skin_selected.connect(self._on_skin_selected)
        self._get_skins_win.skin_installed.connect(self._on_skin_installed)

    def _setup_shortcuts(self):
        # Enter/Return opens chat input (on ghost or bubble window)
        for window in (self._ghost, self._bubble):
            QShortcut(QKeySequence(Qt.Key.Key_Return), window).activated.connect(
                self._toggle_chat_input
            )
            QShortcut(QKeySequence(Qt.Key.Key_Enter), window).activated.connect(
                self._toggle_chat_input
            )

        # Copy bubble content from ghost or bubble focus
        for window in (self._ghost, self._bubble):
            QShortcut(QKeySequence(Qt.Key.Key_C), window).activated.connect(
                self._bubble.copy_last_clicked_or_newest
            )
            QShortcut(QKeySequence("Shift+C"), window).activated.connect(
                self._bubble.copy_last_clicked_or_newest
            )
            QShortcut(QKeySequence("Ctrl+C"), window).activated.connect(
                self._bubble.copy_selection_or_last_clicked
            )

        # Ctrl+Q to quit (on ghost or bubble)
        for window in (self._ghost, self._bubble):
            QShortcut(QKeySequence("Ctrl+Q"), window).activated.connect(self._quit)

    def _build_context_menu(self) -> QMenu:
        menu = QMenu()
        menu.addAction("Show/Hide", self._toggle_ghost)
        menu.addAction("Toggle Terminal", self._toggle_quake_terminal)
        menu.addAction("Change Skin", self._show_skin_picker)
        menu.addAction("Get Skins", self._show_get_skins)
        menu.addAction("Settings", self._show_settings)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        return menu

    def _setup_tray(self):
        icon_path = APP_DIR / "icons" / "icon.png"
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

    def _apply_ghost_size(self):
        if self._settings.ghost_width_pixels is not None:
            self._ghost.set_width(self._settings.ghost_width_pixels)
        else:
            self._ghost.set_height(self._settings.ghost_height_pixels)

    def _ghost_screen_rect(self) -> ScreenRect:
        """Return the screen geometry containing the ghost (global coords)."""
        gx, gy = self._ghost_screen_pos()
        comp_screen = compositor().get_screen_at(gx, gy)
        if comp_screen:
            return ScreenRect(*comp_screen)
        screen = self._app.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            return ScreenRect(sg.x(), sg.y(), sg.width(), sg.height())
        return ScreenRect(0, 0, 1920, 1080)

    def _ghost_screen_pos(self) -> tuple[int, int]:
        """Get ghost's real screen position (compositor-aware)."""
        comp_pos = compositor().get_window_position("deskmate-ghost")
        if comp_pos:
            return int(comp_pos[0]), int(comp_pos[1])
        pos = self._ghost.pos()
        return pos.x(), pos.y()

    def _move_window(self, window, x: int, y: int) -> None:
        """Move window using compositor IPC if available, else QWidget.move()."""
        title = window.windowTitle()
        if title and compositor().set_window_position(title, x, y):
            return
        window.move(x, y)

    def _popup_margins(self) -> ScreenMargins:
        s = self._settings
        return ScreenMargins(
            top=int(s.popup_margin_top),
            bottom=int(s.popup_margin_bottom),
            left=int(s.popup_margin_left),
            right=int(s.popup_margin_right),
        )

    def _position_window(self, window, placement):
        """Position *window* relative to ghost using shared anchor + clamping."""
        gx, gy = self._ghost_screen_pos()
        bounds = self._ghost.image_bounds()
        ax, ay = calc_anchor(
            gx,
            gy,
            bounds,
            placement.x,
            placement.y,
        )
        sr = self._ghost_screen_rect()
        pos = calc_window_position(
            ax,
            ay,
            window.width(),
            window.height(),
            placement.origin,
            screen=sr,
            margins=self._popup_margins(),
        )
        self._move_window(window, pos.screen_x, pos.screen_y)
        return pos

    def _reposition_bubble(self):
        if self._skin and self._skin.bubble_placement:
            p = self._skin.bubble_placement
        else:
            p = UiPlacement(x=20, y=-self._bubble.height() + 60, origin="bottom-left")
        pos = self._position_window(self._bubble, p)
        # Set max height to available space from bubble top to screen bottom
        sr = self._ghost_screen_rect()
        available = (sr.y + sr.height) - pos.screen_y
        self._bubble.set_max_height(max(available, 100))

    def _reposition_input(self):
        if self._skin and self._skin.input_placement:
            self._position_window(self._input, self._skin.input_placement)
            return
        # Default: centered below the sprite's bottom edge with a small gap.
        gx, gy = self._ghost_screen_pos()
        bounds = self._ghost.image_bounds()
        ax = gx + bounds["centerX"]
        ay = gy + bounds["bottom"] + 10
        sr = self._ghost_screen_rect()
        pos = calc_window_position(
            ax,
            ay,
            self._input.width(),
            self._input.height(),
            "center",
            screen=sr,
            margins=self._popup_margins(),
        )
        self._move_window(self._input, pos.screen_x, pos.screen_y)

    def _on_ghost_moved(self, pos: QPoint):
        x, y = self._ghost.save_position()
        self._state.ghost_x, self._state.ghost_y = x, y
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
        self._input.show_input(self._input.pos())
        # Reposition happens via window_mapped signal (deferred until compositor maps the window)
        self._input.set_connection_status("connected" if self._gateway else "disconnected")

    def _on_chat_send(self, text: str):
        self._input.hide_input()
        logger.info(f"User message: {text[:80]}")

        # User interaction — reset idle countdown
        self._idle_manager.reset()

        # Debug cheat codes — bypass gateway entirely
        cmd = text.strip().lower()
        if cmd == "ack":
            self._debug_stream_text("ACK", label="ack")
            return
        if cmd == "emo":
            non_neutral = [e for e in self._ghost._emotion_files if e != "neutral"]
            expr = random.choice(non_neutral) if non_neutral else "neutral"
            self._debug_stream_text(f"emotion test [emotion:{expr}]", label="emo")
            return
        if cmd == "md":
            self._debug_stream_text(
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
                "And a [link](https://example.com) for good measure.",
                label="md",
            )
            return
        if cmd == "link":
            self._debug_stream_text(
                "Here are some links:\n\n"
                "Autolink: <https://example.com/path?q=hello&lang=en>\n\n"
                "Bare URL: https://example.com/path?q=hello&lang=en\n\n"
                "Markdown: [Click here](https://example.com)\n\n"
                "Mixed: check <https://example.org> and https://example.net too",
                label="link",
            )
            return
        if cmd == "btn":
            self._debug_stream_text(
                "Here are some actions you can take: [btn:Hi][btn:Thanks][btn:Tell me more]",
                label="btn",
            )
            return
        if cmd == "long":
            self._debug_stream_text(
                "This is a deliberately long message to test horizontal growth of the bubble window. "
                "It contains enough text to push the boundaries and verify that the layout handles "
                "wide content gracefully without clipping or overflow issues.\n\n"
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor "
                "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
                "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute "
                "irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
                "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia "
                "deserunt mollit anim id est laborum.\n\n"
                "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium "
                "doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore "
                "veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam "
                "voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur "
                "magni dolores eos qui ratione voluptatem sequi nesciunt.\n\n"
                "Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, "
                "adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore "
                "magnam aliquam quaerat voluptatem. Ut enim ad minima veniam, quis nostrum "
                "exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi "
                "consequatur? Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse "
                "quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas "
                "nulla pariatur?\n\n"
                "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis "
                "praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias "
                "excepturi sint occaecati cupiditate non provident, similique sunt in culpa qui "
                "officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem "
                "rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est "
                "eligendi optio cumque nihil impedit quo minus id quod maxime placeat facere "
                "possimus, omnis voluptas assumenda est, omnis dolor repellendus.",
                label="long",
                duration_ms=10000,
            )
            return

        if not self._gateway:
            self._debug_stream_text(
                f"Not connected to gateway. Configure in settings.\n\nYou said: {text}",
                label="local",
            )
            return

        self._current_response = ""
        self._active_bubble_id = self._begin_streaming()

        # Send via gateway
        asyncio.run_coroutine_threadsafe(self._send_chat(text), self._loop)

    async def _send_chat(self, text: str):
        session = ChatSession(self._gateway)
        try:
            run_id = await session.send("main", text)
            logger.info(f"Chat sent, run_id={run_id}")
        except Exception as e:
            logger.error(f"Chat send failed: {e}")
            self._on_stream_delta(f"Error: {e}")
            self._on_stream_final(f"Error: {e}")

    def _on_chat_event(self, event):
        """Called from gateway event callback (may be from async thread)."""
        state = event.get("state", "")
        run_id = event.get("runId")
        message = event.get("message")

        # Intercept events from the silent /commands fetch — don't show in bubble
        if self._silent_fetch_run_id and run_id == self._silent_fetch_run_id:
            command_text = self._extract_text_content(message)
            if state == "delta" and command_text:
                self._command_response_buffer = command_text
            elif state == "final":
                final_text = command_text or self._command_response_buffer
                commands = parse_commands_response(final_text)
                if commands:
                    save_cached_commands(self._settings_mgr._config_dir, commands)
                    self._input.set_commands(commands)
                    logger.info(f"Slash commands fetched and cached ({len(commands)} commands)")
                else:
                    logger.warning("Silent /commands fetch returned no parseable commands")
                self._silent_fetch_run_id = None
                self._command_response_buffer = ""
                self._slash_commands_fetch_in_flight = False
            elif state in ("error", "aborted"):
                logger.warning(f"Silent /commands fetch {state}")
                self._silent_fetch_run_id = None
                self._command_response_buffer = ""
                self._slash_commands_fetch_in_flight = False
            return

        if state == "delta" and message:
            text_content = self._extract_text_content(message)
            if text_content:
                self._current_response = text_content
            self._on_stream_delta(self._current_response)

        elif state == "final":
            final_text = self._extract_text_content(message) or self._current_response
            self._on_stream_final(final_text)
            self._current_response = ""

        elif state == "error":
            error_msg = event.get("error_message", "Unknown error")
            self._on_stream_delta(f"Error: {error_msg}")
            self._on_stream_final(f"Error: {error_msg}")

        elif state == "aborted":
            self._on_stream_final(self._current_response)
            self._current_response = ""

    # ------------------------------------------------------------------
    # Streaming lifecycle (shared by gateway and debug cheat codes)
    # ------------------------------------------------------------------

    def _begin_streaming(self, label: str = "msg") -> str:
        """Start a streaming bubble: stop idle, create item, show bubble. Returns item_id."""
        self._idle_manager.stop()
        self._chat_state = "streaming"
        self._current_emotion = "thinking"
        self._ghost.set_expression("thinking")
        self._bubble_counter += 1
        item_id = f"{label}-{self._bubble_counter}"
        self._bubble.start_streaming(item_id, "")
        if not self._bubble.is_bubble_visible():
            self._bubble.show_bubble()
        return item_id

    def _on_stream_delta(self, raw_text: str) -> None:
        """Process a streaming delta: parse emotion, strip tags, update bubble."""
        emotion = parse_emotion(raw_text)
        if emotion and emotion != self._current_emotion:
            self._current_emotion = emotion
            self._ghost.set_expression(emotion)
        display_text = strip_all_tags(raw_text)
        if self._active_bubble_id:
            self._bubble.update_text(self._active_bubble_id, display_text)

    def _on_stream_final(self, raw_text: str) -> None:
        """Finalize streaming: update bubble, extract buttons, end streaming."""
        emotion = parse_emotion(raw_text)
        if emotion:
            self._current_emotion = emotion
            self._ghost.set_expression(emotion)
        elif self._current_emotion == "thinking":
            self._current_emotion = "neutral"
            self._ghost.set_expression("neutral")
        display_text = strip_all_tags(raw_text)
        if self._active_bubble_id:
            self._bubble.update_text(self._active_bubble_id, display_text)
            buttons = parse_buttons(raw_text)
            if buttons:
                self._bubble.set_buttons(self._active_bubble_id, buttons)
        self._end_streaming()

    def _end_streaming(self) -> None:
        """Finalize active bubble and restart idle."""
        if self._active_bubble_id:
            self._bubble.finalize(self._active_bubble_id, self._settings.bubble_timeout_ms)
        self._active_bubble_id = None
        self._chat_state = "idle"
        self._current_emotion = ""
        # If gateway is not connected, restore connecting state instead of idle
        if self._gateway.status != "connected":
            self._apply_connecting_state(True)
        else:
            self._idle_manager.reset()

    def _debug_stream_text(self, text: str, *, label: str = "debug", duration_ms: int = 1000):
        """Stream text into the bubble over duration_ms, simulating gateway streaming."""
        self._active_bubble_id = self._begin_streaming(label=f"debug-{label}")

        # Calculate chunk size to finish in ~duration_ms at 30ms intervals
        tick_interval = 30
        num_ticks = max(1, duration_ms // tick_interval)
        chunk_size = max(1, len(text) // num_ticks)

        self._debug_stream_pos = 0
        self._debug_stream_sample = text
        self._debug_stream_chunk = chunk_size

        def _tick():
            self._debug_stream_pos = min(
                self._debug_stream_pos + self._debug_stream_chunk, len(self._debug_stream_sample)
            )
            partial = self._debug_stream_sample[: self._debug_stream_pos]
            self._on_stream_delta(partial)
            if self._debug_stream_pos >= len(self._debug_stream_sample):
                self._debug_timer.stop()
                self._on_stream_final(self._debug_stream_sample)
                logger.info(f"Debug: {label} streaming complete")

        if hasattr(self, "_debug_timer") and self._debug_timer is not None:
            self._debug_timer.stop()
            self._debug_timer.deleteLater()
        self._debug_timer = QTimer()
        self._debug_timer.setInterval(tick_interval)
        self._debug_timer.timeout.connect(_tick)
        self._debug_timer.start()
        logger.info(f"Debug: {label} streaming started ({len(text)} chars, ~{duration_ms}ms)")

    # ------------------------------------------------------------------
    # Bubble actions
    # ------------------------------------------------------------------

    def _on_bubble_action(self, item_id: str, message: str):
        logger.info(f"Button clicked: {message}")
        self._bubble.set_buttons(item_id, [])
        self._on_chat_send(message)

    # ------------------------------------------------------------------
    # Gateway connection
    # ------------------------------------------------------------------

    def _connect_gateway(self):
        if not self._settings.gateway_url:
            logger.info("No gateway URL configured")
            return

        self._gateway = GatewayClient()
        self._gateway.on_event = self._on_gateway_event
        self._gateway.on_status_change = self._on_gateway_status

        self._gateway_task = asyncio.run_coroutine_threadsafe(
            self._gateway.start(),
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

        if not self._gateway or self._slash_commands_fetch_in_flight:
            return

        self._slash_commands_fetch_in_flight = True
        self._command_response_buffer = ""
        logger.info("Fetching slash commands from gateway")
        asyncio.run_coroutine_threadsafe(self._send_commands_fetch(), self._loop)

    async def _send_commands_fetch(self) -> None:
        assert self._gateway is not None
        session = ChatSession(self._gateway)
        try:
            run_id = await session.send("main", "/commands")
        except Exception as e:
            logger.warning(f"Failed to fetch slash commands: {e}")
            self._slash_commands_fetch_in_flight = False
            self._silent_fetch_run_id = None
            self._command_response_buffer = ""
            return

        self._silent_fetch_run_id = run_id
        logger.debug(f"Silent /commands fetch run_id={run_id}")

    def _extract_text_content(self, message: dict | None) -> str:
        if not message:
            return ""

        chunks: list[str] = []
        for block in message.get("content", []):
            if block.get("type") == "text" and block.get("text"):
                chunks.append(block["text"])
        return "".join(chunks)

    def _on_gateway_event(self, event):
        """Called from async thread — marshal to Qt main thread."""
        if event.event == "chat" and event.payload:
            payload = event.payload
            # Use QTimer.singleShot to marshal to main thread
            QTimer.singleShot(0, lambda: self._on_chat_event(payload))

    def _on_gateway_status(self, status: str):
        logger.info(f"Gateway status: {status}")
        QTimer.singleShot(0, lambda: self._input.set_connection_status(status))
        if status == "connecting":
            QTimer.singleShot(0, lambda: self._apply_connecting_state(True))
        if status == "disconnected":
            QTimer.singleShot(0, lambda: self._apply_connecting_state(True))
            self._silent_fetch_run_id = None
            self._command_response_buffer = ""
            self._slash_commands_fetch_in_flight = False
        if status == "connected":
            QTimer.singleShot(0, lambda: self._apply_connecting_state(False))
            QTimer.singleShot(0, self._fetch_slash_commands)

    def _apply_connecting_state(self, connecting: bool) -> None:
        """Set ghost expression and overlay for connecting/disconnected state."""
        if connecting:
            self._idle_manager.stop()
            self._ghost.set_expression("thinking")
            self._ghost.set_overlay("CONNECTING")
        else:
            self._ghost.set_overlay("")
            self._ghost.set_expression("neutral")
            self._idle_manager.start()

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
        sr = self._ghost_screen_rect()
        self._quake.toggle(
            self._settings.quake_terminal,
            screen_rect=(sr.x, sr.y, sr.width, sr.height),
        )

    def _on_quake_toggled(self, visible: bool):
        logger.info(f"Quake terminal {'shown' if visible else 'hidden'}")

    def _check_sigusr2(self):
        if self._sigusr2_event.is_set():
            self._sigusr2_event.clear()
            self._toggle_ghost()

    def _close_auxiliary_windows(self):
        self._input.hide_input()
        self._settings_win.hide_settings()
        self._skin_picker.hide_picker()
        self._get_skins_win.hide()

    def _toggle_ghost(self):
        self._close_auxiliary_windows()
        if self._ghost.isVisible():
            # Save position while ghost is still visible (swaymsg can find it)
            x, y = self._ghost.save_position()
            self._state.ghost_x, self._state.ghost_y = x, y
            self._bubble_visible_before_hide = self._bubble.is_bubble_visible()
            self._ghost.hide()
            self._bubble.hide_bubble()
        else:
            self._ghost.show()
            # Restore happens via window_mapped signal (deferred until compositor maps the window)

    def _show_skin_picker(self):
        logger.debug("_show_skin_picker: listing skins")
        skins = self._skin_loader.list_skins()
        logger.debug(f"_show_skin_picker: got {len(skins)} skins, calling show_picker")
        self._skin_picker.show_picker(skins, self._settings.current_skin_id)
        logger.debug("_show_skin_picker: show_picker returned, positioning")
        # Position near ghost window
        gx, gy = self._ghost_screen_pos()
        ghost_w = self._ghost.width()
        picker_w = self._skin_picker.width()
        x = gx + ghost_w // 2 - picker_w // 2
        y = gy - self._skin_picker.height() - 10
        sr = self._ghost_screen_rect()
        x = max(sr.x, min(x, sr.x + sr.width - picker_w))
        y = max(sr.y, min(y, sr.y + sr.height - self._skin_picker.height()))
        logger.debug(f"_show_skin_picker: moving to ({x}, {y})")
        self._skin_picker.move(x, y)
        logger.debug("_show_skin_picker: done")

    def _show_get_skins(self):
        gx, gy = self._ghost_screen_pos()
        x = gx + self._ghost.width() + 10
        y = gy - 40
        sr = self._ghost_screen_rect()
        if x + self._get_skins_win.width() > sr.x + sr.width:
            x = gx - self._get_skins_win.width() - 10
        x = max(sr.x, min(x, sr.x + sr.width - self._get_skins_win.width()))
        y = max(sr.y, min(y, sr.y + sr.height - self._get_skins_win.height()))
        self._get_skins_win.move(x, y)
        self._get_skins_win.show_window()

    def _on_skin_selected(self, skin_id: str):
        logger.info(f"_on_skin_selected: switching to {skin_id}")
        try:
            new_skin = self._skin_loader.load_skin(skin_id)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load skin '{skin_id}': {e}")
            return
        logger.debug(f"_on_skin_selected: skin loaded, setting on ghost")
        self._skin = new_skin
        emotions_map = self._load_emotions_map(new_skin)
        logger.debug(
            f"_on_skin_selected: emotions_map has {len(emotions_map)} entries, calling set_skin"
        )
        self._ghost.set_skin(emotions_map, new_skin.path)
        self._idle_manager.set_skin(new_skin)
        logger.debug("_on_skin_selected: set_skin done, saving settings")
        self._settings.current_skin_id = skin_id
        try:
            self._settings_mgr.update(current_skin_id=skin_id)
        except Exception as e:
            logger.warning(f"Failed to save skin setting: {e}")
        logger.info(f"_on_skin_selected: complete, skin={new_skin.name}")

    def _on_skin_installed(self, skin_id: str) -> None:
        logger.info(f"New skin installed: {skin_id}")
        if self._skin_picker.isVisible():
            skins = self._skin_loader.list_skins()
            self._skin_picker.show_picker(skins, self._settings.current_skin_id)

    def _show_settings(self):
        # Position near the ghost
        gx, gy = self._ghost_screen_pos()
        x = gx - self._settings_win.width() - 10
        y = gy
        # Keep on screen
        sr = self._ghost_screen_rect()
        if x < sr.x:
            x = gx + self._ghost.width() + 10
        if y + self._settings_win.height() > sr.y + sr.height:
            y = sr.y + sr.height - self._settings_win.height()
        self._settings_win.move(x, y)

        self._settings_win.show_settings(self._settings)

    def _on_settings_saved(self, updated: dict) -> None:
        old_url = self._settings.gateway_url
        old_token = self._settings.gateway_token
        old_terminal_cmd = self._settings.quake_terminal.command

        # Extract terminal command before passing to settings manager
        new_terminal_cmd = updated.pop("quake_terminal_command", old_terminal_cmd)

        try:
            if new_terminal_cmd != old_terminal_cmd:
                new_qt = self._settings.quake_terminal.model_copy(
                    update={"command": new_terminal_cmd}
                )
                updated["quake_terminal"] = new_qt
            self._settings_mgr.update(**updated)
        except Exception as e:
            logger.warning(f"Failed to persist settings: {e}")
        self._settings = self._settings_mgr.settings

        # Apply changed settings immediately
        self._apply_ghost_size()
        self._idle_manager.set_interval(self._settings.idle_interval_seconds)

        # Kill terminal if command changed — respawns on next toggle
        if new_terminal_cmd != old_terminal_cmd:
            logger.info(f"Terminal command changed to '{new_terminal_cmd}' — killing terminal")
            self._quake.cleanup()

        # Reconnect gateway if URL or token changed
        new_url = self._settings.gateway_url
        new_token = self._settings.gateway_token
        if new_url != old_url or new_token != old_token:
            logger.info("Gateway settings changed — reconnecting")
            if self._gateway:
                self._gateway.stop()
                self._gateway = None
                self._gateway_task = None
            self._connect_gateway()

    def _quit(self):
        self._app.quit()

    def _cleanup(self):
        """Shutdown hook called via aboutToQuit — runs regardless of quit path."""
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

        if self._bubble_visible_before_hide and self._ghost.isVisible():
            self._bubble.show_bubble()

    def run(self) -> int:
        self._ghost.show()
        # Position restore happens via window_mapped signal

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


def _set_process_name(name: str) -> None:
    """Set the process name visible to pkill/pgrep and ps."""
    # setproctitle changes /proc/PID/cmdline (shown by ps -eaf)
    setproctitle.setproctitle(name)
    # prctl changes /proc/PID/comm (used by pkill -x) — Linux only
    if sys.platform == "linux":
        libname = ctypes.util.find_library("c")
        if not libname:
            return
        libc = ctypes.CDLL(libname, use_errno=True)
        PR_SET_NAME = 15
        libc.prctl(PR_SET_NAME, name.encode(), 0, 0, 0)
    logger.info(f"Process name set to '{name}'")


def main():
    _set_process_name("deskmate")
    sys.exit(DeskMate().run())


if __name__ == "__main__":
    main()
