"""Async WebSocket client for the OpenClaw gateway.

Dependency note: requires the ``websockets`` package.
Install with: uv pip install websockets
(Not available in the system Python environment at time of writing.)
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Callable

# websockets is not in the system Python; import is guarded so the module
# can be imported for type-checking even when the package is absent.
try:
    import websockets
    import websockets.exceptions
    from websockets.asyncio.client import connect as ws_connect

    _HAS_WEBSOCKETS = True
except ImportError:  # pragma: no cover
    _HAS_WEBSOCKETS = False

from .device_identity import DeviceIdentity
from .protocol import EventFrame, ResponseFrame, parse_frame
from .types import AuthParams, ClientInfo, ConnectParams, to_wire

logger = logging.getLogger(__name__)

# Reconnect back-off sequence (seconds)
_BACKOFF = [1, 2, 4, 8, 16, 30]


class GatewayError(Exception):
    """Raised when the gateway returns an error response."""


class GatewayClient:
    """Async WebSocket client for the OpenClaw gateway.

    Usage::

        client = GatewayClient()
        client.on_event = lambda frame: print(frame)
        client.on_status_change = lambda status: print(status)
        await client.start("wss://gateway.example.com/ws", token="...", data_dir=Path("~/.config/deskmate"))
        payload = await client.request("sessions.list", {})
        await client.stop()
    """

    def __init__(self) -> None:
        self.on_event: Callable[[EventFrame], None] | None = None
        self.on_status_change: Callable[[str], None] | None = None

        self._url: str = ""
        self._token: str | None = None
        self._data_dir: Path | None = None
        self._identity: DeviceIdentity | None = None

        self._status: str = "disconnected"
        self._pending: dict[str, asyncio.Future] = {}
        self._stop_event: asyncio.Event = asyncio.Event()
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def status(self) -> str:
        return self._status

    async def start(
        self,
        url: str,
        token: str | None = None,
        data_dir: Path | None = None,
    ) -> None:
        """Start the connection loop in a background asyncio task."""
        if not _HAS_WEBSOCKETS:
            raise RuntimeError(
                "websockets package is required but not installed. Run: uv pip install websockets"
            )
        self._url = url
        self._token = token
        self._data_dir = data_dir or Path.home() / ".config" / "deskmate"
        self._identity = DeviceIdentity.load_or_create(self._data_dir)
        self._stop_event.clear()
        self._task = asyncio.create_task(self._connection_loop(), name="gateway-client")
        logger.info("GatewayClient started, connecting to %s", url)

    async def stop(self) -> None:
        """Signal the connection loop to stop and wait for it to finish."""
        self._stop_event.set()
        self._reject_all_pending(GatewayError("Client stopped"))
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._set_status("disconnected")
        logger.info("GatewayClient stopped")

    async def request(self, method: str, params: dict | None = None) -> dict:
        """Send an RPC request and await its response payload.

        Raises ``GatewayError`` on error responses or disconnects.
        """
        if self._status not in ("connected",):
            raise GatewayError(f"Cannot send request: client is {self._status}")
        req_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[req_id] = future
        frame_json = _make_request(req_id, method, params)
        await self._send_raw(frame_json)
        return await future

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_status(self, status: str) -> None:
        if status == self._status:
            return
        self._status = status
        logger.debug("GatewayClient status -> %s", status)
        if self.on_status_change is not None:
            try:
                self.on_status_change(status)
            except Exception:
                logger.exception("on_status_change callback raised")

    async def _send_raw(self, text: str) -> None:
        """Send a raw text message on the active websocket."""
        if self._ws is None:
            raise GatewayError("No active websocket connection")
        await self._ws.send(text)

    def _reject_all_pending(self, exc: Exception) -> None:
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    async def _connection_loop(self) -> None:
        self._ws = None
        attempt = 0
        while not self._stop_event.is_set():
            self._set_status("connecting")
            try:
                async with ws_connect(self._url) as ws:
                    self._ws = ws
                    attempt = 0
                    await self._session(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("WebSocket error: %s", exc)
            finally:
                self._ws = None
                self._set_status("disconnected")
                self._reject_all_pending(GatewayError("WebSocket disconnected"))

            if self._stop_event.is_set():
                break

            backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
            attempt += 1
            logger.info("Reconnecting in %ds (attempt %d)...", backoff, attempt)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=float(backoff))
            except asyncio.TimeoutError:
                pass

    async def _session(self, ws) -> None:
        """Handle one connected WebSocket session end-to-end."""
        # Step 1: wait for connect.challenge
        nonce = await self._wait_for_challenge(ws)

        # Step 2: authenticate
        await self._authenticate(ws, nonce)

        # Step 3: main read loop
        self._set_status("connected")
        async for raw in ws:
            if isinstance(raw, bytes):
                raw = raw.decode()
            frame = parse_frame(raw)
            if isinstance(frame, ResponseFrame):
                self._dispatch_response(frame)
            elif isinstance(frame, EventFrame):
                self._dispatch_event(frame)

    async def _wait_for_challenge(self, ws) -> str:
        """Read messages until we receive a ``connect.challenge`` event."""
        async for raw in ws:
            if isinstance(raw, bytes):
                raw = raw.decode()
            frame = parse_frame(raw)
            if isinstance(frame, EventFrame) and frame.event == "connect.challenge":
                nonce = (frame.payload or {}).get("nonce", "")
                logger.debug("Received challenge nonce: %s", nonce)
                return nonce
            logger.debug("Pre-auth message ignored: %s", raw[:100])
        raise GatewayError("WebSocket closed before challenge arrived")

    async def _authenticate(self, ws, nonce: str) -> None:
        """Build ConnectParams, sign, send ``connect`` RPC, wait for HelloOk."""
        assert self._identity is not None
        client_info = ClientInfo()
        device_params = self._identity.sign_connect_payload(nonce, self._token, client_info)
        auth = AuthParams(token=self._token) if self._token else None
        connect_params = ConnectParams(
            client=client_info,
            device=device_params,
            auth=auth,
        )
        req_id = str(uuid.uuid4())
        frame_json = _make_request(req_id, "connect", to_wire(connect_params))
        await ws.send(frame_json)
        logger.debug("Sent connect request (id=%s)", req_id)

        # Wait for the response to our connect request
        async for raw in ws:
            if isinstance(raw, bytes):
                raw = raw.decode()
            frame = parse_frame(raw)
            if isinstance(frame, ResponseFrame) and frame.id == req_id:
                if not frame.ok:
                    err = (frame.error or {}).get("message", "connect rejected")
                    raise GatewayError(f"Gateway rejected connect: {err}")
                logger.info("Gateway authenticated (HelloOk)")
                return
            # Events before auth response are unusual but not fatal — log and continue
            logger.debug("Pre-auth-response message: %s", raw[:100])
        raise GatewayError("WebSocket closed before connect response")

    def _dispatch_response(self, frame: ResponseFrame) -> None:
        future = self._pending.pop(frame.id, None)
        if future is None:
            logger.debug("No pending request for response id=%s", frame.id)
            return
        if future.done():
            return
        if frame.ok:
            future.set_result(frame.payload or {})
        else:
            msg = (frame.error or {}).get("message", "gateway error")
            future.set_exception(GatewayError(msg))

    def _dispatch_event(self, frame: EventFrame) -> None:
        if self.on_event is not None:
            try:
                self.on_event(frame)
            except Exception:
                logger.exception("on_event callback raised")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_request(req_id: str, method: str, params: dict | None) -> str:
    import json

    d: dict = {"type": "req", "id": req_id, "method": method}
    if params is not None:
        d["params"] = params
    return json.dumps(d)
