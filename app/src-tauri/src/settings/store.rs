use serde::{Deserialize, Serialize};
use std::collections::HashMap;
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
    #[serde(default = "default_ghost_height_pixels")]
    pub ghost_height_pixels: u32,
    #[serde(default = "default_popup_margin")]
    pub popup_margin_top: f64,
    #[serde(default = "default_popup_margin")]
    pub popup_margin_bottom: f64,
    #[serde(default = "default_popup_margin")]
    pub popup_margin_left: f64,
    #[serde(default = "default_popup_margin")]
    pub popup_margin_right: f64,
    #[serde(default = "default_idle_interval_seconds")]
    pub idle_interval_seconds: f64,
    #[serde(default)]
    pub quake_terminal: QuakeTerminalConfig,
    #[serde(default = "default_ghost_toggle_hotkey")]
    pub ghost_toggle_hotkey: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuakeTerminalConfig {
    #[serde(default = "default_quake_enabled")]
    pub enabled: bool,
    #[serde(default = "default_quake_hotkey")]
    pub hotkey: String,
    #[serde(default)]
    pub terminal_emulator: Option<String>,
    #[serde(default = "default_quake_command")]
    pub command: String,
    #[serde(default = "default_quake_height_percent")]
    pub height_percent: u32,
}

fn default_quake_enabled() -> bool { true }
fn default_quake_hotkey() -> String { "ctrl+alt+`".to_string() }
fn default_quake_command() -> String { "openclaw tui".to_string() }
fn default_quake_height_percent() -> u32 { 40 }

impl Default for QuakeTerminalConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            hotkey: default_quake_hotkey(),
            terminal_emulator: None,
            command: default_quake_command(),
            height_percent: 40,
        }
    }
}

fn default_ghost_toggle_hotkey() -> String { "super+f11".to_string() }
fn default_ghost_height_pixels() -> u32 { 540 }
fn default_popup_margin() -> f64 { 10.0 }
fn default_idle_interval_seconds() -> f64 { 30.0 }

impl Default for Settings {
    fn default() -> Self {
        Self {
            gateway_url: "ws://127.0.0.1:18789".to_string(),
            gateway_token: String::new(),
            bubble_timeout_ms: 60000,
            proactive_enabled: false,
            proactive_interval_mins: 60,
            ghost_x: 100.0,
            ghost_y: 100.0,
            current_skin_id: "default".to_string(),
            ghost_height_pixels: 540,
            popup_margin_top: 10.0,
            popup_margin_bottom: 10.0,
            popup_margin_left: 10.0,
            popup_margin_right: 10.0,
            idle_interval_seconds: 30.0,
            quake_terminal: QuakeTerminalConfig::default(),
            ghost_toggle_hotkey: default_ghost_toggle_hotkey(),
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
        config_dir.join("config.yaml")
    }

    pub fn load(app: &tauri::AppHandle) -> Self {
        let path = Self::settings_path(app);
        if path.exists() {
            match std::fs::read_to_string(&path) {
                Ok(contents) => {
                    log::info!("Loaded settings from {}", path.display());
                    serde_yaml::from_str(&contents).unwrap_or_default()
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

    /// Extract comments from existing YAML so we can reattach them after serialization.
    /// Returns (header, per-key comments, trailer).
    /// Per-key: key → (comment lines preceding the key, inline comment after value).
    fn extract_comments(
        contents: &str,
    ) -> (
        Vec<String>,
        HashMap<String, (Vec<String>, Option<String>)>,
        Vec<String>,
    ) {
        let mut header: Vec<String> = Vec::new();
        let mut key_comments: HashMap<String, (Vec<String>, Option<String>)> = HashMap::new();
        let mut pending: Vec<String> = Vec::new();
        let mut seen_any_key = false;

        for line in contents.lines() {
            let trimmed = line.trim();
            let is_key_line = !line.starts_with(' ')
                && !line.starts_with('\t')
                && trimmed.contains(':')
                && !trimmed.starts_with('#');

            if is_key_line {
                let key = trimmed.split(':').next().unwrap_or("").trim().to_string();
                let inline = trimmed
                    .splitn(2, ':')
                    .nth(1)
                    .and_then(|val| val.find(" #").map(|pos| val[pos..].to_string()));
                seen_any_key = true;
                key_comments.insert(key, (std::mem::take(&mut pending), inline));
            } else if trimmed.is_empty() || trimmed.starts_with('#') {
                if seen_any_key {
                    pending.push(line.to_string());
                } else {
                    header.push(line.to_string());
                }
            }
        }

        (header, key_comments, pending)
    }

    pub fn save(&self, app: &tauri::AppHandle) {
        let path = Self::settings_path(app);
        let existing = std::fs::read_to_string(&path).unwrap_or_default();
        let (header, key_comments, trailer) = Self::extract_comments(&existing);

        match serde_yaml::to_string(self) {
            Ok(yaml) => {
                let mut output = String::new();

                for line in &header {
                    output.push_str(line);
                    output.push('\n');
                }

                for line in yaml.lines() {
                    if line.trim() == "---" {
                        continue;
                    }
                    let key = line.split(':').next().unwrap_or("").trim();
                    if let Some((preceding, inline)) = key_comments.get(key) {
                        for c in preceding {
                            output.push_str(c);
                            output.push('\n');
                        }
                        if let Some(comment) = inline {
                            output.push_str(line);
                            output.push_str(comment);
                            output.push('\n');
                            continue;
                        }
                    }
                    output.push_str(line);
                    output.push('\n');
                }

                for line in &trailer {
                    output.push_str(line);
                    output.push('\n');
                }

                if let Err(e) = std::fs::write(&path, &output) {
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
