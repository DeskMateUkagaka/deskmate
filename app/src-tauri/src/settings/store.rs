use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::Manager;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settings {
    pub gateway_url: String,
    pub gateway_token: String,
    pub bubble_timeout_ms: u64,
    pub proactive_enabled: bool,
    pub proactive_interval_mins: u32,
    pub ghost_x: f64,
    pub ghost_y: f64,
    pub current_skin_id: String,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            gateway_url: "ws://127.0.0.1:18789".to_string(),
            gateway_token: String::new(),
            bubble_timeout_ms: 10000,
            proactive_enabled: false,
            proactive_interval_mins: 60,
            ghost_x: 100.0,
            ghost_y: 100.0,
            current_skin_id: "default".to_string(),
        }
    }
}

impl Settings {
    fn settings_path(app: &tauri::AppHandle) -> PathBuf {
        let config_dir = app
            .path()
            .app_config_dir()
            .expect("failed to get app config dir");
        std::fs::create_dir_all(&config_dir).ok();
        config_dir.join("config.json")
    }

    pub fn load(app: &tauri::AppHandle) -> Self {
        let path = Self::settings_path(app);
        if path.exists() {
            match std::fs::read_to_string(&path) {
                Ok(contents) => {
                    log::info!("Loaded settings from {}", path.display());
                    serde_json::from_str(&contents).unwrap_or_default()
                }
                Err(e) => {
                    log::warn!("Failed to read settings file: {}", e);
                    Self::default()
                }
            }
        } else {
            log::info!("No settings file found, using defaults");
            Self::default()
        }
    }

    pub fn save(&self, app: &tauri::AppHandle) {
        let path = Self::settings_path(app);
        match serde_json::to_string_pretty(self) {
            Ok(json) => {
                if let Err(e) = std::fs::write(&path, &json) {
                    log::error!("Failed to write settings to {}: {}", path.display(), e);
                } else {
                    log::info!("Saved settings to {}", path.display());
                }
            }
            Err(e) => {
                log::error!("Failed to serialize settings: {}", e);
            }
        }
    }
}
