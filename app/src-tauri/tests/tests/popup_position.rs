use std::time::Duration;

use crate::helpers::{app::AppInstance, sway};

#[test]
fn test_input_positioned_relative_to_ghost() {
    sway::require_sway();
    let _app = AppInstance::launch();

    // Move ghost to known position
    let ghost_x = 500;
    let ghost_y = 400;
    sway::move_window(sway::GHOST_TITLE, ghost_x, ghost_y);
    std::thread::sleep(Duration::from_millis(300));

    // Focus ghost and press Enter to open chat input
    sway::focus_window(sway::GHOST_TITLE);
    std::thread::sleep(Duration::from_millis(200));
    sway::send_key("Return");

    // Wait for input window to appear
    let input = sway::wait_for_window(sway::INPUT_TITLE, Duration::from_secs(5));
    assert!(input.is_some(), "input window didn't appear after pressing Enter");

    // Verify it's near the ghost (not at 0,0 or default position)
    let (ix, iy, _, _) = sway::get_window_rect(sway::INPUT_TITLE)
        .expect("input window not found");

    // The input should be somewhere near the ghost, not at the screen origin.
    // We can't know the exact offset without reading skin placement, but it
    // should be within a reasonable range of the ghost position.
    let dx = (ix - ghost_x).abs();
    let dy = (iy - ghost_y).abs();
    assert!(
        dx < 600 && dy < 600,
        "input window at ({ix},{iy}) is too far from ghost at ({ghost_x},{ghost_y}): dx={dx}, dy={dy}"
    );

    // Importantly: it should NOT be at (0,0) — that would indicate the
    // "hidden windows can't be moved on Sway" bug
    assert!(
        !(ix == 0 && iy == 0),
        "input window is at (0,0) — likely the show-before-move bug"
    );
}

#[test]
fn test_popup_shown_before_moved() {
    // Regression test: on Sway, hidden windows can't be moved because they're
    // not in the compositor tree. The app must show() before moveWindow().
    // If this order is wrong, the window appears at the default position (0,0).
    sway::require_sway();
    let _app = AppInstance::launch();

    // Move ghost to a non-origin position
    sway::move_window(sway::GHOST_TITLE, 700, 500);
    std::thread::sleep(Duration::from_millis(300));

    // Open input (which should show-then-move on Sway)
    sway::focus_window(sway::GHOST_TITLE);
    std::thread::sleep(Duration::from_millis(200));
    sway::send_key("Return");

    let _ = sway::wait_for_window(sway::INPUT_TITLE, Duration::from_secs(5))
        .expect("input window didn't appear");
    std::thread::sleep(Duration::from_millis(500)); // let positioning complete

    let (ix, iy, _, _) = sway::get_window_rect(sway::INPUT_TITLE)
        .expect("input window not found");

    // If show-before-move is broken, the window stays at default pos.
    // It must be near the ghost, not at origin.
    assert!(
        ix > 100 || iy > 100,
        "input at ({ix},{iy}) — likely stuck at default position (show-before-move broken)"
    );
}

#[test]
fn test_bubble_positioned_relative_to_ghost() {
    sway::require_sway();
    let _app = AppInstance::launch();

    let ghost_x = 500;
    let ghost_y = 300;
    sway::move_window(sway::GHOST_TITLE, ghost_x, ghost_y);
    std::thread::sleep(Duration::from_millis(300));

    // Inject a fake chat event to show the bubble.
    // The app must be in test mode (DESKMATE_TEST_MODE=1) for this to work.
    inject_chat_event();

    let bubble = sway::wait_for_window(sway::BUBBLE_TITLE, Duration::from_secs(5));
    assert!(bubble.is_some(), "bubble window didn't appear after chat event injection");

    std::thread::sleep(Duration::from_millis(500)); // let positioning settle

    let (bx, by, _, _) = sway::get_window_rect(sway::BUBBLE_TITLE)
        .expect("bubble window not found");

    // Bubble should be near the ghost
    let dx = (bx - ghost_x).abs();
    let dy = (by - ghost_y).abs();
    assert!(
        dx < 800 && dy < 800,
        "bubble at ({bx},{by}) is too far from ghost at ({ghost_x},{ghost_y})"
    );
    assert!(
        !(bx == 0 && by == 0),
        "bubble at (0,0) — show-before-move bug"
    );
}

/// Use wtype to type "hello" into the chat input to trigger a response.
/// For tests that need a bubble, we open the input, type, and send.
/// In test mode without a gateway, the app has a debug shortcut.
fn inject_chat_event() {
    // Focus ghost, open input
    sway::focus_window(sway::GHOST_TITLE);
    std::thread::sleep(Duration::from_millis(200));
    sway::send_key("Return");

    // Wait for input
    sway::wait_for_window(sway::INPUT_TITLE, Duration::from_secs(3))
        .expect("input window didn't appear");
    std::thread::sleep(Duration::from_millis(200));

    // Type "md" (debug shortcut that returns sample markdown) and Enter
    sway::focus_window(sway::INPUT_TITLE);
    std::thread::sleep(Duration::from_millis(200));

    let status = std::process::Command::new("wtype")
        .arg("md")
        .status()
        .expect("wtype not found");
    assert!(status.success());

    std::thread::sleep(Duration::from_millis(100));
    sway::send_key("Return");
}
