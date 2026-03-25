#!/bin/bash
rm -f /tmp/debug.log
WEBKIT_DISABLE_COMPOSITING_MODE=1 cargo tauri dev
