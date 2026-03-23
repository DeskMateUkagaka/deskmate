use std::fs;
use std::path::{Path, PathBuf};

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use ed25519_dalek::{SigningKey, VerifyingKey};
use sha2::{Digest, Sha256};

use serde::{Deserialize, Serialize};

/// Persistent device identity (Ed25519 keypair).
#[derive(Clone)]
pub struct DeviceIdentity {
    pub device_id: String,
    pub signing_key: SigningKey,
    pub verifying_key: VerifyingKey,
}

#[derive(Serialize, Deserialize)]
struct StoredIdentity {
    version: u32,
    #[serde(rename = "deviceId")]
    device_id: String,
    #[serde(rename = "publicKeyPem")]
    public_key_pem: String,
    #[serde(rename = "privateKeyPem")]
    private_key_pem: String,
    #[serde(rename = "createdAtMs")]
    created_at_ms: u64,
}

fn device_id_from_raw_public_key(raw: &[u8; 32]) -> String {
    let hash = Sha256::digest(raw);
    hex::encode(hash)
}

// We don't depend on the `hex` crate, so inline it.
mod hex {
    pub fn encode(bytes: impl AsRef<[u8]>) -> String {
        bytes
            .as_ref()
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect()
    }
}

fn resolve_identity_path(app_data_dir: &Path) -> PathBuf {
    app_data_dir.join("identity").join("device.json")
}

fn parse_pem_ed25519_private_key(pem: &str) -> Option<SigningKey> {
    use ed25519_dalek::pkcs8::DecodePrivateKey;
    SigningKey::from_pkcs8_pem(pem).ok()
}

fn generate_identity() -> DeviceIdentity {
    let mut seed = [0u8; 32];
    getrandom::getrandom(&mut seed).expect("getrandom failed");
    let signing_key = SigningKey::from_bytes(&seed);
    let verifying_key = signing_key.verifying_key();
    let device_id = device_id_from_raw_public_key(verifying_key.as_bytes());
    DeviceIdentity {
        device_id,
        signing_key,
        verifying_key,
    }
}

fn signing_key_to_pkcs8_pem(key: &SigningKey) -> String {
    use ed25519_dalek::pkcs8::EncodePrivateKey;
    use ed25519_dalek::pkcs8::spki::der::pem::LineEnding;
    key.to_pkcs8_pem(LineEnding::LF)
        .expect("ed25519 pkcs8 pem export")
        .to_string()
}

fn verifying_key_to_spki_pem(key: &VerifyingKey) -> String {
    use ed25519_dalek::pkcs8::EncodePublicKey;
    use ed25519_dalek::pkcs8::spki::der::pem::LineEnding;
    key.to_public_key_pem(LineEnding::LF)
        .expect("ed25519 spki pem export")
}

/// Load or create a device identity, persisted to `<app_data_dir>/identity/device.json`.
pub fn load_or_create_device_identity(app_data_dir: &Path) -> DeviceIdentity {
    let path = resolve_identity_path(app_data_dir);

    if let Ok(raw) = fs::read_to_string(&path) {
        if let Ok(stored) = serde_json::from_str::<StoredIdentity>(&raw) {
            if stored.version == 1 {
                if let Some(signing_key) = parse_pem_ed25519_private_key(&stored.private_key_pem) {
                    let verifying_key = signing_key.verifying_key();
                    let device_id = device_id_from_raw_public_key(verifying_key.as_bytes());
                    log::info!("device identity loaded: {device_id}");
                    return DeviceIdentity {
                        device_id,
                        signing_key,
                        verifying_key,
                    };
                }
            }
        }
    }

    // Generate new identity.
    let identity = generate_identity();
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let stored = StoredIdentity {
        version: 1,
        device_id: identity.device_id.clone(),
        public_key_pem: verifying_key_to_spki_pem(&identity.verifying_key),
        private_key_pem: signing_key_to_pkcs8_pem(&identity.signing_key),
        created_at_ms: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64,
    };
    let json = serde_json::to_string_pretty(&stored).unwrap();
    if let Err(e) = fs::write(&path, format!("{json}\n")) {
        log::warn!("failed to persist device identity: {e}");
    } else {
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o600));
        }
        log::info!("device identity created: {}", identity.device_id);
    }
    identity
}

/// Build the v3 auth payload string for signing.
pub fn build_device_auth_payload_v3(
    device_id: &str,
    client_id: &str,
    client_mode: &str,
    role: &str,
    scopes: &[String],
    signed_at_ms: u64,
    token: Option<&str>,
    nonce: &str,
    platform: &str,
    device_family: Option<&str>,
) -> String {
    let scopes_joined = scopes.join(",");
    let token_str = token.unwrap_or("");
    let platform_normalized = normalize_device_metadata(platform);
    let family_normalized = normalize_device_metadata(device_family.unwrap_or(""));
    [
        "v3",
        device_id,
        client_id,
        client_mode,
        role,
        &scopes_joined,
        &signed_at_ms.to_string(),
        token_str,
        nonce,
        &platform_normalized,
        &family_normalized,
    ]
    .join("|")
}

/// Normalize device metadata: trim, lowercase ASCII (matching TS `normalizeDeviceMetadataForAuth`).
fn normalize_device_metadata(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    trimmed
        .chars()
        .map(|c| {
            if c.is_ascii_uppercase() {
                c.to_ascii_lowercase()
            } else {
                c
            }
        })
        .collect()
}

/// Sign the payload with the device's private key, returning base64url-encoded signature.
pub fn sign_payload(identity: &DeviceIdentity, payload: &str) -> String {
    use ed25519_dalek::Signer;
    let sig = identity.signing_key.sign(payload.as_bytes());
    URL_SAFE_NO_PAD.encode(sig.to_bytes())
}

/// Get the raw public key as base64url (for the `publicKey` field in ConnectParams.device).
pub fn public_key_base64url(identity: &DeviceIdentity) -> String {
    URL_SAFE_NO_PAD.encode(identity.verifying_key.as_bytes())
}
