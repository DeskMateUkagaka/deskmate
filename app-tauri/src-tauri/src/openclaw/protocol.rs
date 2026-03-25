use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Wire frame sent by the client to the gateway.
///
/// Serialized directly (not via GatewayFrame) when sending to the gateway,
/// so we need the `type` field for serialization. `default` makes deserialization
/// tolerant when the field is consumed by GatewayFrame's tag discriminator.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RequestFrame {
    #[serde(rename = "type", default)]
    pub frame_type: String,
    pub id: String,
    pub method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub params: Option<Value>,
}

impl RequestFrame {
    pub fn new(id: String, method: String, params: Option<Value>) -> Self {
        Self {
            frame_type: "req".to_string(),
            id,
            method,
            params,
        }
    }
}

/// Error payload carried in a ResponseFrame when ok=false.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorPayload {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub retryable: Option<bool>,
    #[serde(rename = "retryAfterMs", skip_serializing_if = "Option::is_none")]
    pub retry_after_ms: Option<u64>,
}

/// Wire frame sent by the gateway as a response to a RequestFrame.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResponseFrame {
    pub id: String,
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub payload: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<ErrorPayload>,
}

/// Wire frame sent by the gateway to push events to the client.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventFrame {
    pub event: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub payload: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub seq: Option<u64>,
}

/// Discriminated union for deserialization of any incoming frame.
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
#[allow(dead_code)]
pub enum GatewayFrame {
    Req(RequestFrame),
    Res(ResponseFrame),
    Event(EventFrame),
}
