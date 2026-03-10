use std::sync::{Arc, Mutex};

use tauri::{AppHandle, Emitter, State};

use crate::openclaw::chat::ChatSession;
use crate::openclaw::client::{ConnectionStatus, GatewayClient};
use crate::openclaw::types::{ChatEvent, SessionInfo};

/// App-managed state for the gateway connection.
pub struct GatewayState {
    pub client: Option<GatewayClient>,
}

impl GatewayState {
    pub fn new() -> Self {
        Self { client: None }
    }
}

/// Connect (or reconnect) to the OpenClaw gateway.
///
/// Spawns the read loop and starts emitting `chat-event` Tauri events.
#[tauri::command]
pub async fn connect_gateway(
    url: String,
    token: Option<String>,
    state: State<'_, Arc<Mutex<GatewayState>>>,
    app: AppHandle,
) -> Result<(), String> {
    // Stop existing client if any.
    {
        let mut gs = state.lock().unwrap();
        if let Some(old) = gs.client.take() {
            old.stop();
        }
    }

    log::info!("connect_gateway called: url={url}");
    let client = GatewayClient::start(url, token);
    let mut event_rx = client.subscribe();

    // Spawn a task that forwards gateway events to the Tauri frontend.
    let app_clone = app.clone();
    tokio::spawn(async move {
        loop {
            match event_rx.recv().await {
                Ok(evt) => {
                    log::info!("gateway event: type={} seq={:?}", evt.event, evt.seq);
                    if evt.event == "chat" {
                        if let Some(payload) = &evt.payload {
                            match serde_json::from_value::<ChatEvent>(payload.clone()) {
                                Ok(chat_evt) => {
                                    log::info!("chat event: state={} runId={}", chat_evt.state, chat_evt.run_id);
                                    let _ = app_clone.emit("chat-event", &chat_evt);
                                }
                                Err(e) => {
                                    log::warn!("chat event parse error: {e}  payload={payload}");
                                }
                            }
                        } else {
                            log::warn!("chat event with no payload");
                        }
                    }
                    // Forward all gateway events for frontend visibility.
                    let _ = app_clone.emit("gateway-event", &serde_json::json!({
                        "event": evt.event,
                        "payload": evt.payload,
                        "seq": evt.seq,
                    }));
                }
                Err(tokio::sync::broadcast::error::RecvError::Lagged(n)) => {
                    log::warn!("gateway event listener lagged by {n} messages");
                }
                Err(tokio::sync::broadcast::error::RecvError::Closed) => {
                    // Client was stopped.
                    break;
                }
            }
        }
    });

    state.lock().unwrap().client = Some(client);
    Ok(())
}

/// Returns the current connection status as a string.
#[tauri::command]
pub fn get_connection_status(state: State<'_, Arc<Mutex<GatewayState>>>) -> String {
    let gs = state.lock().unwrap();
    match &gs.client {
        None => "disconnected".to_string(),
        Some(c) => match c.status() {
            ConnectionStatus::Connected => "connected".to_string(),
            ConnectionStatus::Connecting => "connecting".to_string(),
            ConnectionStatus::Disconnected => "disconnected".to_string(),
        },
    }
}

/// List available chat sessions.
#[tauri::command]
pub async fn list_sessions(
    state: State<'_, Arc<Mutex<GatewayState>>>,
) -> Result<Vec<SessionInfo>, String> {
    let client = {
        let gs = state.lock().unwrap();
        gs.client.clone().ok_or("not connected")?
    };
    let chat = ChatSession::new(client);
    let result = chat.list_sessions().await?;
    Ok(result.sessions)
}

/// Send a chat message. Returns the run_id.
#[tauri::command]
pub async fn chat_send(
    session_key: String,
    message: String,
    state: State<'_, Arc<Mutex<GatewayState>>>,
) -> Result<String, String> {
    let client = {
        let gs = state.lock().unwrap();
        gs.client.clone().ok_or("not connected")?
    };
    let chat = ChatSession::new(client);
    chat.send(session_key, message).await
}

/// Abort an in-flight chat run.
#[tauri::command]
pub async fn chat_abort(
    session_key: String,
    run_id: String,
    state: State<'_, Arc<Mutex<GatewayState>>>,
) -> Result<(), String> {
    let client = {
        let gs = state.lock().unwrap();
        gs.client.clone().ok_or("not connected")?
    };
    let chat = ChatSession::new(client);
    chat.abort(session_key, Some(run_id)).await
}
