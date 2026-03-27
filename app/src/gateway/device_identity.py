"""Ed25519 device identity management for OpenClaw gateway authentication."""

import base64
import hashlib
import json
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from loguru import logger

from .types import ClientInfo, DeviceParams

_DEFAULT_CLIENT_ID = "gateway-client"
_DEFAULT_MODE = "ui"
_DEFAULT_ROLE = "operator"
_DEFAULT_SCOPES = "operator.admin,operator.write"


def _b64url(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class DeviceIdentity:
    """Ed25519 device identity for gateway authentication."""

    def __init__(
        self,
        device_id: str,
        signing_key: Ed25519PrivateKey,
        verifying_key: Ed25519PublicKey,
    ) -> None:
        self.device_id = device_id
        self.signing_key = signing_key
        self.verifying_key = verifying_key

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load_or_create(cls, data_dir: Path) -> "DeviceIdentity":
        """Load identity from ``{data_dir}/identity/device.json`` or create a new one."""
        path = data_dir / "identity" / "device.json"
        if path.exists():
            return cls._load(path)
        return cls._create(path)

    @classmethod
    def _load(cls, path: Path) -> "DeviceIdentity":
        logger.debug(f"Loading device identity from {path}")
        raw = json.loads(path.read_text())
        signing_key = load_pem_private_key(raw["private_key_pem"].encode(), password=None)
        verifying_key = load_pem_public_key(raw["public_key_pem"].encode())
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise ValueError("Stored private key is not Ed25519")
        if not isinstance(verifying_key, Ed25519PublicKey):
            raise ValueError("Stored public key is not Ed25519")
        return cls(
            device_id=raw["device_id"],
            signing_key=signing_key,
            verifying_key=verifying_key,
        )

    @classmethod
    def _create(cls, path: Path) -> "DeviceIdentity":
        logger.info("Generating new Ed25519 device identity")
        signing_key = Ed25519PrivateKey.generate()
        verifying_key = signing_key.public_key()

        raw_public = verifying_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        device_id = hashlib.sha256(raw_public).hexdigest()

        private_pem = signing_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode()
        public_pem = verifying_key.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()

        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "device_id": device_id,
            "private_key_pem": private_pem,
            "public_key_pem": public_pem,
        }
        path.write_text(json.dumps(payload, indent=2))
        path.chmod(0o600)
        logger.info(f"Device identity saved to {path} (device_id={device_id})")

        return cls(device_id=device_id, signing_key=signing_key, verifying_key=verifying_key)

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def sign_connect_payload(
        self,
        nonce: str,
        token: str | None,
        client_info: ClientInfo | None = None,
    ) -> DeviceParams:
        """Build a v3 auth payload, sign it with Ed25519, and return DeviceParams.

        Payload format (pipe-separated fields):
        ``v3|device_id|client_id|mode|role|scopes|signed_at_ms|token|nonce|platform|device_family``

        ``token`` and ``device_family`` are empty strings when absent.
        """
        if client_info is None:
            client_info = ClientInfo()

        signed_at = int(time.time() * 1000)
        scopes = _DEFAULT_SCOPES
        token_field = token or ""
        device_family_field = client_info.device_family or ""
        platform_field = client_info.platform or ""

        payload_str = "|".join(
            [
                "v3",
                self.device_id,
                client_info.id,
                client_info.mode,
                _DEFAULT_ROLE,
                scopes,
                str(signed_at),
                token_field,
                nonce,
                platform_field,
                device_family_field,
            ]
        )

        signature_bytes = self.signing_key.sign(payload_str.encode())
        raw_public = self.verifying_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

        return DeviceParams(
            id=self.device_id,
            public_key=_b64url(raw_public),
            signature=_b64url(signature_bytes),
            signed_at=signed_at,
            nonce=nonce,
        )
