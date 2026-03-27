"""Frame serialization/deserialization for the OpenClaw gateway protocol."""

import json
from dataclasses import dataclass

from loguru import logger


@dataclass
class RequestFrame:
    id: str
    method: str
    params: dict | None = None

    def to_json(self) -> str:
        d: dict = {"type": "req", "id": self.id, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        return json.dumps(d)


@dataclass
class ResponseFrame:
    id: str
    ok: bool
    payload: dict | None = None
    error: dict | None = None


@dataclass
class EventFrame:
    event: str
    payload: dict | None = None
    seq: int | None = None


def parse_frame(text: str) -> RequestFrame | ResponseFrame | EventFrame:
    """Parse a JSON text message into a typed frame.

    Handles three shapes:
    - ``{"type": "req", ...}``    -> RequestFrame
    - ``{"type": "res", ...}``    -> ResponseFrame
    - ``{"type": "event", ...}``  -> EventFrame
    - ``{"id": ..., "ok": ...}``  -> ResponseFrame (type field omitted by some servers)
    - ``{"event": ...}``          -> EventFrame (type field omitted by some servers)
    """
    data: dict = json.loads(text)
    frame_type = data.get("type")

    if frame_type == "req":
        return RequestFrame(
            id=data["id"],
            method=data["method"],
            params=data.get("params"),
        )

    if frame_type == "res" or (frame_type is None and "id" in data and "ok" in data):
        return ResponseFrame(
            id=data["id"],
            ok=bool(data["ok"]),
            payload=data.get("payload") or data.get("result"),
            error=data.get("error"),
        )

    if frame_type == "event" or (frame_type is None and "event" in data):
        return EventFrame(
            event=data["event"],
            payload=data.get("payload"),
            seq=data.get("seq"),
        )

    logger.warning("Unknown frame shape: %s", text[:200])
    # Return a best-effort EventFrame so callers can at least log it
    return EventFrame(event="__unknown__", payload=data)
