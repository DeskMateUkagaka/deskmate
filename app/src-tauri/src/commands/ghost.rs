use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use std::io::Write;
use tauri::State;

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
    app.exit(0);
}

#[tauri::command]
pub fn debug_log(content: String) {
    use std::fs::OpenOptions;
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open("/tmp/ukagaka.log") {
        let _ = f.write_all(content.as_bytes());
    }
}
