use serde::{Deserialize, Serialize};
use serde_json::Value;

// ---------------------------------------------------------------------------
// Connect / Hello
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientInfo {
    /// Must be "gateway-client" for this app.
    pub id: String,
    #[serde(rename = "displayName", skip_serializing_if = "Option::is_none")]
    pub display_name: Option<String>,
    pub version: String,
    pub platform: String,
    #[serde(rename = "deviceFamily", skip_serializing_if = "Option::is_none")]
    pub device_family: Option<String>,
    /// Must be "ui" for this app.
    pub mode: String,
    #[serde(rename = "instanceId", skip_serializing_if = "Option::is_none")]
    pub instance_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthParams {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token: Option<String>,
    #[serde(rename = "deviceToken", skip_serializing_if = "Option::is_none")]
    pub device_token: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub password: Option<String>,
}

/// Sent as params for the "connect" method after receiving connect.challenge.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectParams {
    #[serde(rename = "minProtocol")]
    pub min_protocol: u32,
    #[serde(rename = "maxProtocol")]
    pub max_protocol: u32,
    pub client: ClientInfo,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub caps: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scopes: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub auth: Option<AuthParams>,
}

impl ConnectParams {
    /// Build a default ConnectParams for the ukagaka UI client.
    pub fn new(token: Option<String>) -> Self {
        ConnectParams {
            min_protocol: 3,
            max_protocol: 3,
            client: ClientInfo {
                id: "gateway-client".to_string(),
                display_name: Some("Ukagaka".to_string()),
                version: env!("CARGO_PKG_VERSION").to_string(),
                platform: std::env::consts::OS.to_string(),
                device_family: None,
                mode: "ui".to_string(),
                instance_id: None,
            },
            caps: Some(vec![]),
            role: Some("operator".to_string()),
            scopes: Some(vec!["operator.admin".to_string()]),
            auth: token.map(|t| AuthParams {
                token: Some(t),
                device_token: None,
                password: None,
            }),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerInfo {
    pub version: String,
    #[serde(rename = "connId")]
    pub conn_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Features {
    pub methods: Vec<String>,
    pub events: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Policy {
    #[serde(rename = "tickIntervalMs")]
    pub tick_interval_ms: u64,
    #[serde(rename = "maxPayload")]
    pub max_payload: u64,
    #[serde(rename = "maxBufferedBytes")]
    pub max_buffered_bytes: u64,
}

/// Payload from the "connect" response when ok=true.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HelloOk {
    pub server: ServerInfo,
    pub features: Features,
    pub policy: Policy,
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatSendParams {
    #[serde(rename = "sessionKey")]
    pub session_key: String,
    pub message: String,
    #[serde(rename = "idempotencyKey")]
    pub idempotency_key: String,
}

/// Ack payload returned by the gateway for chat.send (status="started").
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatSendAck {
    #[serde(rename = "runId")]
    pub run_id: String,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatAbortParams {
    #[serde(rename = "sessionKey")]
    pub session_key: String,
    #[serde(rename = "runId", skip_serializing_if = "Option::is_none")]
    pub run_id: Option<String>,
}

/// A single content block inside a ChatMessage.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContentBlock {
    #[serde(rename = "type")]
    pub block_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
}

/// The message payload within a ChatEvent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: Vec<ContentBlock>,
}

/// Event payload for EventFrame { event: "chat" }.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatEvent {
    #[serde(rename = "runId")]
    pub run_id: String,
    #[serde(rename = "sessionKey")]
    pub session_key: String,
    pub seq: u64,
    /// "delta" | "final" | "error" | "aborted"
    pub state: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<ChatMessage>,
    #[serde(rename = "errorMessage", skip_serializing_if = "Option::is_none")]
    pub error_message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage: Option<Value>,
    #[serde(rename = "stopReason", skip_serializing_if = "Option::is_none")]
    pub stop_reason: Option<String>,
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionInfo {
    pub key: String,
    #[serde(rename = "displayName", skip_serializing_if = "Option::is_none")]
    pub display_name: Option<String>,
    #[serde(rename = "updatedAt", skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<i64>,
    #[serde(rename = "lastMessagePreview", skip_serializing_if = "Option::is_none")]
    pub last_message_preview: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionsListResult {
    pub sessions: Vec<SessionInfo>,
}
