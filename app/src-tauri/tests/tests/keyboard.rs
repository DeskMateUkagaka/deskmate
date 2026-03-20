use std::time::Duration;

use crate::helpers::{app::AppInstance, sway};

#[test]
fn test_focus_returns_after_input_close() {
    sway::require_sway();
    let _app = AppInstance::launch();

    // Focus ghost
    sway::focus_window(sway::GHOST_TITLE);
    std::thread::sleep(Duration::from_millis(300));

    // Open input
    sway::send_key("Return");
    sway::wait_for_window(sway::INPUT_TITLE, Duration::from_secs(5))
        .expect("input window didn't appear");
    std::thread::sleep(Duration::from_millis(300));

    // Verify input is focused
    let focused = sway::get_focused_title();
    assert_eq!(
        focused.as_deref(),
        Some(sway::INPUT_TITLE),
        "expected input to be focused, got: {focused:?}"
    );

    // Close input with Escape
    sway::send_key("Escape");
    assert!(
        sway::wait_for_window_gone(sway::INPUT_TITLE, Duration::from_secs(5)),
        "input didn't disappear"
    );
    std::thread::sleep(Duration::from_millis(300));

    // Verify ghost got focus back
    let focused = sway::get_focused_title();
    assert_eq!(
        focused.as_deref(),
        Some(sway::GHOST_TITLE),
        "expected ghost to be focused after input close, got: {focused:?}"
    );
}
