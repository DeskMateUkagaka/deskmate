use std::sync::Mutex;
use tauri::State;

use crate::skin::{SkinInfo, SkinManager};

#[tauri::command]
pub fn list_skins(skin_manager: State<Mutex<SkinManager>>) -> Vec<SkinInfo> {
    let sm = skin_manager.lock().unwrap();
    sm.list_skins()
}

#[tauri::command]
pub fn get_current_skin(skin_manager: State<Mutex<SkinManager>>) -> Option<SkinInfo> {
    let sm = skin_manager.lock().unwrap();
    sm.get_current_skin()
}

#[tauri::command]
pub fn switch_skin(
    skin_id: String,
    skin_manager: State<Mutex<SkinManager>>,
    settings: State<Mutex<crate::settings::Settings>>,
    app: tauri::AppHandle,
) -> Result<(), String> {
    let mut sm = skin_manager.lock().unwrap();
    sm.switch_skin(&skin_id)?;
    let mut s = settings.lock().unwrap();
    s.current_skin_id = skin_id;
    s.save(&app);
    Ok(())
}

#[tauri::command]
pub fn reload_skins(skin_manager: State<Mutex<SkinManager>>) {
    let mut sm = skin_manager.lock().unwrap();
    sm.reload();
}

#[tauri::command]
pub fn get_emotion_image(
    emotion: String,
    skin_manager: State<Mutex<SkinManager>>,
) -> Result<String, String> {
    let sm = skin_manager.lock().unwrap();
    sm.get_emotion_path(&emotion)
}

#[tauri::command]
pub fn get_emotion_images(
    emotion: String,
    skin_manager: State<Mutex<SkinManager>>,
) -> Result<Vec<String>, String> {
    let sm = skin_manager.lock().unwrap();
    sm.get_emotion_paths(&emotion)
}

#[tauri::command]
pub fn get_idle_animation_path(
    filename: String,
    skin_manager: State<Mutex<SkinManager>>,
) -> Result<String, String> {
    let sm = skin_manager.lock().unwrap();
    sm.get_idle_animation_path(&filename)
}
