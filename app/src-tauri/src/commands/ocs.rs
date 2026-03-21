use std::sync::Mutex;
use tauri::State;

use crate::ocs::client;
use crate::ocs::types::{OcsBrowseParams, OcsResponse};
use crate::skin::SkinManager;

#[tauri::command]
pub async fn ocs_browse(
    params: OcsBrowseParams,
    client: State<'_, reqwest::Client>,
) -> Result<OcsResponse, String> {
    client::browse(&client, params).await
}

#[tauri::command]
pub async fn ocs_download_skin(
    content_id: String,
    download_url: String,
    filename: String,
    app: tauri::AppHandle,
    client: State<'_, reqwest::Client>,
    skin_manager: State<'_, Mutex<SkinManager>>,
) -> Result<String, String> {
    // 1. Download ZIP to temp dir
    let temp_dir = std::env::temp_dir().join("deskmate-downloads");
    std::fs::create_dir_all(&temp_dir).map_err(|e| e.to_string())?;
    let zip_path = temp_dir.join(&filename);

    client::download_to_file(&client, &download_url, &zip_path, &app).await?;

    // 2. Extract + validate via SkinManager
    let skin_id = {
        let mut sm = skin_manager.lock().map_err(|e| e.to_string())?;
        sm.install_skin(&zip_path)?
    };

    // 3. Clean up temp file
    let _ = std::fs::remove_file(&zip_path);

    log::info!("Installed skin from Pling: {} (content_id={})", skin_id, content_id);
    Ok(skin_id)
}

#[tauri::command]
pub fn get_installed_skin_ids(
    skin_manager: State<'_, Mutex<SkinManager>>,
) -> Vec<String> {
    let sm = skin_manager.lock().unwrap();
    sm.installed_skin_ids()
}
