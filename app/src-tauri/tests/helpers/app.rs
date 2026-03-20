use std::path::PathBuf;
use std::process::{Child, Command};
use std::time::Duration;

use super::sway;

/// A running DeskMate app instance. Kills the process on drop.
pub struct AppInstance {
    child: Child,
    _data_dir: tempfile::TempDir,
}

impl AppInstance {
    /// Launch the pre-built deskmate binary and wait for the ghost window to appear.
    pub fn launch() -> Self {
        let binary = find_binary();
        let data_dir = tempfile::tempdir().expect("failed to create temp data dir");

        let child = Command::new(&binary)
            .env("DESKMATE_TEST_MODE", "1")
            .env("XDG_DATA_HOME", data_dir.path())
            .env("XDG_CONFIG_HOME", data_dir.path())
            .spawn()
            .unwrap_or_else(|e| panic!("failed to launch {}: {e}", binary.display()));

        let instance = AppInstance {
            child,
            _data_dir: data_dir,
        };

        // Wait for ghost window to appear
        let ghost = sway::wait_for_window(sway::GHOST_TITLE, Duration::from_secs(15));
        assert!(
            ghost.is_some(),
            "ghost window {:?} did not appear within 15s",
            sway::GHOST_TITLE
        );

        // Give the app a moment to finish initialization
        std::thread::sleep(Duration::from_millis(500));

        instance
    }

    pub fn pid(&self) -> u32 {
        self.child.id()
    }
}

impl Drop for AppInstance {
    fn drop(&mut self) {
        // SIGTERM first
        unsafe {
            libc::kill(self.child.id() as i32, libc::SIGTERM);
        }
        // Wait up to 2s for graceful exit
        for _ in 0..20 {
            match self.child.try_wait() {
                Ok(Some(_)) => return,
                _ => std::thread::sleep(Duration::from_millis(100)),
            }
        }
        // Force kill
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn find_binary() -> PathBuf {
    // Look for the debug binary relative to the test binary location
    let candidates = [
        PathBuf::from("target/debug/deskmate"),
        PathBuf::from("../target/debug/deskmate"),
    ];
    for p in &candidates {
        if p.exists() {
            return p.canonicalize().unwrap();
        }
    }
    // Try from CARGO_MANIFEST_DIR
    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        let p = PathBuf::from(manifest).join("target/debug/deskmate");
        if p.exists() {
            return p;
        }
    }
    panic!(
        "deskmate binary not found. Build first with: cd app && cargo tauri build --debug\n\
         Searched: {:?}",
        candidates
    );
}
