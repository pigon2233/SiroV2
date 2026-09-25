use crate::{GrantClaims, GrantError, GrantToken, GrantVerifier};
use rusqlite::{Connection, OptionalExtension, params};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::fs;
use std::io::{self, BufRead, BufReader, Read, Write};
use std::os::unix::fs::{FileTypeExt, PermissionsExt};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub const MAX_RPC_BYTES: u64 = 64 * 1024;

#[derive(Debug, Deserialize)]
#[serde(tag = "method", rename_all = "snake_case")]
pub enum RpcRequest {
    Health,
    Revoke {
        grant_id: String,
    },
    Execute {
        action_id: String,
        capability: String,
        arguments: Value,
        scope_key: String,
        scope_value: String,
        grant: GrantToken,
    },
}

#[derive(Debug, Serialize, Deserialize, PartialEq)]
pub struct RpcResponse {
    pub ok: bool,
    pub result: Option<Value>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct AuditRecord {
    pub action_id: String,
    pub decision: String,
    pub reason: String,
}

pub trait OsDriver {
    fn execute(&mut self, capability: &str, arguments: &Value) -> Result<Value, String>;
}

impl<T: OsDriver + ?Sized> OsDriver for Box<T> {
    fn execute(&mut self, capability: &str, arguments: &Value) -> Result<Value, String> {
        (**self).execute(capability, arguments)
    }
}

#[derive(Default)]
pub struct FakeOsDriver {
    pub calls: Vec<(String, Value)>,
}

impl OsDriver for FakeOsDriver {
    fn execute(&mut self, capability: &str, arguments: &Value) -> Result<Value, String> {
        self.calls.push((capability.to_owned(), arguments.clone()));
        Ok(json!({"fake": true, "capability": capability}))
    }
}

pub struct RuntimeEngine<D: OsDriver> {
    verifier: GrantVerifier,
    state: Option<RuntimeState>,
    pub driver: D,
    pub audit: Vec<AuditRecord>,
}

impl<D: OsDriver> RuntimeEngine<D> {
    pub fn new(secret: Vec<u8>, driver: D) -> Self {
        Self {
            verifier: GrantVerifier::new(secret),
            state: None,
            driver,
            audit: Vec::new(),
        }
    }

    pub fn with_state(secret: Vec<u8>, driver: D, path: impl AsRef<Path>) -> io::Result<Self> {
        Ok(Self {
            verifier: GrantVerifier::new(secret),
            state: Some(RuntimeState::open(path)?),
            driver,
            audit: Vec::new(),
        })
    }

    pub fn revoke(&mut self, grant_id: &str) -> io::Result<()> {
        self.verifier.revoke(grant_id);
        if let Some(state) = &self.state {
            state.revoke(grant_id)?;
        }
        Ok(())
    }

    pub fn handle(&mut self, request: RpcRequest) -> RpcResponse {
        match request {
            RpcRequest::Health => RpcResponse {
                ok: true,
                result: Some(json!({"state": "healthy", "protocol_version": 1})),
                error: None,
            },
            RpcRequest::Revoke { grant_id } => match self.revoke(&grant_id) {
                Ok(()) => RpcResponse {
                    ok: true,
                    result: Some(json!({"revoked": grant_id})),
                    error: None,
                },
                Err(_) => RpcResponse {
                    ok: false,
                    result: None,
                    error: Some("state_unavailable".into()),
                },
            },
            RpcRequest::Execute {
                action_id,
                capability,
                arguments,
                scope_key,
                scope_value,
                grant,
            } => {
                let now_unix = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map_or(u64::MAX, |duration| duration.as_secs());
                let verified = if self.state.is_some() {
                    self.verifier.validate(
                        &grant,
                        &capability,
                        &arguments,
                        (&scope_key, &scope_value),
                        now_unix,
                    )
                } else {
                    self.verifier.verify(
                        &grant,
                        &capability,
                        &arguments,
                        (&scope_key, &scope_value),
                        now_unix,
                    )
                };
                if let Err(error) = verified {
                    let reason = grant_error_code(&error).to_owned();
                    if self.record_audit(&action_id, "deny", &reason).is_err() {
                        return audit_unavailable();
                    }
                    return RpcResponse {
                        ok: false,
                        result: None,
                        error: Some(reason),
                    };
                }
                let claims = verified.expect("verified grant");
                if let Some(state) = &self.state {
                    match state.authorize_action(&claims, &action_id, &capability, now_unix) {
                        Ok(Some(result)) => {
                            if self
                                .record_audit(&action_id, "allow", "idempotent_replay")
                                .is_err()
                            {
                                return audit_unavailable();
                            }
                            return RpcResponse {
                                ok: true,
                                result: Some(result),
                                error: None,
                            };
                        }
                        Ok(None) => {}
                        Err(error) => {
                            let reason = grant_error_code(&error).to_owned();
                            if self.record_audit(&action_id, "deny", &reason).is_err() {
                                return audit_unavailable();
                            }
                            return RpcResponse {
                                ok: false,
                                result: None,
                                error: Some(reason),
                            };
                        }
                    }
                }
                match self.driver.execute(&capability, &arguments) {
                    Ok(result) => {
                        if let Some(state) = &self.state
                            && state.complete_action(&action_id, &result).is_err()
                        {
                            if self
                                .record_audit(&action_id, "deny", "unknown_outcome")
                                .is_err()
                            {
                                return audit_unavailable();
                            }
                            return RpcResponse {
                                ok: false,
                                result: None,
                                error: Some("unknown_outcome".into()),
                            };
                        }
                        if self
                            .record_audit(&action_id, "allow", "valid_grant")
                            .is_err()
                        {
                            return audit_unavailable();
                        }
                        RpcResponse {
                            ok: true,
                            result: Some(result),
                            error: None,
                        }
                    }
                    Err(error) => {
                        if self
                            .record_audit(&action_id, "deny", "driver_error")
                            .is_err()
                        {
                            return audit_unavailable();
                        }
                        RpcResponse {
                            ok: false,
                            result: None,
                            error: Some(error),
                        }
                    }
                }
            }
        }
    }

    fn record_audit(&mut self, action_id: &str, decision: &str, reason: &str) -> io::Result<()> {
        self.audit.push(AuditRecord {
            action_id: action_id.to_owned(),
            decision: decision.to_owned(),
            reason: reason.to_owned(),
        });
        if let Some(state) = &self.state {
            state.audit(action_id, decision, reason)?;
        }
        Ok(())
    }
}

pub struct RuntimeState {
    path: PathBuf,
}

impl RuntimeState {
    fn open(path: impl AsRef<Path>) -> io::Result<Self> {
        let path = path.as_ref().to_owned();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let state = Self { path };
        state
            .connect()?
            .execute_batch(
                "PRAGMA journal_mode=WAL;
                 CREATE TABLE IF NOT EXISTS runtime_grants(
                   grant_id TEXT PRIMARY KEY, capability TEXT NOT NULL, args_hash TEXT NOT NULL,
                   expires_at INTEGER NOT NULL, uses_remaining INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
                 );
                 CREATE TABLE IF NOT EXISTS runtime_audit(
                   audit_id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT NOT NULL,
                   decision TEXT NOT NULL, reason TEXT NOT NULL, timestamp INTEGER NOT NULL
                 );
                 CREATE TABLE IF NOT EXISTS runtime_revocations(
                   grant_id TEXT PRIMARY KEY, revoked_at INTEGER NOT NULL
                 );
                 CREATE TABLE IF NOT EXISTS runtime_actions(
                   action_id TEXT PRIMARY KEY, capability TEXT NOT NULL, args_hash TEXT NOT NULL, state TEXT NOT NULL,
                   result_json TEXT
                 );",
            )
            .map_err(io::Error::other)?;
        Ok(state)
    }

    fn connect(&self) -> io::Result<Connection> {
        Connection::open(&self.path).map_err(io::Error::other)
    }

    fn authorize_action(
        &self,
        claims: &GrantClaims,
        action_id: &str,
        requested_capability: &str,
        now_unix: u64,
    ) -> Result<Option<Value>, GrantError> {
        let mut connection = self.connect().map_err(|_| GrantError::Invalid)?;
        let transaction = connection.transaction().map_err(|_| GrantError::Invalid)?;
        let revoked = transaction
            .query_row(
                "SELECT 1 FROM runtime_revocations WHERE grant_id=?1",
                [&claims.grant_id],
                |_| Ok(()),
            )
            .optional()
            .map_err(|_| GrantError::Invalid)?
            .is_some();
        if revoked {
            return Err(GrantError::Revoked);
        }
        let action: Option<(String, String, String, Option<String>)> = transaction
            .query_row(
                "SELECT capability,args_hash,state,result_json FROM runtime_actions WHERE action_id=?1",
                [action_id],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .optional()
            .map_err(|_| GrantError::Invalid)?;
        if let Some((capability, args_hash, state, result_json)) = action {
            if capability != requested_capability || args_hash != claims.args_hash {
                return Err(GrantError::Conflict);
            }
            if capability == "process.start" {
                return Err(GrantError::UnknownOutcome);
            }
            if state != "succeeded" {
                return Err(GrantError::UnknownOutcome);
            }
            let result = serde_json::from_str(&result_json.ok_or(GrantError::UnknownOutcome)?)
                .map_err(|_| GrantError::Invalid)?;
            return Ok(Some(result));
        }
        let existing: Option<(String, String, i64, u32, bool)> = transaction
            .query_row(
                "SELECT capability,args_hash,expires_at,uses_remaining,revoked FROM runtime_grants WHERE grant_id=?1",
                [&claims.grant_id],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?, row.get(4)?)),
            )
            .optional()
            .map_err(|_| GrantError::Invalid)?;
        if let Some((capability, args_hash, expires_at, remaining, revoked)) = existing {
            let expires_at = u64::try_from(expires_at).map_err(|_| GrantError::Invalid)?;
            if capability != claims.capability
                || args_hash != claims.args_hash
                || expires_at != claims.expires_at_unix
            {
                return Err(GrantError::Invalid);
            }
            if revoked {
                return Err(GrantError::Revoked);
            }
            if now_unix >= expires_at {
                return Err(GrantError::Expired);
            }
            if remaining == 0 {
                return Err(GrantError::Exhausted);
            }
        } else {
            let expires_at =
                i64::try_from(claims.expires_at_unix).map_err(|_| GrantError::Invalid)?;
            transaction
                .execute(
                    "INSERT INTO runtime_grants(grant_id,capability,args_hash,expires_at,uses_remaining,revoked) VALUES (?1,?2,?3,?4,?5,0)",
                    params![claims.grant_id, claims.capability, claims.args_hash, expires_at, claims.uses_remaining],
                )
                .map_err(|_| GrantError::Invalid)?;
        }
        let changed = transaction
            .execute(
                "UPDATE runtime_grants SET uses_remaining=uses_remaining-1 WHERE grant_id=?1 AND uses_remaining>0 AND revoked=0",
                [&claims.grant_id],
            )
            .map_err(|_| GrantError::Invalid)?;
        if changed != 1 {
            return Err(GrantError::Exhausted);
        }
        transaction
            .execute(
                "INSERT INTO runtime_actions(action_id,capability,args_hash,state) VALUES (?1,?2,?3,'running')",
                params![action_id, requested_capability, claims.args_hash],
            )
            .map_err(|_| GrantError::Invalid)?;
        transaction.commit().map_err(|_| GrantError::Invalid)?;
        Ok(None)
    }

    fn complete_action(&self, action_id: &str, result: &Value) -> io::Result<()> {
        let encoded = serde_json::to_string(result).map_err(io::Error::other)?;
        let changed = self
            .connect()?
            .execute(
                "UPDATE runtime_actions SET state='succeeded',result_json=?2 WHERE action_id=?1 AND state='running'",
                params![action_id, encoded],
            )
            .map_err(io::Error::other)?;
        if changed != 1 {
            return Err(io::Error::other("action state conflict"));
        }
        Ok(())
    }

    fn revoke(&self, grant_id: &str) -> io::Result<()> {
        let connection = self.connect()?;
        connection
            .execute(
                "INSERT OR IGNORE INTO runtime_revocations(grant_id,revoked_at) VALUES (?1,strftime('%s','now'))",
                [grant_id],
            )
            .map_err(io::Error::other)?;
        connection
            .execute(
                "UPDATE runtime_grants SET revoked=1 WHERE grant_id=?1",
                [grant_id],
            )
            .map_err(io::Error::other)?;
        Ok(())
    }

    fn audit(&self, action_id: &str, decision: &str, reason: &str) -> io::Result<()> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |duration| duration.as_secs()) as i64;
        self.connect()?
            .execute(
                "INSERT INTO runtime_audit(action_id,decision,reason,timestamp) VALUES (?1,?2,?3,?4)",
                params![action_id, decision, reason, now],
            )
            .map_err(io::Error::other)?;
        Ok(())
    }
}

fn grant_error_code(error: &GrantError) -> &'static str {
    match error {
        GrantError::Forged => "forged_grant",
        GrantError::Invalid => "invalid_grant",
        GrantError::Expired => "expired_grant",
        GrantError::Revoked => "revoked_grant",
        GrantError::Exhausted => "exhausted_grant",
        GrantError::CapabilityMismatch => "capability_mismatch",
        GrantError::ArgumentsChanged => "arguments_changed",
        GrantError::ScopeDenied => "scope_denied",
        GrantError::Conflict => "action_conflict",
        GrantError::UnknownOutcome => "unknown_outcome",
    }
}

fn audit_unavailable() -> RpcResponse {
    RpcResponse {
        ok: false,
        result: None,
        error: Some("audit_unavailable".into()),
    }
}

pub struct LocalRpcServer {
    path: PathBuf,
    listener: UnixListener,
}

impl LocalRpcServer {
    pub fn bind(path: impl AsRef<Path>) -> io::Result<Self> {
        let path = path.as_ref();
        if let Ok(metadata) = fs::symlink_metadata(path) {
            if !metadata.file_type().is_socket() {
                return Err(io::Error::new(
                    io::ErrorKind::AlreadyExists,
                    "runtime socket path is occupied by a non-socket",
                ));
            }
            fs::remove_file(path)?;
        }
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let listener = UnixListener::bind(path)?;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;
        Ok(Self {
            path: path.to_owned(),
            listener,
        })
    }

    pub fn serve_once<D: OsDriver>(&self, engine: &mut RuntimeEngine<D>) -> io::Result<()> {
        let (stream, _) = self.listener.accept()?;
        handle_stream(stream, engine)
    }
}

impl Drop for LocalRpcServer {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

fn handle_stream<D: OsDriver>(
    mut stream: UnixStream,
    engine: &mut RuntimeEngine<D>,
) -> io::Result<()> {
    let reader_stream = stream.try_clone()?;
    let mut line = String::new();
    BufReader::new(reader_stream)
        .take(MAX_RPC_BYTES + 1)
        .read_line(&mut line)?;
    let response = if line.len() as u64 > MAX_RPC_BYTES {
        RpcResponse {
            ok: false,
            result: None,
            error: Some("request_too_large".into()),
        }
    } else {
        match serde_json::from_str::<RpcRequest>(&line) {
            Ok(request) => engine.handle(request),
            Err(_) => RpcResponse {
                ok: false,
                result: None,
                error: Some("invalid_request".into()),
            },
        }
    };
    serde_json::to_writer(&mut stream, &response)?;
    stream.write_all(b"\n")?;
    stream.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{GrantClaims, hash_arguments, issue_grant};
    use std::collections::BTreeMap;
    use std::io::{BufRead, BufReader};
    use std::os::unix::fs::PermissionsExt;
    use std::thread;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn socket_path() -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!("siro-runtime-{}-{nonce}.sock", std::process::id()))
    }

    #[test]
    fn local_socket_health_is_bounded_and_owner_only() {
        let path = socket_path();
        let server = LocalRpcServer::bind(&path).expect("bind");
        let mode = fs::metadata(&path).expect("metadata").permissions().mode() & 0o777;
        assert_eq!(mode, 0o600);
        let mut engine = RuntimeEngine::new(b"secret".to_vec(), FakeOsDriver::default());
        thread::scope(|scope| {
            scope.spawn(|| server.serve_once(&mut engine).expect("serve"));
            let mut stream = UnixStream::connect(&path).expect("connect");
            stream
                .write_all(b"{\"method\":\"health\"}\n")
                .expect("write");
            let mut response = String::new();
            BufReader::new(stream)
                .read_line(&mut response)
                .expect("read");
            let parsed: RpcResponse = serde_json::from_str(&response).expect("response");
            assert!(parsed.ok);
            assert_eq!(parsed.result.expect("result")["protocol_version"], 1);
        });
    }

    #[test]
    fn a14_executes_once_and_audits_denials() {
        let arguments = json!({"path": "/tmp/safe"});
        let claims = GrantClaims {
            grant_id: "one-use".into(),
            actor: "owner".into(),
            capability: "filesystem.read".into(),
            scope: BTreeMap::from([("path".into(), vec!["/tmp/safe".into()])]),
            args_hash: hash_arguments(&arguments),
            expires_at_unix: 4_000_000_000,
            uses_remaining: 1,
        };
        let grant = issue_grant(&claims, b"secret");
        let mut engine = RuntimeEngine::new(b"secret".to_vec(), FakeOsDriver::default());
        let request = |action_id: &str, args: Value| RpcRequest::Execute {
            action_id: action_id.into(),
            capability: "filesystem.read".into(),
            arguments: args,
            scope_key: "path".into(),
            scope_value: "/tmp/safe".into(),
            grant: grant.clone(),
        };
        assert!(engine.handle(request("a1", arguments.clone())).ok);
        let replay = engine.handle(request("a2", arguments));
        assert_eq!(replay.error.as_deref(), Some("exhausted_grant"));
        assert_eq!(engine.driver.calls.len(), 1);
        assert_eq!(engine.audit[0].decision, "allow");
        assert_eq!(engine.audit[1].reason, "exhausted_grant");
    }
}
