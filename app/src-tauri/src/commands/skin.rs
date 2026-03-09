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
pub fn switch_skin(skin_id: String, skin_manager: State<Mutex<SkinManager>>) -> Result<(), String> {
    let mut sm = skin_manager.lock().unwrap();
    sm.switch_skin(&skin_id)
}

#[tauri::command]
pub fn get_expression_image(
    expression: String,
    skin_manager: State<Mutex<SkinManager>>,
) -> Result<String, String> {
    let sm = skin_manager.lock().unwrap();
    sm.get_expression_path(&expression)
}
