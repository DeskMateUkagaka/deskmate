use std::time::{Duration, Instant};
use swayipc::{Connection, Node};

pub const GHOST_TITLE: &str = "deskmate-ghost";
pub const BUBBLE_TITLE: &str = "deskmate-bubble";
pub const INPUT_TITLE: &str = "deskmate-input";
pub const SETTINGS_TITLE: &str = "deskmate-settings";
#[allow(dead_code)]
pub const SKIN_PICKER_TITLE: &str = "deskmate-skin-picker";

const POSITION_TOLERANCE: i32 = 5;

/// Skip the test if not running on Sway.
pub fn require_sway() {
    if std::env::var("SWAYSOCK").is_err() {
        eprintln!("SKIP: not running on Sway (SWAYSOCK not set)");
        std::process::exit(0);
    }
}

/// Find a window node by title in the Sway tree.
pub fn find_window(title: &str) -> Option<Node> {
    let mut conn = Connection::new().ok()?;
    let tree = conn.get_tree().ok()?;
    find_node_by_title(&tree, title)
}

/// Get window rect: (x, y, width, height).
pub fn get_window_rect(title: &str) -> Option<(i32, i32, i32, i32)> {
    let node = find_window(title)?;
    let r = node.rect;
    Some((r.x, r.y, r.width, r.height))
}

/// Poll until a window with the given title appears. Returns the node.
pub fn wait_for_window(title: &str, timeout: Duration) -> Option<Node> {
    let start = Instant::now();
    loop {
        if let Some(node) = find_window(title) {
            return Some(node);
        }
        if start.elapsed() >= timeout {
            return None;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

/// Poll until a window with the given title disappears.
pub fn wait_for_window_gone(title: &str, timeout: Duration) -> bool {
    let start = Instant::now();
    loop {
        if find_window(title).is_none() {
            return true;
        }
        if start.elapsed() >= timeout {
            return false;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

/// Assert a window's position is within ±tolerance of expected.
pub fn assert_position_near(title: &str, expected_x: i32, expected_y: i32) {
    let (x, y, _, _) = get_window_rect(title)
        .unwrap_or_else(|| panic!("window {title:?} not found in Sway tree"));
    let dx = (x - expected_x).abs();
    let dy = (y - expected_y).abs();
    assert!(
        dx <= POSITION_TOLERANCE && dy <= POSITION_TOLERANCE,
        "window {title:?} at ({x},{y}), expected ({expected_x},{expected_y}) ±{POSITION_TOLERANCE}px (dx={dx}, dy={dy})"
    );
}

/// Get the title of the currently focused window.
pub fn get_focused_title() -> Option<String> {
    let mut conn = Connection::new().ok()?;
    let tree = conn.get_tree().ok()?;
    find_focused(&tree).and_then(|n| n.name.clone())
}

/// Move a window to a specific position via swaymsg.
pub fn move_window(title: &str, x: i32, y: i32) {
    let cmd = format!("[title=\"^{title}$\"] move absolute position {x} {y}");
    let mut conn = Connection::new().expect("sway IPC connection failed");
    let outcomes = conn.run_command(&cmd).expect("sway run_command failed");
    for o in &outcomes {
        if let Err(e) = o {
            panic!("sway move failed for {title:?}: {e}");
        }
    }
}

/// Focus a window by title.
pub fn focus_window(title: &str) {
    let cmd = format!("[title=\"^{title}$\"] focus");
    let mut conn = Connection::new().expect("sway IPC connection failed");
    let _ = conn.run_command(&cmd);
}

/// Send a key press via wtype.
pub fn send_key(key: &str) {
    let status = std::process::Command::new("wtype")
        .args(["-k", key])
        .status()
        .expect("wtype not found — install wtype for keyboard simulation");
    assert!(status.success(), "wtype failed for key {key:?}");
}

/// Type text via wtype.
#[allow(dead_code)]
pub fn type_text(text: &str) {
    let status = std::process::Command::new("wtype")
        .arg(text)
        .status()
        .expect("wtype not found");
    assert!(status.success(), "wtype failed for text {text:?}");
}

fn find_node_by_title(node: &Node, title: &str) -> Option<Node> {
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

fn find_focused(node: &Node) -> Option<&Node> {
    if node.focused {
        return Some(node);
    }
    for child in &node.nodes {
        if let Some(n) = find_focused(child) {
            return Some(n);
        }
    }
    for child in &node.floating_nodes {
        if let Some(n) = find_focused(child) {
            return Some(n);
        }
    }
    None
}
