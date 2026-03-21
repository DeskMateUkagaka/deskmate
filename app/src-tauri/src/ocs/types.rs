use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OcsResponse {
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub statuscode: i32,
    #[serde(default)]
    pub totalitems: i32,
    #[serde(default)]
    pub itemsperpage: i32,
    #[serde(default)]
    pub data: Vec<OcsContentItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OcsContentItem {
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub personid: String,
    #[serde(default)]
    pub created: String,
    #[serde(default)]
    pub changed: String,
    #[serde(default)]
    pub downloads: i64,
    #[serde(default)]
    pub score: i64,
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub tags: String,
    #[serde(default)]
    pub previewpic1: String,
    #[serde(default)]
    pub smallpreviewpic1: String,
    #[serde(default)]
    pub downloadlink1: String,
    #[serde(default)]
    pub downloadname1: String,
    #[serde(default)]
    pub downloadsize1: i64,
    #[serde(default)]
    pub downloadmd5sum1: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OcsBrowseParams {
    #[serde(default = "default_categories")]
    pub categories: String,
    #[serde(default = "default_tags")]
    pub tags: String,
    #[serde(default)]
    pub search: String,
    #[serde(default = "default_sortmode")]
    pub sortmode: String,
    #[serde(default)]
    pub page: i32,
    #[serde(default = "default_pagesize")]
    pub pagesize: i32,
}

fn default_categories() -> String {
    "464".to_string()
}

fn default_tags() -> String {
    "deskmate,deskmate-v1".to_string()
}

fn default_sortmode() -> String {
    "new".to_string()
}

fn default_pagesize() -> i32 {
    20
}
