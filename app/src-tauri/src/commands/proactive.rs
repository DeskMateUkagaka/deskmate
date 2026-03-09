use std::sync::{Arc, Mutex};

use tauri::{AppHandle, Emitter, State};
use tokio::sync::watch;

use crate::openclaw::chat::ChatSession;

use super::chat::GatewayState;

/// Manages the proactive dialogue timer.
pub struct ProactiveState {
    /// Send `true` to stop the timer loop.
    stop_tx: Option<watch::Sender<bool>>,
}

impl ProactiveState {
    pub fn new() -> Self {
        Self { stop_tx: None }
    }
}

/// Start or restart the proactive dialogue timer.
///
/// The timer sends a "proactive" chat message every `interval_mins` minutes.
/// If already running, the existing timer is stopped first.
#[tauri::command]
pub async fn start_proactive(
    interval_mins: u32,
    session_key: String,
    gateway_state: State<'_, Arc<Mutex<GatewayState>>>,
    proactive_state: State<'_, Arc<Mutex<ProactiveState>>>,
    app: AppHandle,
) -> Result<(), String> {
    // Stop existing timer if any.
    stop_proactive_inner(&proactive_state);

    let (stop_tx, mut stop_rx) = watch::channel(false);
    {
        let mut ps = proactive_state.lock().unwrap();
        ps.stop_tx = Some(stop_tx);
    }

    let client = {
        let gs = gateway_state.lock().unwrap();
        gs.client.clone().ok_or("not connected")?
    };

    let interval = std::time::Duration::from_secs(interval_mins as u64 * 60);

    tokio::spawn(async move {
        log::info!(
            "Proactive dialogue started: every {} minutes",
            interval_mins
        );

        loop {
            // Wait for the interval, or stop signal.
            tokio::select! {
                _ = tokio::time::sleep(interval) => {}
                _ = stop_rx.changed() => {
                    if *stop_rx.borrow() {
                        log::info!("Proactive dialogue stopped");
                        return;
                    }
                }
            }

            // Send a proactive message.
            let chat = ChatSession::new(client.clone());
            let prompt = "The user hasn't spoken for a while. Say something interesting, \
                          a fun fact, or ask a thoughtful question. Keep it short and friendly.";

            match chat.send(session_key.clone(), prompt.to_string()).await {
                Ok(run_id) => {
                    log::info!("Proactive dialogue sent (run_id: {})", run_id);
                    let _ = app.emit("proactive-triggered", &serde_json::json!({
                        "run_id": run_id,
                    }));
                }
                Err(e) => {
                    log::warn!("Proactive dialogue failed: {}", e);
                }
            }
        }
    });

    Ok(())
}

/// Stop the proactive dialogue timer.
#[tauri::command]
pub fn stop_proactive(proactive_state: State<'_, Arc<Mutex<ProactiveState>>>) {
    stop_proactive_inner(&proactive_state);
}

fn stop_proactive_inner(proactive_state: &Arc<Mutex<ProactiveState>>) {
    let mut ps = proactive_state.lock().unwrap();
    if let Some(tx) = ps.stop_tx.take() {
        let _ = tx.send(true);
    }
}
