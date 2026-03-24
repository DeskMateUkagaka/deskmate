use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Bubble visual theme: colors, borders, fonts for the chat bubble.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct BubbleTheme {
    #[serde(default)]
    pub background_color: Option<String>,
    #[serde(default)]
    pub border_color: Option<String>,
    #[serde(default)]
    pub border_width: Option<String>,
    #[serde(default)]
    pub border_radius: Option<String>,
    #[serde(default)]
    pub text_color: Option<String>,
    #[serde(default)]
    pub accent_color: Option<String>,
    #[serde(default)]
    pub code_background: Option<String>,
    #[serde(default)]
    pub code_text_color: Option<String>,
    #[serde(default)]
    pub font_family: Option<String>,
    #[serde(default)]
    pub font_size: Option<String>,
    /// Bubble width in pixels
    #[serde(default)]
    pub max_bubble_width: Option<u32>,
    /// Maximum bubble height in pixels
    #[serde(default)]
    pub max_bubble_height: Option<u32>,
}

/// Input box theme: max dimensions for the growable chat input.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct InputTheme {
    /// Maximum input width in pixels (default: 640)
    #[serde(default)]
    pub max_width: Option<u32>,
    /// Maximum input height in pixels (default: 480)
    #[serde(default)]
    pub max_height: Option<u32>,
}

/// Which corner of the popup the (x, y) coordinate refers to.
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
#[serde(rename_all = "kebab-case")]
pub enum PlacementOrigin {
    #[default]
    Center,
    TopLeft,
    TopRight,
    BottomLeft,
    BottomRight,
}

/// UI element placement: pixel offset from ghost image center (in original PNG coordinates).
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UiPlacement {
    /// Horizontal offset from image center (px, in original PNG coordinates)
    #[serde(default)]
    pub x: f64,
    /// Vertical offset from image center (px, in original PNG coordinates, negative = above)
    #[serde(default)]
    pub y: f64,
    /// Which corner of the popup the coordinate refers to
    #[serde(default)]
    pub origin: PlacementOrigin,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkinManifest {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    pub author: Option<String>,
    pub version: Option<String>,
    pub emotions: HashMap<String, Vec<String>>,
    /// Bubble placement relative to image center
    pub bubble_placement: Option<UiPlacement>,
    /// Chat input placement relative to image center
    pub input_placement: Option<UiPlacement>,
    /// Bubble visual theme (colors, borders, fonts)
    #[serde(default)]
    pub bubble: Option<BubbleTheme>,
    /// Input box theme (max dimensions)
    #[serde(default)]
    pub input: Option<InputTheme>,
    /// Idle animation clips (optional; empty = no idle animations)
    #[serde(default)]
    pub idle_animations: Vec<IdleAnimation>,
    /// Seconds between idle animations (default 30.0, skin-configurable)
    #[serde(default = "default_idle_interval")]
    pub idle_interval_seconds: f64,
    /// Skin format version (1 = static PNGs, 2+ = future animated)
    #[serde(default = "default_format_version")]
    pub format_version: u32,
}

fn default_format_version() -> u32 { 1 }
fn default_idle_interval() -> f64 { 30.0 }

/// An idle animation clip declared in the skin manifest.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdleAnimation {
    /// Filename relative to skin directory, e.g. "idle-blink.apng"
    pub file: String,
    /// Total animation duration in milliseconds
    pub duration_ms: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkinInfo {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    pub author: Option<String>,
    pub version: Option<String>,
    pub path: String,
    /// Available emotion names from the skin manifest (e.g. ["happy", "sad", "neutral", ...])
    pub emotions: Vec<String>,
    pub bubble_placement: Option<UiPlacement>,
    pub input_placement: Option<UiPlacement>,
    pub bubble_theme: Option<BubbleTheme>,
    pub input_theme: Option<InputTheme>,
    /// Idle animation clips (mirrors SkinManifest)
    pub idle_animations: Vec<IdleAnimation>,
    /// Where this skin came from: "bundled" or "community"
    #[serde(default)]
    pub source: String,
    /// Skin format version (1 = static PNGs)
    #[serde(default = "default_format_version")]
    pub format_version: u32,
}
