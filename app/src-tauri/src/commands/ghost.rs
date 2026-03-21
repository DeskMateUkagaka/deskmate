use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use std::io::Write;
use tauri::{Manager, State};

use crate::settings::Settings;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GhostPosition {
    pub x: f64,
    pub y: f64,
}

#[tauri::command]
pub fn get_ghost_position(settings: State<Mutex<Settings>>) -> GhostPosition {
    let s = settings.lock().unwrap();
    GhostPosition {
        x: s.ghost_x,
        y: s.ghost_y,
    }
}

#[tauri::command]
pub fn set_ghost_position(
    x: f64,
    y: f64,
    settings: State<Mutex<Settings>>,
    app: tauri::AppHandle,
) {
    let mut s = settings.lock().unwrap();
    s.ghost_x = x;
    s.ghost_y = y;
    s.save(&app);
}

#[tauri::command]
pub fn exit_app(app: tauri::AppHandle) {
    // Kill quake terminal if active — use try_state() so this works
    // even if QuakeTerminalState was never registered (e.g., feature disabled)
    if let Some(qt_state) = app.try_state::<Arc<Mutex<crate::quake_terminal::QuakeTerminalState>>>() {
        if let Ok(mut qt) = qt_state.lock() {
            if let Some(ref mut child) = qt.process {
                let _ = child.kill();
            }
        }
    }
    app.exit(0);
}

#[tauri::command]
pub fn debug_log(content: String) {
    use std::fs::OpenOptions;
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open("/tmp/deskmate.log") {
        let _ = f.write_all(content.as_bytes());
    }
}
