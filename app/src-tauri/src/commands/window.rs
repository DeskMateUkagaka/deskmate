// TODO: re-enable when compositor-specific positioning is implemented
#[allow(unused_imports)]
use std::process::Command;

/// Detect the current desktop environment / compositor.
fn detect_compositor() -> Compositor {
    // Sway sets $SWAYSOCK
    if std::env::var("SWAYSOCK").is_ok() {
        return Compositor::Sway;
    }
    // Hyprland sets $HYPRLAND_INSTANCE_SIGNATURE
    if std::env::var("HYPRLAND_INSTANCE_SIGNATURE").is_ok() {
        return Compositor::Hyprland;
    }
    Compositor::Unknown
}

#[derive(Debug)]
enum Compositor {
    Sway,
    Hyprland,
    Unknown,
}

/// Move a window by its title to (x, y) logical coordinates.
/// Returns true if the compositor handled positioning, false if the caller
/// should fall back to Tauri's built-in setPosition.
#[tauri::command]
pub fn move_window(title: String, x: i32, y: i32) -> bool {
    let compositor = detect_compositor();
    log::info!("move_window: title={title:?} pos=({x},{y}) compositor={compositor:?}");

    match compositor {
        // Sway: swaymsg works but is too slow for responsive UI.
        // Keeping detection + scaffolding for future use (e.g. IPC socket directly).
        // Compositor::Sway => {
        //     let criteria = format!("[title=\"^{}$\"]", title);
        //     let pos = format!("move position {} {}", x, y);
        //     let result = Command::new("swaymsg")
        //         .args([&criteria, &pos])
        //         .output();
        //     match result {
        //         Ok(output) if output.status.success() => true,
        //         Ok(output) => {
        //             let stderr = String::from_utf8_lossy(&output.stderr);
        //             log::warn!("swaymsg failed: {stderr}");
        //             false
        //         }
        //         Err(e) => {
        //             log::warn!("Failed to run swaymsg: {e}");
        //             false
        //         }
        //     }
        // }
        // TODO: implement Hyprland, KDE, GNOME, etc.
        // TODO: consider Sway IPC socket directly for better performance
        _ => false,
    }
}
