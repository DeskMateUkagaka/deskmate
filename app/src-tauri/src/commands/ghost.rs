use serde::{Deserialize, Serialize};
use std::sync::Mutex;
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
