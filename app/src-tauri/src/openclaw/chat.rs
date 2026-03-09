use serde_json::Value;

use super::client::GatewayClient;
use super::types::{ChatAbortParams, ChatSendAck, ChatSendParams, SessionsListResult};

/// High-level chat operations on top of GatewayClient.
pub struct ChatSession {
    client: GatewayClient,
}

impl ChatSession {
    pub fn new(client: GatewayClient) -> Self {
        Self { client }
    }

    /// Send a chat message. Returns the run_id from the "started" ack.
    pub async fn send(
        &self,
        session_key: String,
        message: String,
    ) -> Result<String, String> {
        let idempotency_key = uuid::Uuid::new_v4().to_string();
        let params = ChatSendParams {
            session_key,
            message,
            idempotency_key,
        };
        let params_value = serde_json::to_value(&params)
            .map_err(|e| format!("serialize error: {e}"))?;

        let payload = self
            .client
            .request("chat.send", Some(params_value))
            .await?;

        // Ack payload: { runId: string, status: "started" }
        let ack: ChatSendAck = serde_json::from_value(payload)
            .map_err(|e| format!("ack parse error: {e}"))?;

        Ok(ack.run_id)
    }

    /// Abort an in-flight chat run.
    pub async fn abort(
        &self,
        session_key: String,
        run_id: Option<String>,
    ) -> Result<(), String> {
        let params = ChatAbortParams { session_key, run_id };
        let params_value = serde_json::to_value(&params)
            .map_err(|e| format!("serialize error: {e}"))?;
        self.client
            .request("chat.abort", Some(params_value))
            .await?;
        Ok(())
    }

    /// List available sessions via sessions.list RPC.
    pub async fn list_sessions(&self) -> Result<SessionsListResult, String> {
        let payload = self
            .client
            .request("sessions.list", Some(Value::Object(Default::default())))
            .await?;

        serde_json::from_value::<SessionsListResult>(payload)
            .map_err(|e| format!("sessions.list parse error: {e}"))
    }
}
