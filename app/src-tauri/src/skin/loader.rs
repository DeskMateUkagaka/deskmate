use std::collections::HashMap;
use std::path::{Path, PathBuf};
use tauri::Manager;

use super::types::{SkinInfo, SkinManifest, EXPRESSIONS};

pub struct SkinManager {
    skins_dir: PathBuf,
    skins: HashMap<String, LoadedSkin>,
    current_skin_id: String,
}

struct LoadedSkin {
    info: SkinInfo,
    manifest: SkinManifest,
    base_path: PathBuf,
}

impl SkinManager {
    pub fn new(app: &tauri::AppHandle) -> Self {
        // In dev mode, skins are relative to the project root
        // In production, they're in the resource directory
        let skins_dir = if cfg!(debug_assertions) {
            let mut dir = std::env::current_dir().unwrap_or_default();
            // cargo-tauri runs from src-tauri, so go up one level
            if dir.ends_with("src-tauri") {
                dir = dir.parent().unwrap_or(&dir).to_path_buf();
            }
            dir.join("skins")
        } else {
            app.path()
                .resource_dir()
                .unwrap_or_else(|_| PathBuf::from("."))
                .join("skins")
        };

        log::info!("Skins directory: {}", skins_dir.display());

        let mut manager = Self {
            skins_dir,
            skins: HashMap::new(),
            current_skin_id: "default".to_string(),
        };
        manager.scan_skins();
        manager
    }

    fn scan_skins(&mut self) {
        self.skins.clear();

        if !self.skins_dir.exists() {
            log::warn!("Skins directory not found: {}", self.skins_dir.display());
            return;
        }

        let entries = match std::fs::read_dir(&self.skins_dir) {
            Ok(e) => e,
            Err(e) => {
                log::error!("Failed to read skins dir: {}", e);
                return;
            }
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_dir() {
                continue;
            }

            let manifest_path = path.join("manifest.json");
            if !manifest_path.exists() {
                continue;
            }

            let skin_id = path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();

            match Self::load_skin(&skin_id, &path) {
                Ok(skin) => {
                    log::info!("Loaded skin: {} ({})", skin.info.name, skin_id);
                    self.skins.insert(skin_id, skin);
                }
                Err(e) => {
                    log::warn!("Failed to load skin at {}: {}", path.display(), e);
                }
            }
        }
    }

    fn load_skin(id: &str, path: &Path) -> Result<LoadedSkin, String> {
        let manifest_path = path.join("manifest.json");
        let contents = std::fs::read_to_string(&manifest_path)
            .map_err(|e| format!("Failed to read manifest: {}", e))?;
        let manifest: SkinManifest =
            serde_json::from_str(&contents).map_err(|e| format!("Invalid manifest JSON: {}", e))?;

        // Validate that all required expressions have PNGs
        for expr in EXPRESSIONS {
            let png_name = manifest
                .expressions
                .get(*expr)
                .ok_or_else(|| format!("Missing expression '{}' in manifest", expr))?;
            let png_path = path.join(png_name);
            if !png_path.exists() {
                return Err(format!(
                    "Missing PNG for expression '{}': {}",
                    expr,
                    png_path.display()
                ));
            }
        }

        Ok(LoadedSkin {
            info: SkinInfo {
                id: id.to_string(),
                name: manifest.name.clone(),
                author: manifest.author.clone(),
                version: manifest.version.clone(),
                path: path.to_string_lossy().to_string(),
                height_percent: manifest.height_percent,
                bubble_placement: manifest.bubble_placement.clone(),
                input_placement: manifest.input_placement.clone(),
            },
            manifest,
            base_path: path.to_path_buf(),
        })
    }

    pub fn list_skins(&self) -> Vec<SkinInfo> {
        self.skins.values().map(|s| s.info.clone()).collect()
    }

    pub fn get_current_skin(&self) -> Option<SkinInfo> {
        self.skins.get(&self.current_skin_id).map(|s| s.info.clone())
    }

    pub fn switch_skin(&mut self, skin_id: &str) -> Result<(), String> {
        if !self.skins.contains_key(skin_id) {
            return Err(format!("Skin '{}' not found", skin_id));
        }
        self.current_skin_id = skin_id.to_string();
        log::info!("Switched to skin: {}", skin_id);
        Ok(())
    }

    pub fn get_expression_path(&self, expression: &str) -> Result<String, String> {
        let skin = self
            .skins
            .get(&self.current_skin_id)
            .ok_or_else(|| format!("Current skin '{}' not loaded", self.current_skin_id))?;

        let expr = if skin.manifest.expressions.contains_key(expression) {
            expression
        } else {
            "neutral"
        };

        let png_name = skin
            .manifest
            .expressions
            .get(expr)
            .ok_or_else(|| format!("Expression '{}' not in manifest", expr))?;

        let full_path = skin.base_path.join(png_name);
        Ok(full_path.to_string_lossy().to_string())
    }
}
