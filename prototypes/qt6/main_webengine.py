#!/usr/bin/env python3
"""
PyQt6 + QWebEngineView Transparent Desktop Companion Prototype

Tests the architecture: native Qt transparent window for the character sprite,
separate QWebEngineView window (Chromium) for the chat bubble with rich content.

Run: /usr/bin/python3 prototypes/qt6/main_webengine.py
"""

import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    QUrl,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

SKIN_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "skins" / "default"
EXPRESSIONS = ["neutral", "happy", "sad", "surprise", "thinking"]

# Simulated streaming chat content
CHAT_MESSAGES = [
    {
        "text": "Hello! I'm your desktop companion. Let me show you some **markdown** rendering.",
        "streaming": True,
    },
    {
        "text": """Here's a code block:

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

Pretty neat, right?""",
        "streaming": True,
    },
    {
        "text": """I can render rich content:

- **Bold text** and *italics*
- `inline code` spans
- [Links](https://example.com)

> Blockquotes work too!

And here's a longer code example with syntax highlighting:

```rust
fn main() {
    let message = "Hello from Rust!";
    println!("{}", message);
}
```""",
        "streaming": True,
    },
]


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Bubble window — separate top-level window with QWebEngineView
# ---------------------------------------------------------------------------

BUBBLE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

html, body {
    background: transparent;
    overflow: hidden;
    font-family: 'Segoe UI', 'Noto Sans', sans-serif;
    font-size: 14px;
    color: #e0e0e0;
}

#container {
    background: rgba(30, 30, 35, 0.92);
    border: 1px solid rgba(120, 120, 140, 0.3);
    border-radius: 12px;
    padding: 14px 16px;
    margin: 8px;
    min-height: 40px;
    max-height: 500px;
    overflow-y: auto;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
}

#container::-webkit-scrollbar { width: 6px; }
#container::-webkit-scrollbar-track { background: transparent; }
#container::-webkit-scrollbar-thumb {
    background: rgba(100, 100, 120, 0.5);
    border-radius: 3px;
}

#content {
    line-height: 1.5;
}

#content p { margin: 0.4em 0; }
#content strong { color: #fff; }
#content em { color: #c0c0d0; }

#content code {
    background: rgba(80, 80, 100, 0.4);
    padding: 1px 5px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 13px;
}

#content pre {
    background: rgba(20, 20, 28, 0.9);
    border: 1px solid rgba(80, 80, 100, 0.3);
    border-radius: 8px;
    padding: 10px 12px;
    margin: 8px 0;
    overflow-x: auto;
}

#content pre code {
    background: none;
    padding: 0;
    font-size: 12px;
    color: #c8c8d8;
}

#content blockquote {
    border-left: 3px solid rgba(100, 140, 255, 0.5);
    padding-left: 12px;
    margin: 8px 0;
    color: #a0a0b8;
}

#content ul, #content ol {
    padding-left: 20px;
    margin: 4px 0;
}

#content a {
    color: #7aa2f7;
    text-decoration: none;
}

#cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    background: #7aa2f7;
    margin-left: 2px;
    vertical-align: text-bottom;
    animation: blink 0.8s step-end infinite;
}

@keyframes blink {
    50% { opacity: 0; }
}

.fade-in {
    animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
</head>
<body>
<div id="container" class="fade-in">
    <div id="content"></div>
</div>
<script>
// Simple markdown-to-HTML (good enough for prototype)
function md(text) {
    let html = text
        // Code blocks (``` ... ```)
        .replace(/```(\\w*)\\n([\\s\\S]*?)```/g, (_, lang, code) => {
            return '<pre><code class="lang-' + lang + '">' +
                code.replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                '</code></pre>';
        })
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Bold
        .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\\*(.+?)\\*/g, '<em>$1</em>')
        // Links
        .replace(/\\[(.+?)\\]\\((.+?)\\)/g, '<a href="$2">$1</a>')
        // Blockquotes
        .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
        // Unordered lists
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        // Paragraphs (double newline)
        .replace(/\\n\\n/g, '</p><p>')
        // Single newlines within paragraphs
        .replace(/\\n/g, '<br>');

    // Wrap loose <li> in <ul>
    html = html.replace(/((?:<li>.*<\\/li>(?:<br>)?)+)/g, '<ul>$1</ul>');
    html = html.replace(/<br><\\/ul>/g, '</ul>');

    return '<p>' + html + '</p>';
}

function setContent(text, showCursor) {
    const el = document.getElementById('content');
    el.innerHTML = md(text) + (showCursor ? '<span id="cursor"></span>' : '');
    // Auto-scroll
    const container = document.getElementById('container');
    container.scrollTop = container.scrollHeight;
}

function clearContent() {
    document.getElementById('content').innerHTML = '';
}
</script>
</body>
</html>"""


class TransparentWebPage(QWebEnginePage):
    """WebEngine page with transparent background."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundColor(QColor(0, 0, 0, 0))


class BubbleWindow(QWidget):
    """Separate transparent window containing a QWebEngineView for rich chat content."""

    def __init__(self):
        super().__init__()

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(380, 280)

        # Web engine view for rich content
        self._web = QWebEngineView(self)
        page = TransparentWebPage(self._web)
        self._web.setPage(page)

        # Enable transparency in web view
        self._web.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._web.setStyleSheet("background: transparent;")
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._web)

        self._web.setHtml(BUBBLE_HTML)

        # Streaming state
        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(30)  # ~33 chars/sec
        self._stream_timer.timeout.connect(self._stream_tick)
        self._stream_text = ""
        self._stream_pos = 0
        self._current_display = ""

        self._visible = False
        log("BubbleWindow created with QWebEngineView (Chromium renderer)")

    def stream_message(self, text: str) -> None:
        """Start streaming a message character by character."""
        self._stream_text = text
        self._stream_pos = 0
        self._current_display = ""
        self._stream_timer.start()
        log(f"Streaming message ({len(text)} chars)")

    def set_message(self, text: str) -> None:
        """Set message instantly (no streaming)."""
        self._stream_timer.stop()
        self._current_display = text
        self._web.page().runJavaScript(f"setContent({self._js_escape(text)}, false);")

    def clear(self) -> None:
        self._stream_timer.stop()
        self._current_display = ""
        self._web.page().runJavaScript("clearContent();")

    def _stream_tick(self) -> None:
        # Stream 1-3 chars per tick for natural feel
        import random

        chars = random.randint(1, 3)
        self._stream_pos = min(self._stream_pos + chars, len(self._stream_text))
        self._current_display = self._stream_text[: self._stream_pos]

        self._web.page().runJavaScript(
            f"setContent({self._js_escape(self._current_display)}, true);"
        )

        if self._stream_pos >= len(self._stream_text):
            self._stream_timer.stop()
            # Remove cursor after done
            QTimer.singleShot(
                500,
                lambda: self._web.page().runJavaScript(
                    f"setContent({self._js_escape(self._current_display)}, false);"
                ),
            )
            log("Streaming complete")

    def _js_escape(self, text: str) -> str:
        """Escape text for JavaScript string literal."""
        return (
            '"'
            + text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            + '"'
        )

    def show_bubble(self) -> None:
        self._visible = True
        self.show()
        log("Bubble window shown")

    def hide_bubble(self) -> None:
        self._visible = False
        self.hide()
        log("Bubble window hidden — check for bleed artifacts at previous location")

    def is_bubble_visible(self) -> bool:
        return self._visible


# ---------------------------------------------------------------------------
# Ghost window — native Qt transparent rendering for the character sprite
# ---------------------------------------------------------------------------

DISPLAY_HEIGHT = 400


class GhostWindow(QWidget):
    position_changed = pyqtSignal(QPoint)

    def __init__(self):
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
        self._dragging = False
        self._drag_offset = QPoint()

        # Load skin textures
        self._pixmaps: dict[str, QPixmap] = {}
        for expr in EXPRESSIONS:
            path = SKIN_DIR / f"{expr}.png"
            if path.exists():
                pm = QPixmap(str(path))
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

        first = next(iter(self._pixmaps.values()))
        self.resize(first.width() + 20, first.height() + 20)
        log(f"GhostWindow created. Size: {self.width()}x{self.height()}")

    def current_expr(self) -> str:
        return EXPRESSIONS[self._expr_index]

    def _current_pixmap(self) -> QPixmap:
        expr = self.current_expr()
        if expr in self._pixmaps:
            return self._pixmaps[expr]
        return next(iter(self._pixmaps.values()))

    def cycle_expression(self) -> None:
        prev = self.current_expr()
        self._expr_index = (self._expr_index + 1) % len(EXPRESSIONS)
        self.update()
        log(f"Expression: {prev} -> {self.current_expr()}. Watch for bleed artifacts.")

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Clear to fully transparent
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Draw sprite centered
        pm = self._current_pixmap()
        x = (self.width() - pm.width()) // 2
        y = (self.height() - pm.height()) // 2
        painter.drawPixmap(x, y, pm)
        painter.end()

    # Drag support
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self.position_changed.emit(self.pos())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.position_changed.emit(self.pos())


# ---------------------------------------------------------------------------
# Orchestrator — coordinates ghost + bubble windows
# ---------------------------------------------------------------------------


class Orchestrator:
    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("deskmate-qt6-webengine-prototype")

        self._ghost = GhostWindow()
        self._bubble = BubbleWindow()
        self._msg_index = 0

        # Position ghost at center of screen
        screen = self._app.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self._ghost.move(
                sg.center().x() - self._ghost.width() // 2,
                sg.center().y() - self._ghost.height() // 2,
            )

        # Update bubble position when ghost moves
        self._ghost.position_changed.connect(self._reposition_bubble)

        # Global shortcuts (on the ghost window since it stays focused)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self._ghost).activated.connect(
            self._on_expression
        )
        QShortcut(QKeySequence(Qt.Key.Key_B), self._ghost).activated.connect(self._on_toggle_bubble)
        QShortcut(QKeySequence(Qt.Key.Key_N), self._ghost).activated.connect(self._on_next_message)
        QShortcut(QKeySequence(Qt.Key.Key_Q), self._ghost).activated.connect(self._on_quit)

    def _reposition_bubble(self, ghost_pos: QPoint = None) -> None:
        """Position bubble window above-right of the ghost."""
        if ghost_pos is None:
            ghost_pos = self._ghost.pos()
        bx = ghost_pos.x() + self._ghost.width() - 40
        by = ghost_pos.y() - self._bubble.height() + 60
        self._bubble.move(bx, by)

    def _on_expression(self) -> None:
        self._ghost.cycle_expression()

    def _on_toggle_bubble(self) -> None:
        if self._bubble.is_bubble_visible():
            self._bubble.hide_bubble()
        else:
            self._reposition_bubble()
            self._bubble.show_bubble()
            if not self._bubble._current_display:
                self._bubble.stream_message(CHAT_MESSAGES[0]["text"])

    def _on_next_message(self) -> None:
        """Stream the next demo message."""
        if not self._bubble.is_bubble_visible():
            self._reposition_bubble()
            self._bubble.show_bubble()

        self._msg_index = (self._msg_index + 1) % len(CHAT_MESSAGES)
        msg = CHAT_MESSAGES[self._msg_index]
        if msg["streaming"]:
            self._bubble.stream_message(msg["text"])
        else:
            self._bubble.set_message(msg["text"])
        log(f"Message {self._msg_index}: streaming={msg['streaming']}")

    def _on_quit(self) -> None:
        log("Quitting.")
        self._app.quit()

    def run(self) -> int:
        self._ghost.show()
        self._reposition_bubble()

        log("=" * 60)
        log("Qt6 + QWebEngineView Transparent Prototype")
        log("=" * 60)
        log(f"Expressions: {EXPRESSIONS}")
        log("Shortcuts:")
        log("  Space = cycle expression (watch for bleed)")
        log("  B     = toggle bubble window")
        log("  N     = next message (stream rich content)")
        log("  Q     = quit")
        log("")
        log("TESTS TO RUN:")
        log("  1. Press Space rapidly — any ghost pixels from previous expression?")
        log("  2. Press B to show bubble — is the background transparent?")
        log("  3. Press N to stream markdown/code — does it render correctly?")
        log("  4. Press B to hide bubble — any bleed at the old position?")
        log("  5. Drag the character — does bubble follow?")
        log("=" * 60)

        return self._app.exec()


if __name__ == "__main__":
    sys.exit(Orchestrator().run())
