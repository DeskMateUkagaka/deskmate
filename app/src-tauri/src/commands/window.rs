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
pub fn move_window(title: String, x: i32, y: i32) -> bool {
    let compositor = detect_compositor();
    log::info!("move_window: title={title:?} pos=({x},{y}) compositor={compositor:?}");

    match compositor {
        Compositor::Sway => {
            let cmd = format!("[title=\"^{}$\"] move absolute position {} {}", title, x, y);
            match swayipc::Connection::new() {
                Ok(mut conn) => {
                    match conn.run_command(&cmd) {
                        Ok(outcomes) => {
                            let all_ok = outcomes.iter().all(|o| o.is_ok());
                            if !all_ok {
                                let errs: Vec<_> = outcomes.iter().filter_map(|o| o.as_ref().err()).collect();
                                log::warn!("sway IPC command had failures: {errs:?}");
                            }
                            all_ok
                        }
                        Err(e) => {
                            log::warn!("sway IPC run_command failed: {e}");
                            false
                        }
                    }
                }
                Err(e) => {
                    log::warn!("sway IPC connection failed: {e}");
                    false
                }
            }
        }
        // TODO: implement Hyprland, KDE, GNOME, etc.
        _ => false,
    }
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
