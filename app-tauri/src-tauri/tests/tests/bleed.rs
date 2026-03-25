use std::time::Duration;

use crate::helpers::{app::AppInstance, green_screen::GreenScreen, screenshot, sway};

#[test]
fn test_no_bleed_after_bubble_hide() {
    sway::require_sway();
    let _green = GreenScreen::start();
    let _app = AppInstance::launch();

    // Move ghost to known position
    sway::move_window(sway::GHOST_TITLE, 400, 300);
    std::thread::sleep(Duration::from_millis(300));

    // Open input and type "md" to get a bubble
    trigger_bubble();

    // Wait for bubble to appear and record its position
    let bubble = sway::wait_for_window(sway::BUBBLE_TITLE, Duration::from_secs(5))
        .expect("bubble didn't appear");
    let br = bubble.rect;
    std::thread::sleep(Duration::from_millis(500)); // let content render

    // Dismiss the bubble with Escape
    sway::focus_window(sway::BUBBLE_TITLE);
    std::thread::sleep(Duration::from_millis(200));
    sway::send_key("Escape");

    // Wait for bubble to disappear
    assert!(
        sway::wait_for_window_gone(sway::BUBBLE_TITLE, Duration::from_secs(5)),
        "bubble didn't disappear after Escape"
    );

    // Wait for nudge repaint to complete
    std::thread::sleep(Duration::from_millis(800));

    // Screenshot the region where the bubble was
    let tmp = tempfile::NamedTempFile::with_suffix(".png").unwrap();
    screenshot::capture_region(br.x, br.y, br.width, br.height, tmp.path());

    // All pixels should be green (no bleed)
    let bad = screenshot::count_non_green_pixels(tmp.path());
    let total = br.width as u64 * br.height as u64;

    // Allow a tiny fraction of bad pixels for anti-aliasing / compositor artifacts
    let threshold = total / 100; // 1%
    assert!(
        bad <= threshold,
        "bleed detected: {bad}/{total} non-green pixels in bubble region ({} > {threshold} threshold)",
        bad
    );
}

#[test]
fn test_no_bleed_after_input_hide() {
    sway::require_sway();
    let _green = GreenScreen::start();
    let _app = AppInstance::launch();

    sway::move_window(sway::GHOST_TITLE, 400, 300);
    std::thread::sleep(Duration::from_millis(300));

    // Open input
    sway::focus_window(sway::GHOST_TITLE);
    std::thread::sleep(Duration::from_millis(200));
    sway::send_key("Return");

    let input = sway::wait_for_window(sway::INPUT_TITLE, Duration::from_secs(5))
        .expect("input didn't appear");
    let ir = input.rect;
    std::thread::sleep(Duration::from_millis(300));

    // Close input with Escape
    sway::focus_window(sway::INPUT_TITLE);
    std::thread::sleep(Duration::from_millis(200));
    sway::send_key("Escape");

    assert!(
        sway::wait_for_window_gone(sway::INPUT_TITLE, Duration::from_secs(5)),
        "input didn't disappear after Escape"
    );

    std::thread::sleep(Duration::from_millis(800));

    // Screenshot where the input was
    let tmp = tempfile::NamedTempFile::with_suffix(".png").unwrap();
    screenshot::capture_region(ir.x, ir.y, ir.width, ir.height, tmp.path());

    let bad = screenshot::count_non_green_pixels(tmp.path());
    let total = ir.width as u64 * ir.height as u64;
    let threshold = total / 100;
    assert!(
        bad <= threshold,
        "bleed detected after input hide: {bad}/{total} non-green pixels ({} > {threshold})",
        bad
    );
}

fn trigger_bubble() {
    sway::focus_window(sway::GHOST_TITLE);
    std::thread::sleep(Duration::from_millis(200));
    sway::send_key("Return");

    sway::wait_for_window(sway::INPUT_TITLE, Duration::from_secs(3))
        .expect("input didn't appear");
    std::thread::sleep(Duration::from_millis(200));

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
