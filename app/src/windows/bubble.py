"""BubbleWindow — transparent window with QWebEngineView for rich chat content."""

import json

from loguru import logger
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

# ---------------------------------------------------------------------------
# Embedded HTML template — full feature bubble with markdown, streaming,
# dismiss/pin/copy buttons, progress bar, JS↔Python QWebChannel bridge.
# ---------------------------------------------------------------------------

BUBBLE_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

html, body {
    background: transparent;
    overflow: hidden;
    font-family: 'Segoe UI', 'Noto Sans', sans-serif;
    font-size: 14px;
    color: #e0e0e0;
    max-width: 640px;
}

#items-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px;
    max-width: 640px;
    height: 100vh;
    overflow-y: auto;
}
#items-container::-webkit-scrollbar { display: none; }

.bubble-item {
    background: rgba(30, 30, 35, 0.92);
    border: 1px solid rgba(120, 120, 140, 0.3);
    border-radius: 12px;
    padding: 12px 14px 10px 14px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
    position: relative;
    animation: fadeIn 0.25s ease-out;
    max-width: 640px;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}

@keyframes fadeOut {
    from { opacity: 1; transform: translateY(0); }
    to   { opacity: 0; transform: translateY(-6px); }
}

.bubble-item.dismissing {
    animation: fadeOut 0.2s ease-in forwards;
}

/* ---- header row (copy + pin + dismiss button) ---- */
.bubble-header {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
    min-height: 18px;
}

.btn-icon {
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 4px;
    font-size: 12px;
    color: rgba(200, 200, 220, 0.5);
    line-height: 1;
    transition: color 0.15s, background 0.15s;
}
.btn-icon:hover { color: #e0e0e0; background: rgba(255,255,255,0.08); }
.btn-icon.pinned { color: #7aa2f7; }
.btn-icon.copy-btn {
    font-size: 15px;
    padding: 1px 3px;
}
.btn-icon.copy-btn.copied {
    color: #73daca;
    background: rgba(115, 218, 202, 0.14);
}

/* ---- content area ---- */
.bubble-content {
    line-height: 1.55;
    overflow-wrap: break-word;
    word-break: break-word;
    max-height: var(--max-content-height, 480px);
    overflow-y: auto;
}

.bubble-content::-webkit-scrollbar { width: 5px; }
.bubble-content::-webkit-scrollbar-track { background: transparent; }
.bubble-content::-webkit-scrollbar-thumb {
    background: rgba(100, 100, 120, 0.4);
    border-radius: 3px;
}

.bubble-content p { margin: 0.35em 0; }
.bubble-content p:first-child { margin-top: 0; }
.bubble-content p:last-child  { margin-bottom: 0; }
.bubble-content strong { color: #fff; }
.bubble-content em     { color: #c0c0d0; }
.bubble-content a      { color: #7aa2f7; text-decoration: none; }
.bubble-content a:hover { text-decoration: underline; }

.bubble-content code {
    background: rgba(80, 80, 100, 0.4);
    padding: 1px 5px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 12.5px;
}

.bubble-content pre {
    background: rgba(18, 18, 26, 0.95);
    border: 1px solid rgba(80, 80, 100, 0.35);
    border-radius: 8px;
    padding: 10px 12px;
    margin: 8px 0;
    overflow-x: auto;
    position: relative;
}
.bubble-content pre code {
    background: none;
    padding: 0;
    font-size: 12px;
    color: #c8c8d8;
}
.bubble-content blockquote {
    border-left: 3px solid rgba(100, 140, 255, 0.5);
    padding-left: 12px;
    margin: 8px 0;
    color: #a0a0b8;
}
.bubble-content ul, .bubble-content ol { padding-left: 18px; margin: 4px 0; }
.bubble-content li { margin: 2px 0; }

/* copy button inside code blocks */
.code-copy-btn {
    position: absolute;
    top: 6px;
    right: 8px;
    background: rgba(60, 60, 80, 0.7);
    border: 1px solid rgba(100,100,120,0.4);
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 11px;
    color: #b0b0c8;
    cursor: pointer;
}
.code-copy-btn:hover { background: rgba(80,80,100,0.9); color: #e0e0e0; }

/* ---- streaming cursor ---- */
.cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    background: #7aa2f7;
    margin-left: 2px;
    vertical-align: text-bottom;
    animation: blink 0.8s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }

/* ---- action buttons ---- */
.btn-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 10px;
}
.action-btn {
    background: rgba(60, 80, 140, 0.35);
    border: 1px solid rgba(100, 140, 220, 0.4);
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 13px;
    color: #aabcf0;
    cursor: pointer;
    transition: background 0.15s;
}
.action-btn:hover { background: rgba(80, 110, 180, 0.5); color: #d0dcff; }

/* ---- dismiss progress bar ---- */
.progress-bar-wrap {
    margin-top: 8px;
    height: 2px;
    background: rgba(80, 80, 100, 0.2);
    border-radius: 1px;
    overflow: hidden;
}
.progress-bar-fill {
    height: 100%;
    background: rgba(120, 140, 220, 0.5);
    border-radius: 1px;
    transition: width linear;
}
</style>
</head>
<body>
<div id="items-container"></div>

<script>
// ---- QWebChannel bridge ----
var _bridge = null;
new QWebChannel(qt.webChannelTransport, function(channel) {
    _bridge = channel.objects.bridge;
});

function callBridge(method, args) {
    if (_bridge) {
        _bridge[method](JSON.stringify(args));
    }
}

// ---- Markdown renderer ----
function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function md(text) {
    var lines = text.split('\\n');
    var out = [];
    var inCode = false;
    var codeLang = '';
    var codeLines = [];

    for (var i = 0; i < lines.length; i++) {
        var line = lines[i];

        // fenced code block start
        if (!inCode && /^```(\\w*)/.test(line)) {
            codeLang = line.match(/^```(\\w*)/)[1];
            inCode = true;
            codeLines = [];
            continue;
        }
        // fenced code block end
        if (inCode && line.trim() === '```') {
            inCode = false;
            var codeHtml = escapeHtml(codeLines.join('\\n'));
            out.push('<pre><code class="lang-' + escapeHtml(codeLang) + '">' + codeHtml + '</code></pre>');
            continue;
        }
        if (inCode) {
            codeLines.push(line);
            continue;
        }

        // blockquote
        if (/^> /.test(line)) {
            out.push('<blockquote>' + inlinemd(line.slice(2)) + '</blockquote>');
            continue;
        }
        // unordered list item
        if (/^- /.test(line)) {
            out.push('<ul><li>' + inlinemd(line.slice(2)) + '</li></ul>');
            continue;
        }
        // ordered list item
        if (/^\\d+\\. /.test(line)) {
            out.push('<ol><li>' + inlinemd(line.replace(/^\\d+\\. /, '')) + '</li></ol>');
            continue;
        }
        // blank line = paragraph break
        if (line.trim() === '') {
            out.push('<p style="margin:0.2em 0"></p>');
            continue;
        }
        out.push('<p>' + inlinemd(line) + '</p>');
    }

    // flush unclosed code block
    if (inCode) {
        out.push('<pre><code>' + escapeHtml(codeLines.join('\\n')) + '</code></pre>');
    }

    // merge consecutive <ul>/<ol>
    var html = out.join('');
    html = html.replace(/<\\/ul><ul>/g, '').replace(/<\\/ol><ol>/g, '');
    return html;
}

function inlinemd(s) {
    return s
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
        .replace(/\\*(.+?)\\*/g, '<em>$1</em>')
        .replace(/\\_\\_(.+?)\\_\\_ /g, '<strong>$1</strong>')
        .replace(/\\_(.+?)\\_/g, '<em>$1</em>')
        .replace(/\\[(.+?)\\]\\((.+?)\\)/g, '<a href="$2" target="_blank">$1</a>');
}

// ---- Item management ----
var _items = {};   // id -> { el, timerId, totalMs, startTime, pinned, animFrame, rawText }

function _getContainer() { return document.getElementById('items-container'); }

function addItem(id, text, isStreaming) {
    if (_items[id]) return;

    var wrap = document.createElement('div');
    wrap.className = 'bubble-item';
    wrap.id = 'item-' + id;

    var header = document.createElement('div');
    header.className = 'bubble-header';

    var copyBtn = document.createElement('button');
    copyBtn.className = 'btn-icon copy-btn';
    copyBtn.textContent = '\ud83d\udccb';  // 📋
    copyBtn.title = 'Copy to clipboard';
    copyBtn.onclick = function() { callBridge('onCopy', {id: id}); };

    var pinBtn = document.createElement('button');
    pinBtn.className = 'btn-icon pin-btn';
    pinBtn.textContent = '\\u{1F4CC}';  // 📌
    pinBtn.title = 'Pin';
    pinBtn.onclick = function() { callBridge('onPin', {id: id}); };

    var dismissBtn = document.createElement('button');
    dismissBtn.className = 'btn-icon';
    dismissBtn.textContent = '\\u00D7';  // ×
    dismissBtn.title = 'Dismiss';
    dismissBtn.onclick = function() { callBridge('onDismiss', {id: id}); };

    header.appendChild(copyBtn);
    header.appendChild(pinBtn);
    header.appendChild(dismissBtn);

    var content = document.createElement('div');
    content.className = 'bubble-content';

    var btnRow = document.createElement('div');
    btnRow.className = 'btn-row';
    btnRow.style.display = 'none';

    var progressWrap = document.createElement('div');
    progressWrap.className = 'progress-bar-wrap';
    progressWrap.style.display = 'none';
    var progressFill = document.createElement('div');
    progressFill.className = 'progress-bar-fill';
    progressFill.style.width = '100%';
    progressWrap.appendChild(progressFill);

    wrap.appendChild(header);
    wrap.appendChild(content);
    wrap.appendChild(btnRow);
    wrap.appendChild(progressWrap);
    _getContainer().appendChild(wrap);

    _items[id] = {
        el: wrap,
        contentEl: content,
        btnRowEl: btnRow,
        progressWrap: progressWrap,
        progressFill: progressFill,
        copyBtn: copyBtn,
        pinBtn: pinBtn,
        timerId: null,
        animFrame: null,
        copyResetTimer: null,
        totalMs: 0,
        startTime: 0,
        pinned: false,
        rawText: text,
    };

    _renderContent(id, text, isStreaming);
    _getContainer().scrollTop = _getContainer().scrollHeight;
    notifySized();
}

function updateItem(id, text, isStreaming) {
    if (!_items[id]) { addItem(id, text, isStreaming); return; }
    _renderContent(id, text, isStreaming);
    // Auto-scroll both the container and the item's content area to the end
    _getContainer().scrollTop = _getContainer().scrollHeight;
    var item = _items[id];
    if (item) item.contentEl.scrollTop = item.contentEl.scrollHeight;
    notifySized();
}

function finalizeItem(id) {
    var item = _items[id];
    if (!item) return;
    // remove cursor
    var cursor = item.contentEl.querySelector('.cursor');
    if (cursor) cursor.remove();
    notifySized();
}

function setButtons(id, buttonsJson) {
    var item = _items[id];
    if (!item) return;
    var buttons;
    try { buttons = JSON.parse(buttonsJson); } catch(e) { return; }
    var row = item.btnRowEl;
    row.innerHTML = '';
    buttons.forEach(function(label) {
        var btn = document.createElement('button');
        btn.className = 'action-btn';
        btn.textContent = label;
        btn.onclick = function() { callBridge('onAction', {id: id, label: label}); };
        row.appendChild(btn);
    });
    row.style.display = buttons.length ? 'flex' : 'none';
    notifySized();
}

function startDismissTimer(id, durationMs) {
    var item = _items[id];
    if (!item || item.pinned) return;
    item.totalMs = durationMs;
    item.startTime = Date.now();
    item.progressWrap.style.display = 'block';
    // Start at 100%, then animate to 0% via CSS transition
    item.progressFill.style.transition = 'none';
    item.progressFill.style.width = '100%';
    // Force reflow so the browser registers 100% before transitioning
    void item.progressFill.offsetWidth;
    item.progressFill.style.transition = 'width ' + durationMs + 'ms linear';
    item.progressFill.style.width = '0%';
    item.timerId = setTimeout(function() {
        callBridge('onDismiss', {id: id});
    }, durationMs);
}

function removeItem(id) {
    var item = _items[id];
    if (!item) return;
    if (item.timerId) clearTimeout(item.timerId);
    if (item.animFrame) cancelAnimationFrame(item.animFrame);
    if (item.copyResetTimer) clearTimeout(item.copyResetTimer);
    item.el.classList.add('dismissing');
    setTimeout(function() {
        if (item.el.parentNode) item.el.parentNode.removeChild(item.el);
        delete _items[id];
        notifySized();
        if (Object.keys(_items).length === 0 && _bridge) {
            _bridge.onAllDismissed();
        }
    }, 220);
}

function pinItem(id) {
    var item = _items[id];
    if (!item) return;
    item.pinned = true;
    if (item.timerId) { clearTimeout(item.timerId); item.timerId = null; }
    if (item.animFrame) { cancelAnimationFrame(item.animFrame); item.animFrame = null; }
    item.progressWrap.style.display = 'none';
    item.pinBtn.classList.add('pinned');
    item.pinBtn.title = 'Pinned';
}

function flashCopyButton(id) {
    var item = _items[id];
    if (!item || !item.copyBtn) return;
    item.copyBtn.classList.add('copied');
    item.copyBtn.textContent = '\u2713';
    item.copyBtn.title = 'Copied';
    if (item.copyResetTimer) clearTimeout(item.copyResetTimer);
    item.copyResetTimer = setTimeout(function() {
        item.copyBtn.classList.remove('copied');
        item.copyBtn.textContent = '\ud83d\udccb';
        item.copyBtn.title = 'Copy to clipboard';
        item.copyResetTimer = null;
    }, 1200);
}

function clearAll() {
    Object.keys(_items).forEach(function(id) { removeItem(id); });
}

function dismissOldest() {
    var ids = Object.keys(_items);
    // First try oldest unpinned
    for (var i = 0; i < ids.length; i++) {
        if (!_items[ids[i]].pinned) { removeItem(ids[i]); return true; }
    }
    // Then oldest pinned
    if (ids.length > 0) { removeItem(ids[0]); return true; }
    return false;
}

function pinNewest() {
    var ids = Object.keys(_items);
    for (var i = ids.length - 1; i >= 0; i--) {
        if (!_items[ids[i]].pinned) { pinItem(ids[i]); return true; }
    }
    return false;
}

function copyNewest() {
    var ids = Object.keys(_items);
    if (ids.length === 0) return false;
    callBridge('onCopy', {id: ids[ids.length - 1]});
    return true;
}

function _renderContent(id, text, isStreaming) {
    var item = _items[id];
    if (!item) return;
    item.rawText = text;
    var html = md(text);
    if (isStreaming) {
        html += '<span class="cursor"></span>';
    }
    item.contentEl.innerHTML = html;
    // attach copy buttons to all pre blocks
    item.contentEl.querySelectorAll('pre').forEach(function(pre) {
        if (!pre.querySelector('.code-copy-btn')) {
            var btn = document.createElement('button');
            btn.className = 'code-copy-btn';
            btn.textContent = 'copy';
            btn.onclick = function() {
                var code = pre.querySelector('code');
                if (code) {
                    callBridge('onCopyText', {text: code.innerText});
                    btn.textContent = 'copied!';
                    setTimeout(function() { btn.textContent = 'copy'; }, 1500);
                }
            };
            pre.appendChild(btn);
        }
    });
}

function notifySized() {
    var container = _getContainer();
    // Sum actual item heights + gaps + padding (not scrollHeight,
    // which grows unbounded once the container is scrollable)
    var items = container.children;
    var totalH = 0;
    for (var i = 0; i < items.length; i++) {
        totalH += items[i].offsetHeight;
    }
    var style = getComputedStyle(container);
    var gap = parseFloat(style.gap) || 0;
    var padY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    var h = totalH + padY + Math.max(0, items.length - 1) * gap;
    if (_bridge) _bridge.onContentSized(JSON.stringify({height: h}));
}

// Keyboard: Escape/X dismiss oldest, P pin newest, C copy newest
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' || e.key === 'x' || e.key === 'X') {
        dismissOldest();
    } else if (e.key === 'p' || e.key === 'P') {
        pinNewest();
    } else if (e.key === 'c' || e.key === 'C') {
        copyNewest();
    }
});

// notify once bridge is ready
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(notifySized, 100);
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# JS → Python bridge object
# ---------------------------------------------------------------------------


class _BubbleBridge(QObject):
    """Registered with QWebChannel so JS can call Python methods."""

    action_triggered = Signal(str, str)  # item_id, label
    dismiss_triggered = Signal(str)  # item_id
    pin_triggered = Signal(str)  # item_id
    copy_triggered = Signal(str)  # item_id
    code_copy_triggered = Signal(str)  # raw code text
    content_sized = Signal(int)  # height
    all_dismissed = Signal()

    @Slot(str)
    def onAction(self, payload: str) -> None:
        data = json.loads(payload)
        self.action_triggered.emit(str(data.get("id", "")), str(data.get("label", "")))

    @Slot(str)
    def onDismiss(self, payload: str) -> None:
        data = json.loads(payload)
        self.dismiss_triggered.emit(str(data.get("id", "")))

    @Slot(str)
    def onPin(self, payload: str) -> None:
        data = json.loads(payload)
        self.pin_triggered.emit(str(data.get("id", "")))

    @Slot(str)
    def onCopy(self, payload: str) -> None:
        data = json.loads(payload)
        self.copy_triggered.emit(str(data.get("id", "")))

    @Slot(str)
    def onCopyText(self, payload: str) -> None:
        data = json.loads(payload)
        self.code_copy_triggered.emit(str(data.get("text", "")))

    @Slot()
    def onAllDismissed(self) -> None:
        self.all_dismissed.emit()

    @Slot(str)
    def onContentSized(self, payload: str) -> None:
        data = json.loads(payload)
        h = int(data.get("height", 0))
        self.content_sized.emit(h)


# ---------------------------------------------------------------------------
# Transparent QWebEnginePage
# ---------------------------------------------------------------------------


class _TransparentWebPage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundColor(QColor(0, 0, 0, 0))


# ---------------------------------------------------------------------------
# BubbleWindow
# ---------------------------------------------------------------------------


class BubbleWindow(QWidget):
    """Transparent window with QWebEngineView for rich chat content.

    Uses Chromium (via QWebEngineView) for rendering so there are zero
    bleed-artifact issues — the renderer handles compositing cleanly.
    """

    # Re-exported from bridge for convenience
    action = Signal(str, str)  # item_id, label
    content_sized = Signal(int)  # height
    all_dismissed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("deskmate-bubble")
        self.resize(648, 400)
        self._max_window_height = 560

        # WebView
        self._web = QWebEngineView(self)
        self._page = _TransparentWebPage(self._web)
        self._web.setPage(self._page)
        self._web.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._web.setStyleSheet("background: transparent;")
        self._page.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, True)
        self._page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        # QWebChannel bridge
        self._bridge = _BubbleBridge(self)
        self._channel = QWebChannel(self._page)
        self._channel.registerObject("bridge", self._bridge)
        self._page.setWebChannel(self._channel)

        # Forward bridge signals
        self._bridge.action_triggered.connect(self.action)
        self._bridge.content_sized.connect(self._on_content_sized)
        self._bridge.dismiss_triggered.connect(self._on_bridge_dismiss)
        self._bridge.pin_triggered.connect(self._on_bridge_pin)
        self._bridge.copy_triggered.connect(self._on_bridge_copy)
        self._bridge.code_copy_triggered.connect(self._copy_raw_text_to_clipboard)
        self._bridge.all_dismissed.connect(self.all_dismissed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._web)

        self._page.setHtml(BUBBLE_HTML)
        self._page.loadFinished.connect(self._on_load_finished)
        self._loaded = False
        self._last_content_h = 0

        # Pending JS queue — runs once page is loaded
        self._pending_js: list[str] = []

        logger.info("BubbleWindow created (Chromium renderer)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_streaming(self, item_id: str, initial_text: str = "") -> None:
        """Add a new bubble item in streaming mode."""
        js = f"addItem({self._js_str(item_id)}, {self._js_str(initial_text)}, true);"
        self._run_js(js)

    def update_text(self, item_id: str, text: str) -> None:
        """Update text of an existing streaming item."""
        js = f"updateItem({self._js_str(item_id)}, {self._js_str(text)}, true);"
        self._run_js(js)

    def finalize(self, item_id: str, dismiss_after_ms: int = 60_000) -> None:
        """End streaming, remove cursor, start auto-dismiss timer."""
        js = (
            f"finalizeItem({self._js_str(item_id)});"
            f"startDismissTimer({self._js_str(item_id)}, {int(dismiss_after_ms)});"
        )
        self._run_js(js)

    def set_message(self, item_id: str, text: str, dismiss_after_ms: int = 60_000) -> None:
        """Add a non-streaming item and immediately finalize it."""
        js = (
            f"addItem({self._js_str(item_id)}, {self._js_str(text)}, false);"
            f"startDismissTimer({self._js_str(item_id)}, {int(dismiss_after_ms)});"
        )
        self._run_js(js)

    def set_buttons(self, item_id: str, buttons: list[str]) -> None:
        """Add action buttons to an item."""
        buttons_json = json.dumps(buttons)
        js = f"setButtons({self._js_str(item_id)}, {self._js_str(buttons_json)});"
        self._run_js(js)

    def dismiss(self, item_id: str) -> None:
        """Programmatically dismiss a bubble item."""
        self._run_js(f"removeItem({self._js_str(item_id)});")

    def pin(self, item_id: str) -> None:
        """Pin an item (cancel auto-dismiss)."""
        self._run_js(f"pinItem({self._js_str(item_id)});")

    def clear(self) -> None:
        """Remove all bubble items."""
        self._run_js("clearAll();")

    def _dismiss_oldest(self) -> None:
        """Dismiss the oldest bubble item (unpinned first, then pinned)."""
        self._run_js("dismissOldest();")

    def _pin_newest(self) -> None:
        """Pin the most recent unpinned bubble item."""
        self._run_js("pinNewest();")

    def copy_newest(self) -> None:
        """Copy the most recent bubble item to the system clipboard."""
        self._run_js("copyNewest();")

    def set_max_height(self, h: int) -> None:
        """Set max window height and update CSS content max-height accordingly."""
        self._max_window_height = h
        content_h = max(h - 16, 100)
        self._run_js(
            f"document.documentElement.style.setProperty('--max-content-height', '{content_h}px');"
        )

    def show_bubble(self) -> None:
        self.show()
        logger.debug("Bubble shown")

    def hide_bubble(self) -> None:
        self.hide()
        logger.debug("Bubble hidden")

    def is_bubble_visible(self) -> bool:
        return self.isVisible()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            logger.error("BubbleWindow: page load failed")
            return
        self._loaded = True
        for js in self._pending_js:
            self._page.runJavaScript(js)
        self._pending_js.clear()
        logger.debug(f"BubbleWindow: page loaded, flushed {len(self._pending_js)} pending JS calls")

    def _run_js(self, js: str) -> None:
        if self._loaded:
            self._page.runJavaScript(js)
        else:
            self._pending_js.append(js)

    def _on_content_sized(self, h: int) -> None:
        if h > 0:
            new_h = min(max(h + 16, 60), self._max_window_height)
            if new_h != self._last_content_h:
                self._last_content_h = new_h
                self.resize(self.width(), new_h)
                self.content_sized.emit(new_h)
                logger.debug(f"Bubble content height: {h} -> window height {new_h}")

    def _on_bridge_dismiss(self, item_id: str) -> None:
        self._run_js(f"removeItem({self._js_str(item_id)});")

    def _on_bridge_pin(self, item_id: str) -> None:
        self._run_js(f"pinItem({self._js_str(item_id)});")

    def _on_bridge_copy(self, item_id: str) -> None:
        js = f"(_items[{self._js_str(item_id)}] && _items[{self._js_str(item_id)}].rawText) || '';"
        self._page.runJavaScript(js, lambda text: self._copy_text_to_clipboard(item_id, text))

    @staticmethod
    def _copy_raw_text_to_clipboard(text: str) -> None:
        QGuiApplication.clipboard().setText(text or "")

    def _copy_text_to_clipboard(self, item_id: str, text: str) -> None:
        self._copy_raw_text_to_clipboard(text)
        self._run_js(f"flashCopyButton({self._js_str(item_id)});")

    @staticmethod
    def _js_str(text: str) -> str:
        """Escape a Python string for safe embedding in a JS string literal."""
        escaped = (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
            .replace("\0", "")
        )
        return f'"{escaped}"'
