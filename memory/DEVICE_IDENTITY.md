# Device Identity for Gateway Scopes

## Problem

The OpenClaw gateway strips self-declared scopes from clients that don't present a `device` identity in their ConnectParams. Without scopes, `chat.send` (which requires `operator.write`) fails with "missing scope: operator.write".

The TUI works because it uses the TS gateway client library which generates a device identity (Ed25519 keypair) and signs the connect payload.

## How Device Identity Works (from `~/work/openclaw/src/gateway/client.ts`)

1. **Keypair**: Generate an Ed25519 keypair once, persist to disk (device ID + PEM keys).
2. **On connect**: After receiving the `connect.challenge` nonce, build a signed payload:
   - `buildDeviceAuthPayloadV3({ deviceId, clientId, clientMode, role, scopes, signedAtMs, token, nonce, platform, deviceFamily })`
   - Sign with `signDevicePayload(privateKeyPem, payload)`
3. **Send `device` field** in ConnectParams:
   ```json
   {
     "id": "<deviceId>",
     "publicKey": "<base64url-encoded raw public key>",
     "signature": "<signature>",
     "signedAt": <timestampMs>,
     "nonce": "<nonce from connect.challenge>"
   }
   ```
4. The nonce from `connect.challenge` is embedded in the signed payload — it is NOT discarded.

## Server-Side Scope Logic (`~/work/openclaw/src/gateway/server/ws-connection/message-handler.ts`)

Lines 509-548: When `device` is absent, `clearUnboundScopes()` is called, stripping all self-declared scopes — **unless** the client is `openclaw-control-ui` with `allowInsecureAuth` on localhost.

## Relevant Server Files

- `src/gateway/server/ws-connection/message-handler.ts` — handshake, scope clearing
- `src/gateway/server/ws-connection/connect-policy.ts` — `evaluateMissingDeviceIdentity`
- `src/gateway/role-policy.ts` — `roleCanSkipDeviceIdentity`
- `src/gateway/method-scopes.ts` — which methods require which scopes
- `src/gateway/device-auth.ts` — `buildDeviceAuthPayload`, `buildDeviceAuthPayloadV3`
- `src/gateway/protocol/client-info.ts` — valid client IDs and modes
- `src/gateway/client.ts` lines 400-442 — TS reference implementation of device signing

## Implementation

Implemented in `app/src-tauri/src/openclaw/device_identity.rs`. The Rust client generates an Ed25519 keypair on first run (persisted to `<app_data_dir>/identity/device.json`), signs the v3 connect payload with the challenge nonce, and sends the `device` field in ConnectParams — matching the TS gateway client behavior.

On first connect, the device will need to be paired (approved) on the gateway side, same as `openclaw tui` on first use.
