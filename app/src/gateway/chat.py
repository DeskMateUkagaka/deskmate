"""High-level ChatSession API built on top of GatewayClient."""

import logging
from uuid import uuid4

from .client import GatewayClient
from .types import ChatSendParams, SessionInfo, to_wire

logger = logging.getLogger(__name__)


class ChatSession:
    """High-level API for OpenClaw chat operations.

    Chat events (streaming deltas, final responses) are delivered via
    ``GatewayClient.on_event`` — register your callback there before calling
    ``send()``.

    Usage::

        client = GatewayClient()
        session = ChatSession(client)
        await client.start("wss://...", token="...")
        run_id = await session.send("my-session", "Hello!")
        # GatewayClient.on_event fires with ChatEvent frames as the AI replies
    """

    def __init__(self, client: GatewayClient) -> None:
        self.client = client

    async def send(self, session_key: str, message: str) -> str:
        """Send a chat message and return the run_id from the ack.

        The gateway returns an immediate ack ``{runId, status: "started"}``.
        AI response chunks arrive as separate ``chat`` EventFrames delivered
        via ``client.on_event``.
        """
        params = ChatSendParams(
            session_key=session_key,
            message=message,
            idempotency_key=str(uuid4()),
        )
        payload = await self.client.request("chat.send", to_wire(params))
        run_id: str = payload["runId"]
        logger.debug("chat.send ack: runId=%s status=%s", run_id, payload.get("status"))
        return run_id

    async def abort(self, session_key: str, run_id: str | None = None) -> None:
        """Abort an in-progress chat run.

        If ``run_id`` is None the server aborts the most recent run for the
        session.
        """
        params: dict = {"sessionKey": session_key}
        if run_id is not None:
            params["runId"] = run_id
        await self.client.request("chat.abort", params)
        logger.debug("chat.abort sent for session=%s run=%s", session_key, run_id)

    async def list_sessions(self) -> list[SessionInfo]:
        """Return the list of sessions visible to the authenticated operator."""
        payload = await self.client.request("sessions.list", {})
        sessions = payload.get("sessions", [])
        result: list[SessionInfo] = []
        for raw in sessions:
            result.append(
                SessionInfo(
                    key=raw.get("key", ""),
                    display_name=raw.get("displayName"),
                    updated_at=raw.get("updatedAt"),
                    last_message_preview=raw.get("lastMessagePreview"),
                )
            )
        return result
