use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub const EXPRESSIONS: &[&str] = &[
    "happy",
    "sad",
    "angry",
    "disgusted",
    "condescending",
    "thinking",
    "uwamezukai",
    "neutral",
];

/// UI element placement: pixel offset from ghost image center + screen-edge margins.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UiPlacement {
    /// Horizontal offset from image center (px)
    #[serde(default)]
    pub x: f64,
    /// Vertical offset from image center (px, negative = above)
    #[serde(default)]
    pub y: f64,
    /// Minimum horizontal distance from screen edge (px)
    #[serde(default)]
    pub margin_x: f64,
    /// Minimum vertical distance from screen edge (px)
    #[serde(default)]
    pub margin_y: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkinManifest {
    pub name: String,
    pub author: Option<String>,
    pub version: Option<String>,
    pub expressions: HashMap<String, String>,
    /// Bubble placement relative to image center
    pub bubble_placement: Option<UiPlacement>,
    /// Chat input placement relative to image center
    pub input_placement: Option<UiPlacement>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkinInfo {
    pub id: String,
    pub name: String,
    pub author: Option<String>,
    pub version: Option<String>,
    pub path: String,
    pub bubble_placement: Option<UiPlacement>,
    pub input_placement: Option<UiPlacement>,
}
