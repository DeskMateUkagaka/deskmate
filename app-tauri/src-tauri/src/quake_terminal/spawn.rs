use std::process::{Child, Command};

/// Spawn a terminal running the given command at the specified geometry.
/// Returns the Child process handle.
pub fn spawn_terminal(
    terminal: &str,
    command: &str,
    width: u32,
    height: u32,
) -> Result<Child, String> {
    log::info!("Spawning terminal: {terminal} with command: {command} ({width}x{height})");

    // Split the command string into program + args for -e flag
    let cmd_parts: Vec<&str> = command.split_whitespace().collect();
    if cmd_parts.is_empty() {
        return Err("Empty command".to_string());
    }

    let child = match terminal {
        #[cfg(target_os = "linux")]
        "foot" => {
            Command::new("foot")
                .arg("--title=deskmate-quake")
                .arg(format!("--window-size-pixels={}x{}", width, height))
                .arg("-e")
                .args(&cmd_parts)
                .spawn()
        }
        #[cfg(target_os = "linux")]
        "kitty" => {
            Command::new("kitty")
                .arg("--title")
                .arg("deskmate-quake")
                .arg("-o")
                .arg(format!("initial_window_width={width}"))
                .arg("-o")
                .arg(format!("initial_window_height={height}"))
                .arg("-e")
                .args(&cmd_parts)
                .spawn()
        }
        #[cfg(target_os = "linux")]
        "alacritty" => {
            Command::new("alacritty")
                .arg("--title")
                .arg("deskmate-quake")
                .arg("-e")
                .args(&cmd_parts)
                .spawn()
            // alacritty doesn't support pixel-based sizing via CLI well;
            // rely on compositor to resize after spawn
        }
        #[cfg(target_os = "linux")]
        "konsole" => {
            Command::new("konsole")
                .arg("--title")
                .arg("deskmate-quake")
                .arg("-e")
                .args(&cmd_parts)
                .spawn()
        }
        #[cfg(target_os = "linux")]
        "xterm" => {
            Command::new("xterm")
                .arg("-title")
                .arg("deskmate-quake")
                .arg(format!("-geometry={}x{}+0+0", width / 8, height / 16)) // approximate char cells
                .arg("-e")
                .args(&cmd_parts)
                .spawn()
        }
        #[cfg(target_os = "linux")]
        "xfce4-terminal" => {
            Command::new("xfce4-terminal")
                .arg("--title=deskmate-quake")
                .arg("-e")
                .arg(command) // xfce4-terminal takes command as single string
                .spawn()
        }
        #[cfg(target_os = "macos")]
        "iterm2" => {
            // Use AppleScript to open iTerm2 with the command
            let script = format!(
                r#"tell application "iTerm2"
                    create window with default profile command "{command}"
                end tell"#,
            );
            Command::new("osascript")
                .arg("-e")
                .arg(&script)
                .spawn()
        }
        #[cfg(target_os = "macos")]
        "terminal.app" => {
            Command::new("open")
                .arg("-a")
                .arg("Terminal")
                .arg("-n")
                .arg("--args")
                .args(&cmd_parts)
                .spawn()
        }
        #[cfg(target_os = "macos")]
        "kitty" | "alacritty" => {
            // Same CLI flags work on macOS
            Command::new(terminal)
                .arg("--title")
                .arg("deskmate-quake")
                .arg("-e")
                .args(&cmd_parts)
                .spawn()
        }
        #[cfg(target_os = "windows")]
        "wt" => {
            // Windows Terminal built-in quake mode
            let mut cmd = Command::new("wt");
            cmd.arg("--window").arg("_quake");
            // Pass command if not the default shell
            if !command.is_empty() {
                cmd.args(&cmd_parts);
            }
            cmd.spawn()
        }
        #[cfg(target_os = "windows")]
        "powershell" => {
            Command::new("powershell.exe")
                .arg("-NoExit")
                .arg("-Command")
                .arg(command)
                .spawn()
        }
        _ => {
            // Generic fallback: try running the terminal with -e
            Command::new(terminal)
                .arg("--title")
                .arg("deskmate-quake")
                .arg("-e")
                .args(&cmd_parts)
                .spawn()
        }
    }
    .map_err(|e| format!("Failed to spawn terminal '{terminal}': {e}"))?;

    log::info!("Terminal spawned with PID: {}", child.id());
    Ok(child)
}

/// Position a terminal window on Sway using swayipc.
/// Retries up to 10 times (the window may not be in the compositor tree immediately).
#[cfg(target_os = "linux")]
pub async fn sway_position_terminal(width: u32, height: u32) -> Result<(), String> {
    let cmd = format!(
        r#"[title="^deskmate-quake$"] floating enable, resize set {} {}, move position 0 0"#,
        width, height
    );

    for attempt in 1..=10 {
        let mut conn = swayipc::Connection::new()
            .map_err(|e| format!("swayipc connection failed: {e}"))?;

        match conn.run_command(&cmd) {
            Ok(outcomes) if outcomes.iter().all(|o| o.is_ok()) => {
                log::info!("Positioned quake terminal via swayipc");
                return Ok(());
            }
            Ok(outcomes) => {
                let errs: Vec<_> = outcomes.iter().filter_map(|o| o.as_ref().err()).collect();
                if errs.iter().any(|e| format!("{e}").contains("No matching node")) && attempt < 10 {
                    log::info!("Quake terminal not in sway tree yet, retry {attempt}/10");
                    tokio::time::sleep(std::time::Duration::from_millis(100)).await;
                    continue;
                }
                return Err(format!("sway position command failed: {errs:?}"));
            }
            Err(e) => {
                return Err(format!("swayipc run_command failed: {e}"));
            }
        }
    }
    Err("Failed to position quake terminal after 10 retries".to_string())
}
