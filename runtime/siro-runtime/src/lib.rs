use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

pub mod linux;
pub mod rpc;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Decision {
    Allow,
    Deny,
    Ask,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GrantClaims {
    pub grant_id: String,
    pub actor: String,
    pub capability: String,
    pub scope: BTreeMap<String, Vec<String>>,
    pub args_hash: String,
    pub expires_at_unix: u64,
    pub uses_remaining: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GrantToken {
    pub claims_json: Vec<u8>,
    pub signature_hex: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GrantError {
    Forged,
    Invalid,
    Expired,
    Revoked,
    Exhausted,
    CapabilityMismatch,
    ArgumentsChanged,
    ScopeDenied,
    Conflict,
    UnknownOutcome,
}

pub fn hash_arguments(arguments: &serde_json::Value) -> String {
    let bytes = serde_json::to_vec(arguments).expect("JSON value is serializable");
    hex::encode(Sha256::digest(bytes))
}

pub fn issue_grant(claims: &GrantClaims, secret: &[u8]) -> GrantToken {
    let claims_json = serde_json::to_vec(claims).expect("grant claims are serializable");
    let mut mac = HmacSha256::new_from_slice(secret).expect("HMAC accepts any key length");
    mac.update(&claims_json);
    GrantToken {
        claims_json,
        signature_hex: hex::encode(mac.finalize().into_bytes()),
    }
}

pub struct GrantVerifier {
    secret: Vec<u8>,
    revoked: BTreeSet<String>,
    remaining: BTreeMap<String, u32>,
}

impl GrantVerifier {
    pub fn new(secret: Vec<u8>) -> Self {
        Self {
            secret,
            revoked: BTreeSet::new(),
            remaining: BTreeMap::new(),
        }
    }

    pub fn revoke(&mut self, grant_id: &str) {
        self.revoked.insert(grant_id.to_owned());
    }

    pub fn verify(
        &mut self,
        token: &GrantToken,
        capability: &str,
        arguments: &serde_json::Value,
        requested_scope: (&str, &str),
        now_unix: u64,
    ) -> Result<GrantClaims, GrantError> {
        let claims = self.validate(token, capability, arguments, requested_scope, now_unix)?;
        let remaining = self
            .remaining
            .entry(claims.grant_id.clone())
            .or_insert(claims.uses_remaining);
        if *remaining == 0 {
            return Err(GrantError::Exhausted);
        }
        *remaining -= 1;
        Ok(claims)
    }

    pub fn validate(
        &self,
        token: &GrantToken,
        capability: &str,
        arguments: &serde_json::Value,
        requested_scope: (&str, &str),
        now_unix: u64,
    ) -> Result<GrantClaims, GrantError> {
        let signature = hex::decode(&token.signature_hex).map_err(|_| GrantError::Forged)?;
        let mut mac = HmacSha256::new_from_slice(&self.secret).map_err(|_| GrantError::Invalid)?;
        mac.update(&token.claims_json);
        mac.verify_slice(&signature)
            .map_err(|_| GrantError::Forged)?;
        let claims: GrantClaims =
            serde_json::from_slice(&token.claims_json).map_err(|_| GrantError::Invalid)?;
        if self.revoked.contains(&claims.grant_id) {
            return Err(GrantError::Revoked);
        }
        if now_unix >= claims.expires_at_unix {
            return Err(GrantError::Expired);
        }
        if claims.capability != capability {
            return Err(GrantError::CapabilityMismatch);
        }
        if claims.args_hash != hash_arguments(arguments) {
            return Err(GrantError::ArgumentsChanged);
        }
        let scope_allowed = claims
            .scope
            .get(requested_scope.0)
            .is_some_and(|values| values.iter().any(|value| value == requested_scope.1));
        if !scope_allowed {
            return Err(GrantError::ScopeDenied);
        }
        Ok(claims)
    }
}

pub fn policy_decision(capability: &str, allow: &[&str], ask: &[&str]) -> Decision {
    if allow.contains(&capability) {
        Decision::Allow
    } else if ask.contains(&capability) {
        Decision::Ask
    } else {
        Decision::Deny
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn fixture() -> (GrantClaims, serde_json::Value) {
        let arguments = json!({"path": "/tmp/siro-safe/file.txt"});
        let claims = GrantClaims {
            grant_id: "grant-1".into(),
            actor: "owner".into(),
            capability: "filesystem.read".into(),
            scope: BTreeMap::from([("path".into(), vec!["/tmp/siro-safe/file.txt".into()])]),
            args_hash: hash_arguments(&arguments),
            expires_at_unix: 2_000,
            uses_remaining: 1,
        };
        (claims, arguments)
    }

    #[test]
    fn valid_grant_and_policy_decisions() {
        let (claims, arguments) = fixture();
        let token = issue_grant(&claims, b"local-test-secret");
        let mut verifier = GrantVerifier::new(b"local-test-secret".to_vec());
        assert!(
            verifier
                .verify(
                    &token,
                    "filesystem.read",
                    &arguments,
                    ("path", "/tmp/siro-safe/file.txt"),
                    1_000,
                )
                .is_ok()
        );
        assert_eq!(
            verifier.verify(
                &token,
                "filesystem.read",
                &arguments,
                ("path", "/tmp/siro-safe/file.txt"),
                1_001,
            ),
            Err(GrantError::Exhausted)
        );
        assert_eq!(policy_decision("safe", &["safe"], &[]), Decision::Allow);
        assert_eq!(policy_decision("confirm", &[], &["confirm"]), Decision::Ask);
        assert_eq!(policy_decision("unknown", &[], &[]), Decision::Deny);
    }

    #[test]
    fn forged_expired_revoked_and_changed_grants_fail() {
        let (claims, arguments) = fixture();
        let token = issue_grant(&claims, b"local-test-secret");
        let mut verifier = GrantVerifier::new(b"local-test-secret".to_vec());

        let mut forged = token.clone();
        forged.claims_json.push(b' ');
        assert_eq!(
            verifier.verify(
                &forged,
                "filesystem.read",
                &arguments,
                ("path", "/tmp/siro-safe/file.txt"),
                1_000,
            ),
            Err(GrantError::Forged)
        );
        assert_eq!(
            verifier.verify(
                &token,
                "filesystem.read",
                &arguments,
                ("path", "/tmp/siro-safe/file.txt"),
                2_000,
            ),
            Err(GrantError::Expired)
        );
        assert_eq!(
            verifier.verify(
                &token,
                "filesystem.read",
                &json!({"path": "/etc/passwd"}),
                ("path", "/tmp/siro-safe/file.txt"),
                1_000,
            ),
            Err(GrantError::ArgumentsChanged)
        );
        verifier.revoke("grant-1");
        assert_eq!(
            verifier.verify(
                &token,
                "filesystem.read",
                &arguments,
                ("path", "/tmp/siro-safe/file.txt"),
                1_000,
            ),
            Err(GrantError::Revoked)
        );
    }
}
