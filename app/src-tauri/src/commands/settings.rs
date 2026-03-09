use std::sync::Mutex;
use tauri::State;

use crate::settings::Settings;

#[tauri::command]
pub fn get_settings(settings: State<Mutex<Settings>>) -> Settings {
    settings.lock().unwrap().clone()
}

#[tauri::command]
pub fn update_settings(
    new_settings: Settings,
    settings: State<Mutex<Settings>>,
    app: tauri::AppHandle,
) {
    let mut s = settings.lock().unwrap();
    *s = new_settings;
    s.save(&app);
}
