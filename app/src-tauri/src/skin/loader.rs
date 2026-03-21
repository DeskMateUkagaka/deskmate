use std::collections::HashMap;
use std::io::Read;
use std::path::{Path, PathBuf};
use tauri::Manager;

use super::types::{SkinInfo, SkinManifest};

pub struct SkinManager {
    skins_dir: PathBuf,
    user_skins_dir: PathBuf,
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

        let user_skins_dir = app.path()
            .app_data_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join("skins");
        if !user_skins_dir.exists() {
            if let Err(e) = std::fs::create_dir_all(&user_skins_dir) {
                log::warn!("Failed to create user skins dir: {}", e);
            }
        }
        log::info!("User skins directory: {}", user_skins_dir.display());

        let mut manager = Self {
            skins_dir,
            user_skins_dir,
            skins: HashMap::new(),
            current_skin_id: "default".to_string(),
        };
        manager.scan_skins();
        manager
    }

    fn scan_skins(&mut self) {
        self.skins.clear();
        self.scan_dir(&self.skins_dir.clone(), "bundled");
        self.scan_dir(&self.user_skins_dir.clone(), "community");
    }

    fn scan_dir(&mut self, dir: &Path, source: &str) {
        if !dir.exists() {
            log::warn!("Skins directory not found: {}", dir.display());
            return;
        }

        let entries = match std::fs::read_dir(dir) {
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

            if !path.join("manifest.yaml").exists() {
                continue;
            }

            let skin_id = path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();

            match Self::load_skin(&skin_id, &path, source) {
                Ok(skin) => {
                    log::info!("Loaded skin: {} ({}) [{}]", skin.info.name, skin_id, source);
                    self.skins.insert(skin_id, skin);
                }
                Err(e) => {
                    log::warn!("Failed to load skin at {}: {}", path.display(), e);
                }
            }
        }
    }

    fn load_skin(id: &str, path: &Path, source: &str) -> Result<LoadedSkin, String> {
        let manifest_path = path.join("manifest.yaml");
        let contents = std::fs::read_to_string(&manifest_path)
            .map_err(|e| format!("Failed to read manifest: {}", e))?;
        let manifest: SkinManifest =
            serde_yaml::from_str(&contents).map_err(|e| format!("Invalid manifest YAML: {}", e))?;

        // Validate that 'neutral' emotion exists (required for all skins)
        if !manifest.emotions.contains_key("neutral") {
            return Err("Missing required emotion 'neutral' in manifest".to_string());
        }

        // Validate that all declared emotion PNGs exist on disk
        for (emotion, png_name) in &manifest.emotions {
            let png_path = path.join(png_name);
            if !png_path.exists() {
                return Err(format!(
                    "Missing PNG for emotion '{}': {}",
                    emotion,
                    png_path.display()
                ));
            }
        }

        // Validate idle animation files exist on disk and don't escape the skin directory
        for anim in &manifest.idle_animations {
            let anim_path = path.join(&anim.file);
            if !anim_path.exists() {
                return Err(format!(
                    "Missing idle animation file '{}': {}",
                    anim.file, anim_path.display()
                ));
            }
            // Prevent path traversal via manifest (e.g., file: "../../etc/passwd")
            let canonical = anim_path.canonicalize()
                .map_err(|e| format!("Cannot resolve idle animation path '{}': {}", anim.file, e))?;
            let base_canonical = path.canonicalize()
                .map_err(|e| format!("Cannot resolve skin base path: {}", e))?;
            if !canonical.starts_with(&base_canonical) {
                return Err(format!(
                    "Idle animation '{}' escapes skin directory",
                    anim.file
                ));
            }
            if anim.duration_ms == 0 {
                return Err(format!(
                    "Idle animation '{}' has duration_ms of 0",
                    anim.file
                ));
            }
        }
        if !manifest.idle_animations.is_empty() && manifest.idle_interval_seconds < 1.0 {
            return Err("idle_interval_seconds must be >= 1.0".to_string());
        }

        Ok(LoadedSkin {
            info: SkinInfo {
                id: id.to_string(),
                name: manifest.name.clone(),
                author: manifest.author.clone(),
                version: manifest.version.clone(),
                path: path.to_string_lossy().to_string(),
                emotions: manifest.emotions.keys().cloned().collect(),
                bubble_placement: manifest.bubble_placement.clone(),
                input_placement: manifest.input_placement.clone(),
                bubble_theme: manifest.bubble.clone(),
                input_theme: manifest.input.clone(),
                idle_animations: manifest.idle_animations.clone(),
                idle_interval_seconds: manifest.idle_interval_seconds,
                source: source.to_string(),
                format_version: manifest.format_version,
            },
            manifest,
            base_path: path.to_path_buf(),
        })
    }

    pub fn reload(&mut self) {
        let current = self.current_skin_id.clone();
        self.scan_skins();
        // Keep current skin if it still exists after reload
        if self.skins.contains_key(&current) {
            self.current_skin_id = current;
        }
        log::info!("Reloaded skins from disk");
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

    pub fn get_emotion_path(&self, emotion: &str) -> Result<String, String> {
        let skin = self
            .skins
            .get(&self.current_skin_id)
            .ok_or_else(|| format!("Current skin '{}' not loaded", self.current_skin_id))?;

        let resolved = if skin.manifest.emotions.contains_key(emotion) {
            emotion
        } else {
            log::warn!(
                "Emotion '{}' not found in skin '{}', falling back to neutral",
                emotion,
                self.current_skin_id
            );
            "neutral"
        };

        let png_name = skin
            .manifest
            .emotions
            .get(resolved)
            .ok_or_else(|| format!("Emotion '{}' not in manifest", resolved))?;

        let full_path = skin.base_path.join(png_name);
        Ok(full_path.to_string_lossy().to_string())
    }

    const SUPPORTED_FORMAT_VERSION: u32 = 1;

    pub fn install_skin(&mut self, zip_path: &Path) -> Result<String, String> {
        let file = std::fs::File::open(zip_path)
            .map_err(|e| format!("Failed to open ZIP: {}", e))?;
        let mut archive = zip::ZipArchive::new(file)
            .map_err(|e| format!("Invalid ZIP file: {}", e))?;

        // Find manifest.yaml — check root, then one level deep
        let mut manifest_prefix = String::new();
        let has_root_manifest = (0..archive.len()).any(|i| {
            archive.by_index(i).map(|f| f.name() == "manifest.yaml").unwrap_or(false)
        });

        if !has_root_manifest {
            // Check one subfolder deep
            let mut found = false;
            for i in 0..archive.len() {
                if let Ok(f) = archive.by_index(i) {
                    let name = f.name().to_string();
                    if name.ends_with("/manifest.yaml") && name.matches('/').count() == 1 {
                        manifest_prefix = name.split('/').next().unwrap_or("").to_string() + "/";
                        found = true;
                        break;
                    }
                }
            }
            if !found {
                return Err("No manifest.yaml found in ZIP (checked root and one subfolder deep)".to_string());
            }
        }

        // Pre-validate format version by reading manifest from ZIP
        let manifest_name = format!("{}manifest.yaml", manifest_prefix);
        let manifest_contents = {
            let mut manifest_file = archive.by_name(&manifest_name)
                .map_err(|e| format!("Failed to read manifest from ZIP: {}", e))?;
            let mut contents = String::new();
            manifest_file.read_to_string(&mut contents)
                .map_err(|e| format!("Failed to read manifest contents: {}", e))?;
            contents
        };
        let manifest: crate::skin::types::SkinManifest = serde_yaml::from_str(&manifest_contents)
            .map_err(|e| format!("Invalid manifest YAML in ZIP: {}", e))?;

        if manifest.format_version > Self::SUPPORTED_FORMAT_VERSION {
            return Err(format!(
                "This skin requires DeskMate v{} (you have v1). Please update DeskMate.",
                manifest.format_version
            ));
        }

        // Determine skin_id
        let skin_id = if manifest_prefix.is_empty() {
            zip_path.file_stem().unwrap_or_default().to_string_lossy().to_string()
        } else {
            manifest_prefix.trim_end_matches('/').to_string()
        };

        // Avoid collision with bundled skins
        let skin_id = if self.skins.get(&skin_id).map(|s| s.info.source == "bundled").unwrap_or(false) {
            format!("community-{}", skin_id)
        } else {
            skin_id
        };

        let target_dir = self.user_skins_dir.join(&skin_id);

        // Remove existing if present (overwrite/update)
        if target_dir.exists() {
            std::fs::remove_dir_all(&target_dir)
                .map_err(|e| format!("Failed to remove existing skin: {}", e))?;
        }
        std::fs::create_dir_all(&target_dir)
            .map_err(|e| format!("Failed to create skin dir: {}", e))?;

        // Extract files
        for i in 0..archive.len() {
            let mut file = archive.by_index(i)
                .map_err(|e| format!("Failed to read ZIP entry: {}", e))?;
            let name = file.name().to_string();

            // Skip junk
            if name.contains("__MACOSX") || name.ends_with(".DS_Store") {
                continue;
            }

            // Strip prefix if manifest was in a subfolder
            let relative = if manifest_prefix.is_empty() {
                name.clone()
            } else {
                match name.strip_prefix(&manifest_prefix) {
                    Some(r) => r.to_string(),
                    None => continue,
                }
            };

            if relative.is_empty() {
                continue;
            }

            let out_path = target_dir.join(&relative);
            if file.is_dir() {
                std::fs::create_dir_all(&out_path)
                    .map_err(|e| format!("Failed to create dir: {}", e))?;
            } else {
                if let Some(parent) = out_path.parent() {
                    std::fs::create_dir_all(parent)
                        .map_err(|e| format!("Failed to create parent dir: {}", e))?;
                }
                let mut outfile = std::fs::File::create(&out_path)
                    .map_err(|e| format!("Failed to create file {}: {}", out_path.display(), e))?;
                std::io::copy(&mut file, &mut outfile)
                    .map_err(|e| format!("Failed to write file: {}", e))?;
                log::info!("Extracted: {}", out_path.display());
            }
        }

        // Validate the extracted skin
        let skin = Self::load_skin(&skin_id, &target_dir, "community")?;
        log::info!("Installed skin: {} ({})", skin.info.name, skin_id);
        self.skins.insert(skin_id.clone(), skin);

        Ok(skin_id)
    }

    pub fn installed_skin_ids(&self) -> Vec<String> {
        self.skins.values()
            .filter(|s| s.info.source == "community")
            .map(|s| s.info.id.clone())
            .collect()
    }

    pub fn get_idle_animation_path(&self, filename: &str) -> Result<String, String> {
        let skin = self.skins.get(&self.current_skin_id)
            .ok_or_else(|| format!("Current skin '{}' not loaded", self.current_skin_id))?;
        // Verify the filename is declared in idle_animations (prevent path traversal)
        if !skin.manifest.idle_animations.iter().any(|a| a.file == filename) {
            return Err(format!("'{}' is not a declared idle animation", filename));
        }
        let full_path = skin.base_path.join(filename);
        // Defense-in-depth: verify resolved path stays within skin directory
        let canonical = full_path.canonicalize()
            .map_err(|e| format!("Cannot resolve path '{}': {}", filename, e))?;
        let base_canonical = skin.base_path.canonicalize()
            .map_err(|e| format!("Cannot resolve skin base: {}", e))?;
        if !canonical.starts_with(&base_canonical) {
            return Err(format!("'{}' escapes skin directory", filename));
        }
        Ok(canonical.to_string_lossy().to_string())
    }

    pub fn user_skins_dir(&self) -> &Path {
        &self.user_skins_dir
    }
}
