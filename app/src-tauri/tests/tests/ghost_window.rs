use std::time::Duration;

use crate::helpers::{app::AppInstance, green_screen::GreenScreen, screenshot, sway};

#[test]
fn test_ghost_renders_on_sway() {
    sway::require_sway();
    let _app = AppInstance::launch();

    let node = sway::find_window(sway::GHOST_TITLE)
        .expect("ghost window not found in Sway tree");
    let r = node.rect;
    assert!(r.width > 0 && r.height > 0, "ghost window has zero dimensions: {r:?}");
}

#[test]
fn test_ghost_transparent_background() {
    sway::require_sway();
    let _green = GreenScreen::start();
    let _app = AppInstance::launch();

    // Move ghost to a known position
    sway::move_window(sway::GHOST_TITLE, 200, 200);
    std::thread::sleep(Duration::from_millis(300));

    // Get ghost rect
    let (gx, gy, gw, gh) = sway::get_window_rect(sway::GHOST_TITLE)
        .expect("ghost window not found");

    // Screenshot a small strip at the top-left corner of the ghost window.
    // The ghost image is centered — corners should be transparent (showing green).
    let strip_w = 20.min(gw);
    let strip_h = 20.min(gh);
    let tmp = tempfile::NamedTempFile::with_suffix(".png").unwrap();
    screenshot::capture_region(gx, gy, strip_w, strip_h, tmp.path());
    screenshot::assert_all_pixels_green(tmp.path());
}

#[test]
fn test_ghost_position_save_restore() {
    sway::require_sway();

    let target_x = 350;
    let target_y = 250;

    // First launch: move ghost, then exit
    {
        let _app = AppInstance::launch();
        sway::move_window(sway::GHOST_TITLE, target_x, target_y);
        std::thread::sleep(Duration::from_millis(300));

        // Send Ctrl+Q to trigger save-and-exit
        sway::focus_window(sway::GHOST_TITLE);
        std::thread::sleep(Duration::from_millis(200));
        send_ctrl_q();

        // Wait for app to exit
        assert!(
            sway::wait_for_window_gone(sway::GHOST_TITLE, Duration::from_secs(5)),
            "ghost window didn't disappear after Ctrl+Q"
        );
    }

    // Second launch: verify position was restored
    std::thread::sleep(Duration::from_millis(500));
    {
        let _app = AppInstance::launch();
        std::thread::sleep(Duration::from_millis(500));
        sway::assert_position_near(sway::GHOST_TITLE, target_x, target_y);
    }
}

fn send_ctrl_q() {
    let status = std::process::Command::new("wtype")
        .args(["-M", "ctrl", "-k", "q", "-m", "ctrl"])
        .status()
        .expect("wtype not found");
    assert!(status.success(), "wtype Ctrl+Q failed");
}
