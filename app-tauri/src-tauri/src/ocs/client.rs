use std::io::Write;
use std::path::{Path, PathBuf};

use serde::Serialize;

use super::types::{OcsBrowseParams, OcsResponse};

#[derive(Debug, Clone, Serialize)]
pub struct DownloadProgress {
    pub downloaded: usize,
    pub total: Option<usize>,
}

pub async fn browse(
    client: &reqwest::Client,
    params: OcsBrowseParams,
) -> Result<OcsResponse, String> {
    let url = "https://api.pling.com/ocs/v1/content/data";

    let response = client
        .get(url)
        .query(&[
            ("format", "json"),
            ("categories", &params.categories),
            ("tags", &params.tags),
            ("search", &params.search),
            ("sortmode", &params.sortmode),
            ("page", &params.page.to_string()),
            ("pagesize", &params.pagesize.to_string()),
        ])
        .send()
        .await
        .map_err(|e| format!("OCS browse request failed: {}", e))?;

    let status = response.status();
    if !status.is_success() {
        return Err(format!("OCS browse returned HTTP {}", status));
    }

    let ocs_response = response
        .json::<OcsResponse>()
        .await
        .map_err(|e| format!("OCS browse JSON parse failed: {}", e))?;

    log::info!(
        "OCS browse: {} items (page {}, total {})",
        ocs_response.data.len(),
        params.page,
        ocs_response.totalitems
    );

    Ok(ocs_response)
}

pub async fn download_to_file(
    client: &reqwest::Client,
    url: &str,
    dest: &Path,
    app: &tauri::AppHandle,
) -> Result<PathBuf, String> {
    use tauri::Emitter;

    let response = client
        .get(url)
        .send()
        .await
        .map_err(|e| format!("Download request failed: {}", e))?;

    let status = response.status();
    if !status.is_success() {
        return Err(format!("Download returned HTTP {}", status));
    }

    let total: Option<usize> = response
        .headers()
        .get(reqwest::header::CONTENT_LENGTH)
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.parse().ok());

    let mut file = std::fs::File::create(dest)
        .map_err(|e| format!("Failed to create file {}: {}", dest.display(), e))?;

    log::info!("Downloading skin to {}", dest.display());

    let mut downloaded: usize = 0;
    let mut response = response;

    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|e| format!("Download stream error: {}", e))?
    {
        file.write_all(&chunk)
            .map_err(|e| format!("Failed to write chunk to {}: {}", dest.display(), e))?;

        downloaded += chunk.len();

        let _ = app.emit(
            "skin-download-progress",
            DownloadProgress {
                downloaded,
                total,
            },
        );
    }

    log::info!(
        "Download complete: {} bytes written to {}",
        downloaded,
        dest.display()
    );

    Ok(dest.to_path_buf())
}
