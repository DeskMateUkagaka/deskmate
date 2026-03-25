use std::process::{Child, Command};
use std::time::Duration;

/// A green background via swaybg for bleed detection tests.
/// Renders on the wallpaper layer (always behind all windows).
pub struct GreenScreen {
    child: Child,
}

impl GreenScreen {
    pub fn start() -> Self {
        let child = Command::new("swaybg")
            .args(["-c", "#00ff00", "-m", "solid_color"])
            .spawn()
            .expect("swaybg not found — install swaybg for bleed tests");

        // Give swaybg time to render
        std::thread::sleep(Duration::from_millis(300));

        GreenScreen { child }
    }
}

impl Drop for GreenScreen {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
