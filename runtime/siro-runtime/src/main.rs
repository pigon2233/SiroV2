use siro_runtime::linux::LinuxDriver;
use siro_runtime::rpc::{LocalRpcServer, OsDriver, RuntimeEngine};
use std::env;
use std::io;
use std::path::PathBuf;

fn main() -> io::Result<()> {
    let socket = env::var_os("SIRO_RUNTIME_SOCKET")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/tmp/siro-runtime.sock"));
    let secret = env::var("SIRO_RUNTIME_SECRET").map_err(|_| {
        io::Error::new(
            io::ErrorKind::PermissionDenied,
            "SIRO_RUNTIME_SECRET is required",
        )
    })?;
    let state = env::var_os("SIRO_RUNTIME_DB")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/tmp/siro-runtime-state.sqlite3"));
    let roots = env::var_os("SIRO_RUNTIME_ROOTS")
        .map(|value| env::split_paths(&value).collect::<Vec<_>>())
        .unwrap_or_default();
    let driver: Box<dyn OsDriver> = Box::new(LinuxDriver::new(roots, 1024 * 1024)?);
    let server = LocalRpcServer::bind(socket)?;
    let mut engine = RuntimeEngine::with_state(secret.into_bytes(), driver, state)?;
    loop {
        server.serve_once(&mut engine)?;
    }
}
