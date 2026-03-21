use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use tokio::sync::{broadcast, oneshot};
use tokio::time::sleep;
use tokio_tungstenite::connect_async;
use tokio_tungstenite::tungstenite::Message;

use tauri::{AppHandle, Emitter};

use super::protocol::{EventFrame, GatewayFrame, RequestFrame};
use super::types::{ConnectParams, HelloOk};

/// Status of the gateway connection.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConnectionStatus {
    Disconnected,
    Connecting,
    Connected,
}

/// Internal state shared between the actor task and external callers.
struct Inner {
    status: ConnectionStatus,
    /// Pending requests waiting for a ResponseFrame by request ID.
    pending: HashMap<String, oneshot::Sender<Result<Value, String>>>,
    /// Tick interval from server policy (ms).
    tick_interval_ms: u64,
}

impl Inner {
    fn new() -> Self {
        Self {
            status: ConnectionStatus::Disconnected,
            pending: HashMap::new(),
            tick_interval_ms: 30_000,
        }
    }
}

/// Commands sent from the GatewayClient handle into the actor task.
enum ClientCmd {
    /// Send a request frame; response arrives on the oneshot sender.
    Request {
        id: String,
        method: String,
        params: Option<Value>,
        tx: oneshot::Sender<Result<Value, String>>,
    },
    /// Gracefully shut down the actor.
    Stop,
}

/// Handle to a running GatewayClient actor.
///
/// Clone-safe: all clones share the same underlying actor.
#[derive(Clone)]
pub struct GatewayClient {
    cmd_tx: tokio::sync::mpsc::UnboundedSender<ClientCmd>,
    inner: Arc<Mutex<Inner>>,
    event_tx: broadcast::Sender<EventFrame>,
}

impl GatewayClient {
    /// Start the gateway client actor connecting to `url`.
    pub fn start(url: String, token: Option<String>, app_handle: AppHandle) -> Self {
        let (cmd_tx, cmd_rx) = tokio::sync::mpsc::unbounded_channel();
        let (event_tx, _) = broadcast::channel(256);
        let inner = Arc::new(Mutex::new(Inner::new()));

        let actor = ClientActor {
            url,
            token,
            cmd_rx,
            inner: Arc::clone(&inner),
            event_tx: event_tx.clone(),
            app_handle,
        };

        tokio::spawn(actor.run());

        GatewayClient {
            cmd_tx,
            inner,
            event_tx,
        }
    }

    /// Current connection status.
    pub fn status(&self) -> ConnectionStatus {
        self.inner.lock().unwrap().status.clone()
    }

    /// Subscribe to all gateway events.
    pub fn subscribe(&self) -> broadcast::Receiver<EventFrame> {
        self.event_tx.subscribe()
    }

    /// Send a request and await the response payload.
    pub async fn request(&self, method: &str, params: Option<Value>) -> Result<Value, String> {
        let id = uuid::Uuid::new_v4().to_string();
        let (tx, rx) = oneshot::channel();
        self.cmd_tx
            .send(ClientCmd::Request {
                id,
                method: method.to_string(),
                params,
                tx,
            })
            .map_err(|_| "gateway client stopped".to_string())?;
        rx.await.map_err(|_| "gateway client dropped request".to_string())?
    }

    /// Stop the client actor.
    pub fn stop(&self) {
        let _ = self.cmd_tx.send(ClientCmd::Stop);
    }
}

/// The actor that owns the WebSocket connection.
struct ClientActor {
    url: String,
    token: Option<String>,
    cmd_rx: tokio::sync::mpsc::UnboundedReceiver<ClientCmd>,
    inner: Arc<Mutex<Inner>>,
    event_tx: broadcast::Sender<EventFrame>,
    app_handle: AppHandle,
}

impl ClientActor {
    async fn run(mut self) {
        let mut backoff_ms: u64 = 1_000;

        loop {
            self.set_status(ConnectionStatus::Connecting);

            match self.connect_once(&mut backoff_ms).await {
                Ok(()) => {}
                Err(stop) if stop => {
                    self.set_status(ConnectionStatus::Disconnected);
                    return;
                }
                Err(_) => {}
            }

            self.set_status(ConnectionStatus::Disconnected);
            // Flush all pending requests with an error.
            self.flush_pending_errors("gateway disconnected");
            // Drain any queued commands that arrived while we were trying to connect.
            self.drain_queued_commands();

            let delay = backoff_ms;
            backoff_ms = (backoff_ms * 2).min(30_000);
            sleep(Duration::from_millis(delay)).await;
        }
    }

    /// Returns Ok(()) on clean disconnect, Err(true) on Stop command, Err(false) on error.
    async fn connect_once(&mut self, backoff_ms: &mut u64) -> Result<(), bool> {
        log::info!("gateway: attempting WebSocket connect to {}", self.url);
        let ws_stream = match connect_async(&self.url).await {
            Ok((ws, _)) => {
                log::info!("gateway: WebSocket connected, waiting for challenge...");
                ws
            }
            Err(e) => {
                log::warn!("gateway connection failed: {e}");
                return Err(false);
            }
        };

        let (mut write, mut read) = ws_stream.split();

        // Wait for connect.challenge event.
        let nonce = loop {
            match read.next().await {
                Some(Ok(Message::Text(text))) => {
                    log::debug!("gateway: raw frame: {}", text);
                    match serde_json::from_str::<GatewayFrame>(&text) {
                        Err(e) => {
                            log::warn!("gateway: challenge phase parse error: {e}  raw={text}");
                        }
                        Ok(GatewayFrame::Event(evt)) if evt.event == "connect.challenge" => {
                            if let Some(nonce) = evt
                                .payload
                                .as_ref()
                                .and_then(|p| p.get("nonce"))
                                .and_then(|n| n.as_str())
                                .map(|s| s.trim().to_string())
                                .filter(|s| !s.is_empty())
                            {
                                break nonce;
                            } else {
                                log::error!("gateway connect.challenge missing nonce");
                                return Err(false);
                            }
                        }
                        Ok(other) => {
                            log::debug!("gateway: challenge phase ignoring frame: {:?}", other);
                        }
                    }
                }
                Some(Ok(_)) => {} // skip non-text frames
                Some(Err(e)) => {
                    log::warn!("gateway ws error waiting for challenge: {e}");
                    return Err(false);
                }
                None => return Err(false),
            }
        };

        // Send "connect" request with ConnectParams.
        log::info!("gateway: got challenge nonce, sending connect request...");
        let connect_id = uuid::Uuid::new_v4().to_string();
        let connect_params = ConnectParams::new(self.token.clone());
        let _ = nonce; // nonce stored in server; we just need to have received it
        let req = RequestFrame::new(
            connect_id.clone(),
            "connect".to_string(),
            Some(serde_json::to_value(&connect_params).unwrap_or(Value::Null)),
        );
        let req_text = serde_json::to_string(&req).unwrap();
        log::debug!("gateway: connect request: {}", req_text);
        if let Err(e) = write.send(Message::Text(req_text.into())).await {
            log::warn!("gateway failed to send connect: {e}");
            return Err(false);
        }
        log::info!("gateway: connect request sent, waiting for hello...");

        // Wait for the connect response.
        let hello: HelloOk = loop {
            match read.next().await {
                Some(Ok(Message::Text(text))) => {
                    log::debug!("gateway: hello-wait raw frame: {}", text);
                    if let Ok(GatewayFrame::Res(res)) = serde_json::from_str::<GatewayFrame>(&text) {
                        if res.id == connect_id {
                            if !res.ok {
                                let msg = res
                                    .error
                                    .as_ref()
                                    .map(|e| e.message.clone())
                                    .unwrap_or_else(|| "connect rejected".to_string());
                                log::error!("gateway connect rejected: {msg}");
                                return Err(false);
                            }
                            let payload = res.payload.unwrap_or(Value::Null);
                            match serde_json::from_value::<HelloOk>(payload) {
                                Ok(h) => break h,
                                Err(e) => {
                                    log::error!("gateway hello-ok parse error: {e}");
                                    return Err(false);
                                }
                            }
                        }
                    }
                }
                Some(Ok(_)) => {}
                Some(Err(e)) => {
                    log::warn!("gateway ws error waiting for hello: {e}");
                    return Err(false);
                }
                None => return Err(false),
            }
        };

        // Connected successfully.
        let tick_interval_ms = hello.policy.tick_interval_ms;
        self.set_status(ConnectionStatus::Connected);
        self.inner.lock().unwrap().tick_interval_ms = tick_interval_ms;
        *backoff_ms = 1_000; // reset backoff on successful connect
        log::info!("gateway connected (server {})", hello.server.version);

        // Main read/write loop.
        loop {
            tokio::select! {
                msg = read.next() => {
                    match msg {
                        Some(Ok(Message::Text(text))) => {
                            self.handle_message(&text);
                        }
                        Some(Ok(Message::Ping(data))) => {
                            let _ = write.send(Message::Pong(data)).await;
                        }
                        Some(Ok(_)) => {}
                        Some(Err(e)) => {
                            log::warn!("gateway ws read error: {e}");
                            return Err(false);
                        }
                        None => return Ok(()),
                    }
                }
                cmd = self.cmd_rx.recv() => {
                    match cmd {
                        None => return Err(true),
                        Some(ClientCmd::Stop) => return Err(true),
                        Some(ClientCmd::Request { id, method, params, tx }) => {
                            let req = RequestFrame::new(id.clone(), method, params);
                            let text = serde_json::to_string(&req).unwrap();
                            if let Err(e) = write.send(Message::Text(text.into())).await {
                                log::warn!("gateway send error: {e}");
                                let _ = tx.send(Err("send failed".to_string()));
                            } else {
                                self.inner.lock().unwrap().pending.insert(id, tx);
                            }
                        }
                    }
                }
            }
        }
    }

    fn handle_message(&self, text: &str) {
        match serde_json::from_str::<GatewayFrame>(text) {
            Ok(GatewayFrame::Res(res)) => {
                let tx = self.inner.lock().unwrap().pending.remove(&res.id);
                if let Some(tx) = tx {
                    if res.ok {
                        let _ = tx.send(Ok(res.payload.unwrap_or(Value::Null)));
                    } else {
                        let msg = res
                            .error
                            .as_ref()
                            .map(|e| e.message.clone())
                            .unwrap_or_else(|| "unknown error".to_string());
                        let _ = tx.send(Err(msg));
                    }
                }
            }
            Ok(GatewayFrame::Event(evt)) => {
                // Broadcast to all subscribers; ignore send errors (no receivers).
                let _ = self.event_tx.send(evt);
            }
            Ok(GatewayFrame::Req(_)) => {
                // Gateway should not send req frames to clients; ignore.
            }
            Err(e) => {
                log::debug!("gateway frame parse error: {e}  raw={text}");
            }
        }
    }

    fn set_status(&self, status: ConnectionStatus) {
        self.inner.lock().unwrap().status = status.clone();
        let status_str = match &status {
            ConnectionStatus::Disconnected => "disconnected",
            ConnectionStatus::Connecting => "connecting",
            ConnectionStatus::Connected => "connected",
        };
        let _ = self.app_handle.emit("connection-status-changed", status_str);
    }

    fn flush_pending_errors(&self, msg: &str) {
        let mut inner = self.inner.lock().unwrap();
        for (_, tx) in inner.pending.drain() {
            let _ = tx.send(Err(msg.to_string()));
        }
    }

    /// Drain any commands queued in the mpsc channel while disconnected,
    /// rejecting them immediately so callers don't hang forever.
    fn drain_queued_commands(&mut self) {
        while let Ok(cmd) = self.cmd_rx.try_recv() {
            match cmd {
                ClientCmd::Request { tx, .. } => {
                    let _ = tx.send(Err("gateway not connected".to_string()));
                }
                ClientCmd::Stop => {
                    self.set_status(ConnectionStatus::Disconnected);
                    return;
                }
            }
        }
    }
}
