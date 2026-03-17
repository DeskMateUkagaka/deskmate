use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub const EXPRESSIONS: &[&str] = &[
    "happy",
    "sad",
    "angry",
    "disgusted",
    "condescending",
    "thinking",
    "neutral",
];

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
    /// Which corner of the popup the coordinate refers to
    #[serde(default)]
    pub origin: PlacementOrigin,
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
    /// Bubble visual theme (colors, borders, fonts)
    #[serde(default)]
    pub bubble: Option<BubbleTheme>,
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
    pub bubble_theme: Option<BubbleTheme>,
}
