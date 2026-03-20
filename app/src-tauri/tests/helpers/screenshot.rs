use image::GenericImageView;
use std::path::Path;
use std::process::Command;

const COLOR_TOLERANCE: u8 = 5;

/// Capture a region of the screen using grim.
/// Returns the path to the saved PNG.
pub fn capture_region(x: i32, y: i32, w: i32, h: i32, output: &Path) {
    let geometry = format!("{x},{y} {w}x{h}");
    let status = Command::new("grim")
        .args(["-g", &geometry, output.to_str().unwrap()])
        .status()
        .expect("grim not found — install grim for screenshot tests");
    assert!(status.success(), "grim failed to capture region {geometry}");
}

/// Capture the full screen using grim.
#[allow(dead_code)]
pub fn capture_screen(output: &Path) {
    let status = Command::new("grim")
        .arg(output.to_str().unwrap())
        .status()
        .expect("grim not found");
    assert!(status.success(), "grim failed to capture screen");
}

/// Assert all pixels in an image are within ±tolerance of expected RGB.
/// Returns Ok(()) or panics with details about bad pixels.
pub fn assert_all_pixels_green(img_path: &Path) {
    let img = image::open(img_path)
        .unwrap_or_else(|e| panic!("failed to open screenshot {}: {e}", img_path.display()));
    let (w, h) = img.dimensions();
    let mut bad_count = 0u64;
    let mut first_bad: Option<(u32, u32, [u8; 3])> = None;

    for y in 0..h {
        for x in 0..w {
            let pixel = img.get_pixel(x, y);
            let [r, g, b, _] = pixel.0;
            if !is_near_green(r, g, b) {
                bad_count += 1;
                if first_bad.is_none() {
                    first_bad = Some((x, y, [r, g, b]));
                }
            }
        }
    }

    if bad_count > 0 {
        let total = w as u64 * h as u64;
        let (bx, by, [br, bg, bb]) = first_bad.unwrap();
        panic!(
            "bleed detected: {bad_count}/{total} pixels are not green (0,255,0) ±{COLOR_TOLERANCE}. \
             First bad pixel at ({bx},{by}): rgb({br},{bg},{bb})"
        );
    }
}

/// Count pixels that are NOT within tolerance of green.
pub fn count_non_green_pixels(img_path: &Path) -> u64 {
    let img = image::open(img_path)
        .unwrap_or_else(|e| panic!("failed to open screenshot {}: {e}", img_path.display()));
    let (w, h) = img.dimensions();
    let mut bad = 0u64;
    for y in 0..h {
        for x in 0..w {
            let [r, g, b, _] = img.get_pixel(x, y).0;
            if !is_near_green(r, g, b) {
                bad += 1;
            }
        }
    }
    bad
}

fn is_near_green(r: u8, g: u8, b: u8) -> bool {
    r <= COLOR_TOLERANCE && g >= 255 - COLOR_TOLERANCE && b <= COLOR_TOLERANCE
}
