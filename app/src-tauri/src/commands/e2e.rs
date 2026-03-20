use tauri::Emitter;

/// Emit an arbitrary Tauri event. Only active when DESKMATE_TEST_MODE=1.
/// Always registered but no-ops at runtime if not in test mode.
#[tauri::command]
pub fn e2e_inject_event(app: tauri::AppHandle, name: String, payload: String) {
    if !is_test_mode() {
        log::warn!("e2e_inject_event called but DESKMATE_TEST_MODE is not set");
        return;
    }
    let value: serde_json::Value =
        serde_json::from_str(&payload).unwrap_or(serde_json::Value::Null);
    log::info!("e2e_inject_event: name={name} payload={value}");
    let _ = app.emit(&name, value);
}

pub fn is_test_mode() -> bool {
    std::env::var("DESKMATE_TEST_MODE").map_or(false, |v| v == "1")
}
