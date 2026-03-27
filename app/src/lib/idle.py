"""IdleAnimationManager — plays idle animations on the ghost when chat is quiet."""

import random

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal

from src.lib.skin import SkinInfo


class IdleAnimationManager(QObject):
    """Manages idle animation playback on the ghost window.

    When chat is idle AND bubble is not visible, starts an idle timer.
    After idle_interval_seconds (with ±10% jitter), picks a random idle
    animation from the skin, emits idle_override with the file path, then
    after the animation's duration_ms emits idle_cleared and restarts the
    timer.

    Any user interaction should call reset() to cancel the current
    animation and restart the countdown.
    """

    idle_override = Signal(str)  # file path to APNG/PNG to display
    idle_cleared = Signal()  # animation ended — restore expression

    def __init__(self, parent=None):
        super().__init__(parent)

        self._skin: SkinInfo | None = None
        self._interval_seconds: float = 30.0
        self._enabled: bool = True
        self._animating: bool = False

        # Timer that fires when idle long enough to start an animation
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_fired)

        # Timer that fires when the current animation's duration is up
        self._anim_timer = QTimer(self)
        self._anim_timer.setSingleShot(True)
        self._anim_timer.timeout.connect(self._on_anim_complete)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin the idle timer cycle."""
        if not self._enabled or not self._has_animations():
            return
        self._start_idle_timer()

    def stop(self) -> None:
        """Stop all timers and clear any playing animation."""
        self._idle_timer.stop()
        self._anim_timer.stop()
        if self._animating:
            self._animating = False
            self.idle_cleared.emit()

    def reset(self) -> None:
        """Cancel current animation and restart the idle countdown.

        Call on any user interaction: chat send, bubble show, expression change.
        """
        self._idle_timer.stop()
        self._anim_timer.stop()
        if self._animating:
            self._animating = False
            self.idle_cleared.emit()
            logger.debug("[idle] interaction interrupted animation")
        if self._enabled and self._has_animations():
            self._start_idle_timer()

    def set_skin(self, skin: SkinInfo) -> None:
        """Update available animations when the skin changes."""
        self._skin = skin
        # Restart the cycle with the new skin
        if self._enabled:
            self.reset()

    def set_interval(self, seconds: float) -> None:
        """Update the idle interval (takes effect on next cycle)."""
        self._interval_seconds = seconds

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the idle system."""
        self._enabled = enabled
        if enabled:
            self.reset()
        else:
            self.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_animations(self) -> bool:
        return self._skin is not None and len(self._skin.idle_animations) > 0

    def _start_idle_timer(self) -> None:
        base_ms = self._interval_seconds * 1000
        jitter = base_ms * (random.random() * 0.2 - 0.1)  # ±10%
        delay_ms = int(base_ms + jitter)
        logger.debug(
            "[idle] starting idle timer: %dms (base=%dms, jitter=%+.0fms)",
            delay_ms,
            int(base_ms),
            jitter,
        )
        self._idle_timer.start(delay_ms)

    def _on_idle_fired(self) -> None:
        if not self._enabled or not self._has_animations():
            return

        anims = self._skin.idle_animations  # type: ignore[union-attr]
        anim = random.choice(anims)
        path = str(self._skin.path / anim.file)  # type: ignore[union-attr]

        logger.debug(f"[idle] timer fired, playing: {anim.file} (duration={anim.duration_ms}ms)")

        self._animating = True
        self.idle_override.emit(path)
        self._anim_timer.start(anim.duration_ms)

    def _on_anim_complete(self) -> None:
        logger.debug("[idle] animation complete, restoring expression")
        self._animating = False
        self.idle_cleared.emit()
        # Restart idle timer for next cycle
        if self._enabled and self._has_animations():
            self._start_idle_timer()
