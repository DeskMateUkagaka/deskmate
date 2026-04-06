#!/usr/bin/env python3
"""Interactive Live2D model viewer for previewing motions and expressions.

Usage:
    python scripts/live2d_viewer.py path/to/Character.model3.json
    python scripts/live2d_viewer.py app/skins/live2d-hiyori/model/Hiyori/Hiyori.model3.json

Renders the model in a window with clickable buttons for every motion group/index
and expression found in the .model3.json. Useful for authoring manifest.yaml mappings.
"""

import json
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QColor
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

# Resolve paths
SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = SCRIPT_DIR.parent / "app"
LIB_DIR = APP_DIR / "lib" / "live2d"


def _file_url(path: Path) -> str:
    return QUrl.fromLocalFile(str(path)).toString()


def build_html() -> str:
    pixi = _file_url(LIB_DIR / "pixi.min.js")
    cubism_core = _file_url(LIB_DIR / "live2dcubismcore.min.js")
    cubism4 = _file_url(LIB_DIR / "cubism4.min.js")
    live2d_display = _file_url(LIB_DIR / "pixi-live2d-display.min.js")

    return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="{pixi}"></script>
<script src="{cubism_core}"></script>
<script src="{cubism4}"></script>
<script src="{live2d_display}"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
    background: #2b2b2b;
    overflow: hidden;
    width: 100vw;
    height: 100vh;
}}
#status {{
    position: absolute;
    bottom: 8px;
    left: 8px;
    color: #aaa;
    font: 12px monospace;
    z-index: 10;
    pointer-events: none;
}}
</style>
</head>
<body>
<div id="status">Loading model...</div>
<script>
let app = null;
let model = null;

async function loadModel(url) {{
    try {{
        app = new PIXI.Application({{
            view: document.createElement('canvas'),
            backgroundAlpha: 0,
            resizeTo: window,
            antialias: true,
        }});
        document.body.insertBefore(app.view, document.getElementById('status'));

        model = await PIXI.live2d.Live2DModel.from(url);
        model.anchor.set(0.5, 0.5);

        const s = (window.innerHeight / model.height) * 0.9;
        model.scale.set(s, s);
        model.x = window.innerWidth / 2;
        model.y = window.innerHeight / 2;

        app.stage.addChild(model);
        document.getElementById('status').textContent = 'Model loaded';

        window.addEventListener('resize', () => {{
            if (!model) return;
            const ns = (window.innerHeight / model.height) * 0.9;
            model.scale.set(ns, ns);
            model.x = window.innerWidth / 2;
            model.y = window.innerHeight / 2;
        }});
    }} catch (e) {{
        document.getElementById('status').textContent = 'Error: ' + e;
        console.error(e);
    }}
}}

function triggerMotion(group, index) {{
    if (!model) return;
    document.getElementById('status').textContent = 'Motion: ' + group + '[' + index + ']';
    model.motion(group, index);
}}

function setExpression(id) {{
    if (!model) return;
    document.getElementById('status').textContent = 'Expression: ' + id;
    model.expression(id);
}}
</script>
</body>
</html>"""


def parse_model(model_path: Path) -> dict:
    """Parse .model3.json and return motions and expressions."""
    with open(model_path) as f:
        data = json.load(f)

    refs = data.get("FileReferences", {})

    motions: dict[str, int] = {}
    for group, entries in refs.get("Motions", {}).items():
        motions[group] = len(entries)

    expressions: list[str] = []
    for entry in refs.get("Expressions", []):
        name = entry.get("Name", "")
        if name:
            expressions.append(name)

    return {"motions": motions, "expressions": expressions}


class ViewerWindow(QWidget):
    def __init__(self, model_path: Path) -> None:
        super().__init__()
        self.model_path = model_path.resolve()
        self.setWindowTitle(f"Live2D Viewer — {model_path.name}")
        self.resize(1100, 700)

        parsed = parse_model(self.model_path)

        # Layout: splitter with webview (left) and control panel (right)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        # WebView
        self.webview = QWebEngineView()
        page = self.webview.page()
        page.setBackgroundColor(QColor(43, 43, 43))
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)

        html = build_html()
        self.webview.setHtml(html, QUrl.fromLocalFile(str(self.model_path.parent) + "/"))
        self.webview.loadFinished.connect(self._on_page_loaded)

        splitter.addWidget(self.webview)

        # Control panel
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)

        # Model info
        info = QLabel(f"<b>{model_path.name}</b>")
        info.setWordWrap(True)
        panel_layout.addWidget(info)

        # Scrollable area for buttons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Motion groups
        if parsed["motions"]:
            for group, count in sorted(parsed["motions"].items()):
                group_box = QGroupBox(f"Motion: {group} ({count})")
                group_layout = QVBoxLayout(group_box)
                for i in range(count):
                    btn = QPushButton(f"{group}[{i}]")
                    btn.clicked.connect(self._make_motion_handler(group, i))
                    group_layout.addWidget(btn)
                scroll_layout.addWidget(group_box)
        else:
            scroll_layout.addWidget(QLabel("No motions found"))

        # Expressions
        if parsed["expressions"]:
            exp_box = QGroupBox(f"Expressions ({len(parsed['expressions'])})")
            exp_layout = QVBoxLayout(exp_box)
            for name in parsed["expressions"]:
                btn = QPushButton(name)
                btn.clicked.connect(self._make_expression_handler(name))
                exp_layout.addWidget(btn)
            scroll_layout.addWidget(exp_box)

        # YAML helper
        scroll_layout.addStretch()
        hint = QLabel(
            "<i>Click a button to preview.<br>"
            "Use group + index in your<br>"
            "manifest.yaml mapping.</i>"
        )
        hint.setWordWrap(True)
        scroll_layout.addWidget(hint)

        scroll.setWidget(scroll_content)
        panel_layout.addWidget(scroll)

        panel.setMinimumWidth(200)
        panel.setMaximumWidth(300)
        splitter.addWidget(panel)
        splitter.setSizes([800, 300])

    def _on_page_loaded(self, ok: bool) -> None:
        if not ok:
            print("Failed to load HTML page")
            return
        model_url = QUrl.fromLocalFile(str(self.model_path)).toString()
        self.webview.page().runJavaScript(f'loadModel("{model_url}")')

    def _make_motion_handler(self, group: str, index: int):
        def handler():
            js = f'triggerMotion("{group}", {index})'
            self.webview.page().runJavaScript(js)
            print(f"  motion_group: \"{group}\", motion_index: {index}")
        return handler

    def _make_expression_handler(self, name: str):
        def handler():
            js = f'setExpression("{name}")'
            self.webview.page().runJavaScript(js)
            print(f"  expression: \"{name}\"")
        return handler


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/live2d_viewer.py <path/to/model.model3.json>")
        sys.exit(1)

    model_path = Path(sys.argv[1])
    if not model_path.exists():
        print(f"File not found: {model_path}")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = ViewerWindow(model_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
