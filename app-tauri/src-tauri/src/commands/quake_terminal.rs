use std::sync::{Arc, Mutex};

use tauri::State;

use crate::quake_terminal::QuakeTerminalState;
use crate::settings::Settings;

#[tauri::command]
pub fn toggle_quake_terminal(
    qt_state: State<Arc<Mutex<QuakeTerminalState>>>,
    settings: State<std::sync::Mutex<Settings>>,
    app: tauri::AppHandle,
) -> Result<bool, String> {
    let config = settings.lock().unwrap().quake_terminal.clone();
    let mut state = qt_state.lock().map_err(|e| format!("Lock error: {e}"))?;
    crate::quake_terminal::toggle::toggle(&mut state, &config, &app)?;
    Ok(state.visible)
}

#[tauri::command]
pub fn get_quake_terminal_status(
    qt_state: State<Arc<Mutex<QuakeTerminalState>>>,
) -> bool {
    qt_state.lock().map(|s| s.visible).unwrap_or(false)
}
