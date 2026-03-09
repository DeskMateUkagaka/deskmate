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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkinManifest {
    pub name: String,
    pub author: Option<String>,
    pub version: Option<String>,
    pub expressions: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkinInfo {
    pub id: String,
    pub name: String,
    pub author: Option<String>,
    pub version: Option<String>,
    pub path: String,
}
