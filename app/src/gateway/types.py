"""Data classes for the OpenClaw gateway protocol."""

import platform
from dataclasses import dataclass, field
from typing import Any


def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def to_wire(obj: Any) -> dict:
    """Recursively convert a dataclass instance to a camelCase wire dict.

    Skips keys whose values are None (omit optional fields from the wire
    payload rather than sending explicit nulls).
    """
    if not hasattr(obj, "__dataclass_fields__"):
        return obj  # type: ignore[return-value]
    result: dict = {}
    for snake_key in obj.__dataclass_fields__:
        value = getattr(obj, snake_key)
        if value is None:
            continue
        camel_key = to_camel_case(snake_key)
        if hasattr(value, "__dataclass_fields__"):
            result[camel_key] = to_wire(value)
        elif isinstance(value, list):
            result[camel_key] = [
                to_wire(item) if hasattr(item, "__dataclass_fields__") else item for item in value
            ]
        else:
            result[camel_key] = value
    return result


def _detect_platform() -> str:
    system = platform.system().lower()
    if system == "linux":
        return "linux"
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return system


@dataclass
class ClientInfo:
    id: str = "gateway-client"
    display_name: str = "DeskMate"
    version: str = "0.1.0"
    platform: str = field(default_factory=_detect_platform)
    mode: str = "ui"
    device_family: str | None = None
    instance_id: str | None = None


@dataclass
class DeviceParams:
    id: str
    public_key: str  # base64url, no padding
    signature: str  # base64url, no padding
    signed_at: int  # unix milliseconds
    nonce: str


@dataclass
class AuthParams:
    token: str | None = None
    device_token: str | None = None
    password: str | None = None


@dataclass
class ConnectParams:
    client: ClientInfo
    min_protocol: int = 3
    max_protocol: int = 3
    caps: list[str] = field(default_factory=list)
    role: str = "operator"
    scopes: list[str] = field(default_factory=lambda: ["operator.admin", "operator.write"])
    device: DeviceParams | None = None
    auth: AuthParams | None = None


@dataclass
class ChatSendParams:
    session_key: str
    message: str
    idempotency_key: str


@dataclass
class ChatSendAck:
    run_id: str
    status: str


@dataclass
class ChatEvent:
    run_id: str
    session_key: str
    seq: int
    state: str  # "delta" | "final" | "error" | "aborted"
    message: dict | None = None
    error_message: str | None = None
    usage: dict | None = None
    stop_reason: str | None = None


@dataclass
class SessionInfo:
    key: str
    display_name: str | None = None
    updated_at: int | None = None
    last_message_preview: str | None = None
