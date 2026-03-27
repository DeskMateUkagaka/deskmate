# Device Identity for Gateway Scopes

## Problem

The OpenClaw gateway strips self-declared scopes from clients that don't present a `device` identity in their ConnectParams. Without scopes, `chat.send` (which requires `operator.write`) fails with "missing scope: operator.write".

The TUI works because it uses the TS gateway client library which generates a device identity (Ed25519 keypair) and signs the connect payload.

## How Device Identity Works

1. **Keypair**: Generate an Ed25519 keypair once, persist to disk (device ID + PEM keys).
2. **On connect**: After receiving the `connect.challenge` nonce, build a signed payload:
   - `build_device_auth_payload_v3(device_id, client_id, client_mode, role, scopes, signed_at_ms, token, nonce, platform, device_family)`
   - Sign with Ed25519 private key
3. **Send `device` field** in ConnectParams:
   ```json
   {
     "id": "<deviceId>",
     "publicKey": "<base64url-encoded raw public key>",
     "signature": "<base64url-encoded Ed25519 signature>",
     "signedAt": <timestampMs>,
     "nonce": "<nonce from connect.challenge>"
   }
   ```
4. The nonce from `connect.challenge` is embedded in the signed payload — it is NOT discarded.

## v3 Payload Format

Pipe-separated string:
```
v3|device_id|client_id|mode|role|scopes_joined|signed_at_ms|token|nonce|platform|device_family
```

Example:
```
v3|abc123|gateway-client|ui|operator|operator.admin,operator.write|1711234567890|mytoken|servernonce|linux|
```

## Server-Side Scope Logic

When `device` is absent in ConnectParams, the server calls `clearUnboundScopes()`, stripping all self-declared scopes — **unless** the client is `openclaw-control-ui` with `allowInsecureAuth` on localhost.

## Relevant Server Files (OpenClaw repo)

- `src/gateway/server/ws-connection/message-handler.ts` — handshake, scope clearing
- `src/gateway/server/ws-connection/connect-policy.ts` — `evaluateMissingDeviceIdentity`
- `src/gateway/device-auth.ts` — `buildDeviceAuthPayload`, `buildDeviceAuthPayloadV3`
- `src/gateway/client.ts` lines 400-442 — TS reference implementation of device signing

## Implementation

Implemented in `app/src/gateway/device_identity.py`. The Python client:

1. Generates an Ed25519 keypair on first run using the `cryptography` library
2. Persists to `~/.config/deskmate/identity/device.json` (PKCS8 PEM private key, SPKI PEM public key, file permissions 0o600)
3. `device_id` = SHA-256 hex digest of raw public key bytes
4. `sign_connect_payload(nonce, token)` builds the v3 pipe-separated payload and returns a signed `DeviceParams`
5. Public key exported as base64url (no padding), signature as base64url (no padding)

On first connect, the device will need to be paired (approved) on the gateway side, same as `openclaw tui` on first use.
