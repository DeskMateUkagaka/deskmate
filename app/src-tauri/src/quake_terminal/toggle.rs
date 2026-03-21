use crate::quake_terminal::QuakeTerminalState;
use crate::settings::QuakeTerminalConfig;

/// Toggle the quake terminal. Spawns on first call, shows/hides on subsequent calls.
/// If the process has exited (user closed it), re-spawns.
pub fn toggle(
    state: &mut QuakeTerminalState,
    config: &QuakeTerminalConfig,
    app: &tauri::AppHandle,
) -> Result<(), String> {
    // Step 1: Check process liveness — always do this first
    if let Some(ref mut child) = state.process {
        match child.try_wait() {
            Ok(Some(status)) => {
                log::info!("Quake terminal process exited: {status}");
                state.process = None;
                state.visible = false;
            }
            Err(e) => {
                log::warn!("Failed to check quake terminal process: {e}");
                state.process = None;
                state.visible = false;
            }
            Ok(None) => {} // still alive
        }
    }

    if state.process.is_none() {
        // Step 2: Detect and spawn
        let detected = super::detect::detect_terminal();
        let terminal = config
            .terminal_emulator
            .as_deref()
            .or(detected.as_deref())
            .ok_or("No terminal emulator found. Install foot, kitty, alacritty, or another supported terminal.")?;

        state.terminal_name = Some(terminal.to_string());

        // Get screen geometry from Tauri monitor API
        let (screen_width, screen_height) = get_screen_size(app)?;
        let width = screen_width;
        let height = screen_height * config.height_percent / 100;

        log::info!("Spawning quake terminal: {terminal} at {width}x{height}");
        let child = super::spawn::spawn_terminal(terminal, &config.command, width, height)?;
        state.process = Some(child);
        state.visible = true;

        // Position via compositor (async, fire-and-forget on Sway)
        #[cfg(target_os = "linux")]
        {
            let w = width;
            let h = height;
            tauri::async_runtime::spawn(async move {
                if let Err(e) = super::spawn::sway_position_terminal(w, h).await {
                    log::warn!("Failed to position quake terminal via sway: {e}");
                }
            });
        }
    } else {
        // Step 3: Toggle visibility
        if state.visible {
            hide_terminal()?;
            state.visible = false;
            log::info!("Quake terminal hidden");
        } else {
            let (screen_width, _screen_height) = get_screen_size(app).unwrap_or((1920, 1080));
            let height = _screen_height * config.height_percent / 100;
            show_terminal(screen_width, height)?;
            state.visible = true;
            log::info!("Quake terminal shown");
        }
    }

    Ok(())
}

/// Get the primary monitor's size in logical pixels.
fn get_screen_size(app: &tauri::AppHandle) -> Result<(u32, u32), String> {
    // Try to get primary monitor, fall back to any available monitor
    let monitor = app
        .primary_monitor()
        .map_err(|e| format!("Failed to query monitor: {e}"))?
        .or_else(|| app.available_monitors().ok()?.into_iter().next())
        .ok_or("No monitor found")?;

    let size = monitor.size();
    let scale = monitor.scale_factor();
    // Convert physical pixels to logical pixels
    let width = (size.width as f64 / scale) as u32;
    let height = (size.height as f64 / scale) as u32;
    log::info!("Screen size: {width}x{height} (scale: {scale})");
    Ok((width, height))
}

/// Hide the quake terminal window via compositor.
fn hide_terminal() -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        if std::env::var("SWAYSOCK").is_ok() {
            // Sway: move offscreen
            let mut conn = swayipc::Connection::new()
                .map_err(|e| format!("swayipc: {e}"))?;
            conn.run_command(r#"[title="^deskmate-quake$"] move position 0 -9999"#)
                .map_err(|e| format!("sway hide: {e}"))?;
            return Ok(());
        }
        // X11 fallback: xdotool
        let status = std::process::Command::new("xdotool")
            .args(["search", "--name", "deskmate-quake", "windowunmap"])
            .status()
            .map_err(|e| format!("xdotool hide: {e}"))?;
        if !status.success() {
            return Err("xdotool windowunmap failed".to_string());
        }
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("osascript")
            .arg("-e")
            .arg(r#"tell application "System Events" to set visible of process "Terminal" to false"#)
            .status()
            .map_err(|e| format!("AppleScript hide: {e}"))?;
        return Ok(());
    }

    #[cfg(target_os = "windows")]
    {
        // Windows Terminal quake mode: minimize via PowerShell
        std::process::Command::new("powershell")
            .arg("-Command")
            .arg(r#"(Get-Process -Name WindowsTerminal -ErrorAction SilentlyContinue | Select-Object -First 1).MainWindowHandle | ForEach-Object { [void][Win32.User32]::ShowWindow($_, 6) }"#)
            .status()
            .map_err(|e| format!("Windows hide: {e}"))?;
        return Ok(());
    }

    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    Err("Unsupported platform for hide_terminal".to_string())
}

/// Show the quake terminal window via compositor.
fn show_terminal(width: u32, height: u32) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        if std::env::var("SWAYSOCK").is_ok() {
            // Sway: move back to top of screen
            let mut conn = swayipc::Connection::new()
                .map_err(|e| format!("swayipc: {e}"))?;
            let cmd = format!(
                r#"[title="^deskmate-quake$"] move position 0 0, resize set {} {}"#,
                width, height
            );
            conn.run_command(&cmd)
                .map_err(|e| format!("sway show: {e}"))?;
            // Also focus the terminal
            conn.run_command(r#"[title="^deskmate-quake$"] focus"#)
                .map_err(|e| format!("sway focus: {e}"))?;
            return Ok(());
        }
        // X11 fallback: xdotool
        let status = std::process::Command::new("xdotool")
            .args(["search", "--name", "deskmate-quake", "windowmap", "windowactivate"])
            .status()
            .map_err(|e| format!("xdotool show: {e}"))?;
        if !status.success() {
            return Err("xdotool windowmap failed".to_string());
        }
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("osascript")
            .arg("-e")
            .arg(r#"tell application "Terminal" to activate"#)
            .status()
            .map_err(|e| format!("AppleScript show: {e}"))?;
        return Ok(());
    }

    #[cfg(target_os = "windows")]
    {
        // Windows Terminal quake mode: restore via PowerShell
        std::process::Command::new("powershell")
            .arg("-Command")
            .arg(r#"(Get-Process -Name WindowsTerminal -ErrorAction SilentlyContinue | Select-Object -First 1).MainWindowHandle | ForEach-Object { [void][Win32.User32]::ShowWindow($_, 9) }"#)
            .status()
            .map_err(|e| format!("Windows show: {e}"))?;
        return Ok(());
    }

    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    {
        let _ = (width, height);
        Err("Unsupported platform for show_terminal".to_string())
    }
}
