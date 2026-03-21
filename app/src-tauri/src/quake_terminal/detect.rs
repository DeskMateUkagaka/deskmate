/// Detect the best available terminal emulator for the current platform.
/// Returns the binary name (e.g. "foot", "kitty") or None if nothing found.
pub fn detect_terminal() -> Option<String> {
    #[cfg(target_os = "linux")]
    {
        // Priority list for Linux
        let candidates = ["foot", "kitty", "alacritty", "konsole", "xterm", "xfce4-terminal"];
        for name in &candidates {
            if is_available(name) {
                log::info!("Detected terminal emulator: {name}");
                return Some(name.to_string());
            }
        }
        None
    }

    #[cfg(target_os = "macos")]
    {
        // Check for preferred terminals first, fall back to Terminal.app (always available)
        if std::path::Path::new("/Applications/iTerm.app").exists() {
            log::info!("Detected terminal emulator: iterm2");
            return Some("iterm2".to_string());
        }
        for name in &["kitty", "alacritty"] {
            if is_available(name) {
                log::info!("Detected terminal emulator: {name}");
                return Some(name.to_string());
            }
        }
        log::info!("Detected terminal emulator: Terminal.app (default)");
        Some("terminal.app".to_string())
    }

    #[cfg(target_os = "windows")]
    {
        // Windows Terminal first, then PowerShell fallback
        if is_available("wt") {
            log::info!("Detected terminal emulator: wt (Windows Terminal)");
            return Some("wt".to_string());
        }
        log::info!("Detected terminal emulator: powershell (fallback)");
        Some("powershell".to_string())
    }

    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    {
        log::warn!("Unsupported platform for terminal detection");
        None
    }
}

/// Check if a binary is available on PATH.
fn is_available(name: &str) -> bool {
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    {
        std::process::Command::new("which")
            .arg(name)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("where")
            .arg(name)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
    }

    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    {
        let _ = name;
        false
    }
}
