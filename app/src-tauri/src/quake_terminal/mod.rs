pub mod detect;
pub mod spawn;
pub mod toggle;

use std::process::Child;

/// Managed state for the quake terminal process.
pub struct QuakeTerminalState {
    /// The running terminal process, if any.
    pub process: Option<Child>,
    /// Whether the terminal is currently visible.
    pub visible: bool,
    /// The detected (or user-overridden) terminal emulator name.
    pub terminal_name: Option<String>,
}

impl QuakeTerminalState {
    pub fn new() -> Self {
        Self {
            process: None,
            visible: false,
            terminal_name: None,
        }
    }
}
