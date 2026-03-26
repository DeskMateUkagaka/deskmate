#!/usr/bin/env python3
"""
PyQt6 Transparent Desktop Companion Prototype

Uses real skin assets from app/skins/default/ to test transparency
with actual image swapping (expression changes).

Run: /usr/bin/python3 main.py
"""

import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget

SKIN_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "skins" / "default"

EXPRESSIONS = ["neutral", "happy", "sad", "surprise", "thinking"]


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Bubble widget — separate child widget so opacity animation is isolated
# ---------------------------------------------------------------------------


class BubbleWidget(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._opacity: float = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setVisible(False)
        self.resize(280, 70)

    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    bubbleOpacity = pyqtProperty(float, fget=_get_opacity, fset=_set_opacity)

    def paintEvent(self, _event) -> None:
        if self._opacity <= 0.001:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)

        rect = QRect(4, 4, self.width() - 8, self.height() - 8)
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 12, 12)

        painter.fillPath(path, QColor(40, 40, 40, 220))
        painter.setPen(QPen(QColor(200, 200, 200, 180), 1.5))
        painter.drawPath(path)

        painter.setPen(QColor(255, 255, 255))
        font = QFont("Sans", 9)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(10, 0, -10, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "Hello! I'm your desktop companion!",
        )
        painter.end()


# ---------------------------------------------------------------------------
# Main window — loads real skin PNGs
# ---------------------------------------------------------------------------

# Scale factor for the tall 871x3133 images
DISPLAY_HEIGHT = 400


class CompanionWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._expr_index = 0
        self._bubble_visible = False
        self._click_through = False

        # Load skin textures
        self._pixmaps: dict[str, QPixmap] = {}
        for expr in EXPRESSIONS:
            path = SKIN_DIR / f"{expr}.png"
            if path.exists():
                pm = QPixmap(str(path))
                # Scale to DISPLAY_HEIGHT, keep aspect ratio
                self._pixmaps[expr] = pm.scaledToHeight(
                    DISPLAY_HEIGHT, Qt.TransformationMode.SmoothTransformation
                )
                log(
                    f"Loaded {expr}: {pm.width()}x{pm.height()} -> {self._pixmaps[expr].width()}x{self._pixmaps[expr].height()}"
                )
            else:
                log(f"WARNING: Missing skin asset: {path}")

        if not self._pixmaps:
            log("FATAL: No skin assets found. Exiting.")
            sys.exit(1)

        # Size window to fit the scaled image
        first = self._pixmaps[EXPRESSIONS[self._expr_index]]
        self.resize(first.width() + 20, first.height() + 20)

        # Bubble child widget, positioned above-right of sprite
        self._bubble = BubbleWidget(self)
        self._bubble.move(first.width() - 60, 10)

        # Animation for bubble opacity
        self._anim = QPropertyAnimation(self._bubble, b"bubbleOpacity", self)
        self._anim.setDuration(300)
        self._anim.finished.connect(self._on_anim_finished)

        log(
            f"Window created. Expression: {self._current_expr()}. Size: {self.width()}x{self.height()}"
        )

    def _current_expr(self) -> str:
        return EXPRESSIONS[self._expr_index]

    def _current_pixmap(self) -> QPixmap:
        return self._pixmaps[self._current_expr()]

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Clear to transparent
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Draw the skin image centered
        pm = self._current_pixmap()
        x = (self.width() - pm.width()) // 2
        y = (self.height() - pm.height()) // 2
        painter.drawPixmap(x, y, pm)

        # Mode indicator
        mode_text = "[T] click-through" if self._click_through else "[T] interactive"
        painter.setPen(QColor(200, 200, 200, 160))
        painter.setFont(QFont("Sans", 7))
        painter.drawText(4, 14, mode_text)

        painter.end()

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        key = event.key()

        if key == Qt.Key.Key_Space:
            self._toggle_expression()
        elif key == Qt.Key.Key_B:
            self._toggle_bubble()
        elif key == Qt.Key.Key_F:
            self._animate_bubble()
        elif key == Qt.Key.Key_T:
            self._toggle_click_through()
        elif key == Qt.Key.Key_Q:
            log("Q pressed — quitting.")
            QApplication.quit()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Expression switch — cycles through real skin PNGs
    # ------------------------------------------------------------------

    def _toggle_expression(self) -> None:
        prev = self._current_expr()
        self._expr_index = (self._expr_index + 1) % len(EXPRESSIONS)
        self.update()
        log(
            f"Expression switched: {prev} -> {self._current_expr()}. "
            "Observe window for bleed artifacts (ghost pixels from previous image)."
        )
        QTimer.singleShot(16, self._check_repaint)

    def _check_repaint(self) -> None:
        self.update()
        log("Repaint triggered (16 ms post-switch). Check for residual pixels.")

    # ------------------------------------------------------------------
    # Bubble toggle
    # ------------------------------------------------------------------

    def _toggle_bubble(self) -> None:
        self._bubble_visible = not self._bubble_visible
        if self._bubble_visible:
            self._bubble.setVisible(True)
            self._bubble._opacity = 1.0
            self._bubble.update()
            log("Bubble shown (instant, no animation). Use F to animate.")
        else:
            self._bubble.setVisible(False)
            self._bubble._opacity = 0.0
            log("Bubble hidden.")

    # ------------------------------------------------------------------
    # Fade animation
    # ------------------------------------------------------------------

    def _animate_bubble(self) -> None:
        if self._anim.state() == QPropertyAnimation.State.Running:
            log("Animation already running — skipping.")
            return

        if not self._bubble_visible:
            self._bubble._opacity = 0.0
            self._bubble.setVisible(True)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._bubble_visible = True
            log("Bubble fade-IN animation started.")
        else:
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            log("Bubble fade-OUT animation started.")

        self._anim.start()

    def _on_anim_finished(self) -> None:
        opacity = self._bubble._opacity
        log(f"Animation finished. Final opacity={opacity:.2f}")
        if opacity <= 0.001:
            self._bubble.setVisible(False)
            self._bubble_visible = False
            log("Bubble hidden after fade-out.")

    # ------------------------------------------------------------------
    # Click-through toggle
    # ------------------------------------------------------------------

    def _toggle_click_through(self) -> None:
        self._click_through = not self._click_through
        flags = self.windowFlags()
        if self._click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
            log("Click-through ENABLED. NOTE: On Wayland this flag may have no effect.")
        else:
            flags &= ~Qt.WindowType.WindowTransparentForInput
            log("Click-through DISABLED — window is interactive again.")

        pos = self.pos()
        self.setWindowFlags(flags)
        self.move(pos)
        self.show()
        self.update()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("deskmate-qt6-prototype")

    window = CompanionWindow()
    screen = app.primaryScreen()
    if screen is not None:
        sg = screen.availableGeometry()
        window.move(
            sg.center().x() - window.width() // 2,
            sg.center().y() - window.height() // 2,
        )

    window.show()
    log(f"Window shown. Expressions: {EXPRESSIONS}")
    log("Shortcuts: Space=expression, B=bubble, F=fade, T=click-through, Q=quit")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
