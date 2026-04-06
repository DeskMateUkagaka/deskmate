"""WASM Loading Spike for QWebEngineView (PySide6/Qt6).

Tests whether QWebEngineView can load and execute WebAssembly in the context
needed for Live2D Cubism SDK integration.

Four tests run sequentially:
  1. WebAssembly API available?
  2. Inline base64 WASM instantiation
  3. fetch() with file:// URL
  4. XMLHttpRequest with file:// URL

Run with: python3 app/spike_wasm.py
"""

import base64
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Minimal WASM binary: exports an `add(i32, i32) -> i32` function.
#
# Hand-assembled WAT:
#   (module
#     (func $add (export "add") (param i32 i32) (result i32)
#       local.get 0
#       local.get 1
#       i32.add))
#
# Encoded as bytes (magic + version + type section + function section +
# export section + code section):
WASM_BYTES = bytes([
    0x00, 0x61, 0x73, 0x6D,  # magic: \0asm
    0x01, 0x00, 0x00, 0x00,  # version: 1
    # Type section (id=1): one type: (i32, i32) -> i32
    0x01, 0x07, 0x01, 0x60, 0x02, 0x7F, 0x7F, 0x01, 0x7F,
    # Function section (id=3): one function, type index 0
    0x03, 0x02, 0x01, 0x00,
    # Export section (id=7): export "add" as function 0
    0x07, 0x07, 0x01, 0x03, 0x61, 0x64, 0x64, 0x00, 0x00,
    # Code section (id=10): one function body
    0x0A, 0x09, 0x01, 0x07, 0x00,
    0x20, 0x00,  # local.get 0
    0x20, 0x01,  # local.get 1
    0x6A,        # i32.add
    0x0B,        # end
])

WASM_B64 = base64.b64encode(WASM_BYTES).decode()


def _build_html(wasm_file_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
<script>
// ---- bridge setup ----
let bridge = null;
new QWebChannel(qt.webChannelTransport, function(ch) {{
    bridge = ch.objects.bridge;
    runTests();
}});

function report(name, passed, detail) {{
    if (bridge) bridge.onResult(name, passed, detail || "");
}}

// ---- Test 1: WebAssembly API available ----
function testWasmApi() {{
    if (typeof WebAssembly === "object" && typeof WebAssembly.instantiate === "function") {{
        report("T1_WASM_API", true, "WebAssembly object present");
    }} else {{
        report("T1_WASM_API", false, "WebAssembly not defined");
    }}
}}

// ---- Test 2: Inline base64 WASM instantiation ----
function testInlineWasm() {{
    const b64 = "{WASM_B64}";
    const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    WebAssembly.instantiate(bin).then(result => {{
        const add = result.instance.exports.add;
        const val = add(3, 4);
        if (val === 7) {{
            report("T2_INLINE_WASM", true, "add(3,4)=" + val);
        }} else {{
            report("T2_INLINE_WASM", false, "add(3,4)=" + val + " (expected 7)");
        }}
    }}).catch(e => {{
        report("T2_INLINE_WASM", false, String(e));
    }});
}}

// ---- Test 3: fetch() file:// URL ----
function testFetchFileUrl() {{
    const url = "{wasm_file_url}";
    fetch(url).then(r => {{
        if (!r.ok) {{
            report("T3_FETCH_FILE", false, "HTTP status " + r.status);
            return null;
        }}
        return r.arrayBuffer();
    }}).then(buf => {{
        if (!buf) return;
        return WebAssembly.instantiate(buf);
    }}).then(result => {{
        if (!result) return;
        const val = result.instance.exports.add(10, 20);
        report("T3_FETCH_FILE", val === 30, "add(10,20)=" + val);
    }}).catch(e => {{
        report("T3_FETCH_FILE", false, String(e));
    }});
}}

// ---- Test 4: XMLHttpRequest file:// URL ----
function testXhrFileUrl() {{
    const url = "{wasm_file_url}";
    const xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    xhr.responseType = "arraybuffer";
    xhr.onload = function() {{
        if (xhr.status !== 200 && xhr.status !== 0) {{
            report("T4_XHR_FILE", false, "XHR status " + xhr.status);
            return;
        }}
        WebAssembly.instantiate(xhr.response).then(result => {{
            const val = result.instance.exports.add(5, 6);
            report("T4_XHR_FILE", val === 11, "add(5,6)=" + val);
        }}).catch(e => {{
            report("T4_XHR_FILE", false, String(e));
        }});
    }};
    xhr.onerror = function() {{
        report("T4_XHR_FILE", false, "XHR network error");
    }};
    xhr.send();
}}

function runTests() {{
    testWasmApi();
    testInlineWasm();
    testFetchFileUrl();
    testXhrFileUrl();
}}
</script>
</body>
</html>"""


class _Bridge(QObject):
    result_received = Signal(str, bool, str)

    @Slot(str, bool, str)
    def onResult(self, name: str, passed: bool, detail: str):
        self.result_received.emit(name, passed, detail)


EXPECTED_TESTS = {"T1_WASM_API", "T2_INLINE_WASM", "T3_FETCH_FILE", "T4_XHR_FILE"}

TEST_LABELS = {
    "T1_WASM_API":    "Test 1 — WebAssembly API available",
    "T2_INLINE_WASM": "Test 2 — Inline base64 WASM instantiation",
    "T3_FETCH_FILE":  "Test 3 — fetch() with file:// URL",
    "T4_XHR_FILE":    "Test 4 — XMLHttpRequest with file:// URL",
}


def main():
    app = QApplication(sys.argv)

    # Write the WASM file to a temp location so we can test file:// loading.
    tmp_dir = tempfile.mkdtemp(prefix="spike_wasm_")
    wasm_path = Path(tmp_dir) / "add.wasm"
    wasm_path.write_bytes(WASM_BYTES)
    wasm_file_url = QUrl.fromLocalFile(str(wasm_path)).toString()
    print(f"[spike] WASM test file: {wasm_path}")
    print(f"[spike] file:// URL:    {wasm_file_url}")
    print()

    # Build the view (mirrors ghost.py setup).
    view = QWebEngineView()
    page = QWebEnginePage(view)
    view.setPage(page)

    settings = page.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
    # JavascriptEnabled is on by default; be explicit.
    settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

    bridge = _Bridge()
    channel = QWebChannel(page)
    channel.registerObject("bridge", bridge)
    page.setWebChannel(channel)

    results: dict[str, tuple[bool, str]] = {}

    def on_result(name: str, passed: bool, detail: str):
        results[name] = (passed, detail)
        status = "PASS" if passed else "FAIL"
        label = TEST_LABELS.get(name, name)
        print(f"  [{status}] {label}")
        if detail:
            print(f"         detail: {detail}")

        if results.keys() >= EXPECTED_TESTS:
            finish()

    bridge.result_received.connect(on_result)

    # Safety timeout: if not all results arrive within 10s, report what we have.
    def timeout_handler():
        missing = EXPECTED_TESTS - results.keys()
        if missing:
            for name in sorted(missing):
                label = TEST_LABELS.get(name, name)
                print(f"  [TIMEOUT] {label} — no response from JS")
                results[name] = (False, "timeout")
        finish()

    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.setInterval(10_000)
    timeout.timeout.connect(timeout_handler)

    def finish():
        timeout.stop()
        print()
        print("=" * 60)
        passed_count = sum(1 for p, _ in results.values() if p)
        total = len(EXPECTED_TESTS)
        print(f"Results: {passed_count}/{total} passed")
        print()

        # Summary guidance for Live2D integration decision.
        t2 = results.get("T2_INLINE_WASM", (False, ""))[0]
        t3 = results.get("T3_FETCH_FILE", (False, ""))[0]
        t4 = results.get("T4_XHR_FILE", (False, ""))[0]

        print("Live2D Cubism integration feasibility:")
        if t3:
            print("  GO  — fetch() works with file://. Cubism SDK can load its WASM unchanged.")
        elif t4:
            print("  GO* — fetch() blocked, but XHR works. Cubism SDK loader needs a small patch")
            print("        to use XHR instead of fetch for the .wasm file.")
        elif t2:
            print("  GO* — Both fetch() and XHR blocked. Must pre-load WASM as base64 and pass")
            print("        the ArrayBuffer directly to WebAssembly.instantiate().")
            print("        Cubism SDK loader needs a wrapper shim injected before sdk.js runs.")
        else:
            print("  NO-GO — WebAssembly itself is broken in this build of QWebEngineView.")
            print("          Live2D Cubism integration is not feasible without a Qt rebuild.")
        print("=" * 60)

        app.quit()

    html = _build_html(wasm_file_url)
    # Use file:/// base URL so same-origin checks treat it as a local file context,
    # matching how ghost.py calls setHtml().
    page.setHtml(html, QUrl("file:///"))

    print("[spike] Loading test page...")
    print()
    print("Test results:")

    view.resize(400, 300)
    view.show()

    timeout.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
