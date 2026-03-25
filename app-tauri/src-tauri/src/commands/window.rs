/// Returns true if window positioning uses slow compositor IPC (e.g. swaymsg).
/// Frontend uses this to debounce repositioning.
#[tauri::command]
pub fn uses_compositor_ipc() -> bool {
    matches!(detect_compositor(), Compositor::Sway)
}

/// Detect the current desktop environment / compositor.
fn detect_compositor() -> Compositor {
    if std::env::var("SWAYSOCK").is_ok() {
        return Compositor::Sway;
    }
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
pub async fn move_window(title: String, x: i32, y: i32) -> bool {
    let compositor = detect_compositor();
    log::info!("move_window: title={title:?} pos=({x},{y}) compositor={compositor:?}");

    match compositor {
        Compositor::Sway => sway_move_window(&title, x, y).await,
        // TODO: implement Hyprland, KDE, GNOME, etc.
        _ => false,
    }
}

/// Retry up to 10 times with 100ms async sleep — newly shown windows may not
/// be in Sway's tree yet. Uses async sleep to avoid blocking the thread so
/// the window can finish registering with the compositor between retries.
async fn sway_move_window(title: &str, x: i32, y: i32) -> bool {
    let cmd = format!("[title=\"^{}$\"] move absolute position {} {}", title, x, y);

    for attempt in 1..=10 {
        let mut conn = match swayipc::Connection::new() {
            Ok(c) => c,
            Err(e) => {
                log::warn!("sway IPC connection failed: {e}");
                return false;
            }
        };

        match conn.run_command(&cmd) {
            Ok(outcomes) if outcomes.iter().all(|o| o.is_ok()) => return true,
            Ok(outcomes) => {
                let errs: Vec<_> = outcomes.iter().filter_map(|o| o.as_ref().err()).collect();
                if errs.iter().any(|e| format!("{e}").contains("No matching node")) && attempt < 10 {
                    log::info!("move_window: {title:?} not in tree yet, retry {attempt}/10");
                    tokio::time::sleep(std::time::Duration::from_millis(100)).await;
                    continue;
                }
                log::warn!("sway IPC command failed: {errs:?}");
                return false;
            }
            Err(e) => {
                log::warn!("sway IPC run_command failed: {e}");
                return false;
            }
        }
    }
    false
}

/// Get a window's position by title using compositor IPC.
/// Returns (x, y) if the compositor can provide it, None otherwise
/// (caller should fall back to Tauri's outerPosition).
#[tauri::command]
pub fn get_window_position(title: String) -> Option<(i32, i32)> {
    let compositor = detect_compositor();
    log::info!("get_window_position: title={title:?} compositor={compositor:?}");

    match compositor {
        Compositor::Sway => {
            let mut conn = match swayipc::Connection::new() {
                Ok(c) => c,
                Err(e) => {
                    log::warn!("sway IPC connection failed: {e}");
                    return None;
                }
            };
            let tree = match conn.get_tree() {
                Ok(t) => t,
                Err(e) => {
                    log::warn!("sway IPC get_tree failed: {e}");
                    return None;
                }
            };
            find_node_by_title(&tree, &title).map(|node| {
                let r = node.rect;
                let dr = node.deco_rect;
                let wr = node.window_rect;
                let bw = node.current_border_width;
                log::info!("get_window_position: rect=({},{}) {}x{} deco_rect=({},{}) {}x{} window_rect=({},{}) {}x{} border_width={bw}",
                    r.x, r.y, r.width, r.height,
                    dr.x, dr.y, dr.width, dr.height,
                    wr.x, wr.y, wr.width, wr.height,
                    );
                (r.x, r.y)
            })
        }
        _ => None,
    }
}

fn find_node_by_title(node: &swayipc::Node, title: &str) -> Option<swayipc::Node> {
    if node.name.as_deref() == Some(title) {
        return Some(node.clone());
    }
    for child in &node.nodes {
        if let Some(n) = find_node_by_title(child, title) {
            return Some(n);
        }
    }
    for child in &node.floating_nodes {
        if let Some(n) = find_node_by_title(child, title) {
            return Some(n);
        }
    }
    None
}
