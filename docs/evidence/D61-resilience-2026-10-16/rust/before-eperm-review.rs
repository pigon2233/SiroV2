use crate::rpc::OsDriver;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::fs;
use std::io::{self, Read, Write};
use std::os::unix::fs::OpenOptionsExt;
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub struct LinuxDriver {
    roots: Vec<PathBuf>,
    output_limit: usize,
    managed: BTreeMap<u32, Child>,
}

impl LinuxDriver {
    pub fn new(roots: Vec<PathBuf>, output_limit: usize) -> io::Result<Self> {
        if roots.is_empty() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "at least one runtime root is required",
            ));
        }
        let roots = roots
            .into_iter()
            .map(fs::canonicalize)
            .collect::<io::Result<Vec<_>>>()?;
        Ok(Self {
            roots,
            output_limit,
            managed: BTreeMap::new(),
        })
    }

    fn existing(&self, raw: &str) -> Result<PathBuf, String> {
        let path = fs::canonicalize(raw).map_err(|error| error.to_string())?;
        self.ensure_scope(path)
    }

    fn destination(&self, raw: &str) -> Result<PathBuf, String> {
        let path = Path::new(raw);
        let parent = path.parent().ok_or("destination has no parent")?;
        let parent = fs::canonicalize(parent).map_err(|error| error.to_string())?;
        let name = path.file_name().ok_or("destination has no file name")?;
        self.ensure_scope(parent.join(name))
    }

    fn ensure_scope(&self, path: PathBuf) -> Result<PathBuf, String> {
        if self.roots.iter().any(|root| path.starts_with(root)) {
            Ok(path)
        } else {
            Err("scope_denied".into())
        }
    }

    fn path(arguments: &Value, name: &str) -> Result<String, String> {
        arguments
            .get(name)
            .and_then(Value::as_str)
            .map(str::to_owned)
            .ok_or_else(|| format!("missing string argument: {name}"))
    }

    fn argv(arguments: &Value) -> Result<Vec<String>, String> {
        let values = arguments
            .get("argv")
            .and_then(Value::as_array)
            .ok_or("missing argv")?;
        let argv = values
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .map(str::to_owned)
                    .ok_or("argv must contain strings")
            })
            .collect::<Result<Vec<_>, _>>()?;
        if argv.is_empty() || argv.iter().any(|value| value.contains('\0')) {
            return Err("invalid_argv".into());
        }
        let executable = Path::new(&argv[0])
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or("");
        if ["sh", "bash", "dash", "zsh", "fish", "pwsh", "powershell"].contains(&executable) {
            return Err("shell_requires_separate_capability".into());
        }
        Ok(argv)
    }

    fn command(&self, arguments: &Value) -> Result<Command, String> {
        let argv = Self::argv(arguments)?;
        let cwd = self.existing(&Self::path(arguments, "cwd")?)?;
        let mut command = Command::new(&argv[0]);
        command
            .args(&argv[1..])
            .current_dir(cwd)
            .stdin(Stdio::null());
        Ok(command)
    }

    fn reap_finished(&mut self) -> BTreeMap<u32, String> {
        let mut finished = Vec::new();
        let mut errors = BTreeMap::new();
        for (&pid, child) in &mut self.managed {
            let retained = child
                .try_wait()
                .map_err(|_| "process_reap_failed".to_owned())
                .and_then(|status| {
                    if status.is_some() {
                        process_group_exists(pid)
                    } else {
                        Ok(true)
                    }
                });
            match retained {
                Ok(false) => finished.push(pid),
                Ok(true) => {}
                Err(error) => {
                    errors.insert(pid, error);
                }
            }
        }
        for pid in finished {
            self.managed.remove(&pid);
        }
        errors
    }

    fn run_process(&self, arguments: &Value) -> Result<Value, String> {
        let mut command = self.command(arguments)?;
        let timeout_ms = arguments
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(3_000)
            .min(120_000);
        // Keep one sentinel byte so a file-size-limited prefix cannot appear complete.
        let file_limit = u64::try_from(self.output_limit)
            .ok()
            .and_then(|limit| limit.checked_add(1))
            .ok_or("invalid_output_limit")?;
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        let stdout_path = std::env::temp_dir().join(format!("siro-out-{nonce}"));
        let stderr_path = std::env::temp_dir().join(format!("siro-err-{nonce}"));
        let stdout = fs::File::create(&stdout_path).map_err(|error| error.to_string())?;
        let stderr = fs::File::create(&stderr_path).map_err(|error| error.to_string())?;
        command.stdout(stdout).stderr(stderr);
        // SAFETY: pre_exec only invokes async-signal-safe libc calls before exec.
        unsafe {
            command.pre_exec(move || {
                let limit = libc::rlimit {
                    rlim_cur: file_limit,
                    rlim_max: file_limit,
                };
                if libc::setrlimit(libc::RLIMIT_FSIZE, &limit) != 0 || libc::setpgid(0, 0) != 0 {
                    return Err(io::Error::last_os_error());
                }
                Ok(())
            });
        }
        let mut child = command.spawn().map_err(|error| error.to_string())?;
        let deadline = Instant::now() + Duration::from_millis(timeout_ms);
        let status = loop {
            if let Some(status) = child.try_wait().map_err(|error| error.to_string())? {
                break status;
            }
            if Instant::now() >= deadline {
                kill_group(child.id());
                let _ = child.wait();
                cleanup(&stdout_path, &stderr_path);
                return Err("timeout".into());
            }
            thread::sleep(Duration::from_millis(5));
        };
        let stdout = read_bounded(&stdout_path, self.output_limit);
        let stderr = read_bounded(&stderr_path, self.output_limit);
        cleanup(&stdout_path, &stderr_path);
        Ok(json!({
            "returncode": status.code(),
            "stdout": stdout?,
            "stderr": stderr?,
        }))
    }
}

fn process_group_exists(pid: u32) -> Result<bool, String> {
    let pid = i32::try_from(pid).map_err(|_| "invalid_pid")?;
    // SAFETY: signal zero only checks existence of this driver's owned process group.
    if unsafe { libc::kill(-pid, 0) } == 0 {
        return Ok(true);
    }
    match io::Error::last_os_error().raw_os_error() {
        Some(libc::ESRCH) => Ok(false),
        Some(libc::EPERM) => Ok(true),
        _ => Err("process_group_check_failed".into()),
    }
}

fn kill_group(pid: u32) {
    if let Ok(pid) = i32::try_from(pid) {
        // SAFETY: negative pid targets only the child-created process group.
        unsafe {
            libc::kill(-pid, libc::SIGKILL);
        }
    }
}

fn read_bounded(path: &Path, limit: usize) -> Result<String, String> {
    let mut bytes = Vec::new();
    fs::File::open(path)
        .map_err(|error| error.to_string())?
        .take(u64::try_from(limit).map_err(|_| "invalid_output_limit")? + 1)
        .read_to_end(&mut bytes)
        .map_err(|error| error.to_string())?;
    if bytes.len() > limit {
        return Err("output_limit".into());
    }
    String::from_utf8(bytes).map_err(|_| "invalid_utf8".into())
}

fn cleanup(stdout: &Path, stderr: &Path) {
    let _ = fs::remove_file(stdout);
    let _ = fs::remove_file(stderr);
}

impl OsDriver for LinuxDriver {
    fn execute(&mut self, capability: &str, arguments: &Value) -> Result<Value, String> {
        let reap_errors = self.reap_finished();
        match capability {
            "filesystem.read" => {
                let path = self.existing(&Self::path(arguments, "path")?)?;
                let file = fs::OpenOptions::new()
                    .read(true)
                    .custom_flags(libc::O_NONBLOCK | libc::O_NOFOLLOW)
                    .open(path)
                    .map_err(|error| error.to_string())?;
                let metadata = file.metadata().map_err(|error| error.to_string())?;
                if !metadata.is_file() {
                    return Err("non_regular_file".into());
                }
                let limit = u64::try_from(self.output_limit).map_err(|_| "invalid_output_limit")?;
                if metadata.len() > limit {
                    return Err("output_limit".into());
                }
                let mut bytes = Vec::new();
                file.take(limit.saturating_add(1))
                    .read_to_end(&mut bytes)
                    .map_err(|error| error.to_string())?;
                if bytes.len() > self.output_limit {
                    return Err("output_limit".into());
                }
                let text = String::from_utf8(bytes).map_err(|_| "invalid_utf8")?;
                Ok(json!({"text": text}))
            }
            "filesystem.list" => {
                let path = self.existing(&Self::path(arguments, "path")?)?;
                let mut names = fs::read_dir(path)
                    .map_err(|error| error.to_string())?
                    .map(|entry| {
                        entry
                            .map_err(|error| error.to_string())?
                            .file_name()
                            .into_string()
                            .map_err(|_| "invalid_utf8".to_owned())
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                names.sort();
                if names.iter().map(String::len).sum::<usize>() > self.output_limit {
                    return Err("output_limit".into());
                }
                Ok(json!({"entries": names}))
            }
            "filesystem.write" => {
                let path = self.destination(&Self::path(arguments, "path")?)?;
                let text = Self::path(arguments, "text")?;
                if text.len() > self.output_limit {
                    return Err("output_limit".into());
                }
                let nonce = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map_err(|error| error.to_string())?
                    .as_nanos();
                let temporary = path.with_extension(format!("siro-{nonce}.tmp"));
                let mut file = fs::File::create(&temporary).map_err(|error| error.to_string())?;
                file.write_all(text.as_bytes())
                    .and_then(|()| file.sync_all())
                    .map_err(|error| error.to_string())?;
                fs::rename(&temporary, &path).map_err(|error| {
                    let _ = fs::remove_file(&temporary);
                    error.to_string()
                })?;
                Ok(json!({"bytes_written": text.len()}))
            }
            "filesystem.move" => {
                let source = self.existing(&Self::path(arguments, "source")?)?;
                let destination = self.destination(&Self::path(arguments, "destination")?)?;
                if destination.exists() {
                    return Err("destination_exists".into());
                }
                fs::rename(source, &destination).map_err(|error| error.to_string())?;
                Ok(json!({"path": destination}))
            }
            "process.run" => self.run_process(arguments),
            "process.start" => {
                let mut command = self.command(arguments)?;
                command.stdout(Stdio::null()).stderr(Stdio::null());
                // SAFETY: pre_exec only invokes setpgid before exec.
                unsafe {
                    command.pre_exec(|| {
                        if libc::setpgid(0, 0) != 0 {
                            return Err(io::Error::last_os_error());
                        }
                        Ok(())
                    });
                }
                let child = command.spawn().map_err(|error| error.to_string())?;
                let pid = child.id();
                self.managed.insert(pid, child);
                Ok(json!({"pid": pid}))
            }
            "process.list" => {
                if let Some(error) = reap_errors.values().next() {
                    return Err(error.clone());
                }
                Ok(json!({"pids": self.managed.keys().copied().collect::<Vec<_>>()}))
            }
            "process.stop" => {
                let pid_u64 = arguments
                    .get("pid")
                    .and_then(Value::as_u64)
                    .ok_or("missing pid")?;
                let pid = u32::try_from(pid_u64).map_err(|_| "invalid_pid")?;
                if let Some(error) = reap_errors.get(&pid) {
                    return Err(error.clone());
                }
                let mut child = self.managed.remove(&pid).ok_or("process_not_owned")?;
                kill_group(pid);
                child.wait().map_err(|error| error.to_string())?;
                Ok(json!({"stopped": pid}))
            }
            _ => Err("unsupported_capability".into()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::CString;
    use std::os::unix::ffi::OsStrExt;

    struct ReadFixture(PathBuf);

    impl ReadFixture {
        fn new() -> Self {
            let nonce = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos();
            let root =
                std::env::temp_dir().join(format!("siro-read-leaf-{}-{nonce}", std::process::id()));
            fs::create_dir(&root).expect("root");
            Self(root)
        }

        fn read(&self, name: &str, limit: usize) -> Result<Value, String> {
            let mut driver = LinuxDriver::new(vec![self.0.clone()], limit).expect("driver");
            driver.execute("filesystem.read", &json!({"path": self.0.join(name)}))
        }
    }

    impl Drop for ReadFixture {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).expect("fixture cleanup");
        }
    }

    fn run_read_probe(test_name: &str, path: &Path) -> std::process::Output {
        let mut command = Command::new(std::env::current_exe().expect("test executable"));
        command
            .args(["--exact", test_name, "--nocapture", "--test-threads=1"])
            .env("SIRO_READ_LEAF_PROBE", path)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        if path.is_dir() {
            command.env("TMPDIR", path);
        }
        // SAFETY: this owned test child invokes only async-signal-safe setrlimit before exec.
        unsafe {
            command.pre_exec(|| {
                let limit = libc::rlimit {
                    rlim_cur: 128 * 1024 * 1024,
                    rlim_max: 128 * 1024 * 1024,
                };
                if libc::setrlimit(libc::RLIMIT_AS, &limit) != 0 {
                    return Err(io::Error::last_os_error());
                }
                Ok(())
            });
        }
        let mut child = command.spawn().expect("owned test child");
        let deadline = Instant::now() + Duration::from_secs(3);
        while child.try_wait().expect("test child status").is_none() {
            if Instant::now() >= deadline {
                child.kill().expect("stop blocked test child");
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        child.wait_with_output().expect("join test child")
    }

    fn probe_path() -> Option<PathBuf> {
        std::env::var_os("SIRO_READ_LEAF_PROBE").map(PathBuf::from)
    }

    fn read_probe(path: &Path) -> Result<Value, String> {
        let root = path.parent().expect("probe root");
        let mut driver = LinuxDriver::new(vec![root.to_path_buf()], 8192).expect("driver");
        driver.execute("filesystem.read", &json!({"path": path}))
    }

    #[test]
    fn filesystem_read_preserves_empty_exact_limit_and_utf8_result_shape() {
        let fixture = ReadFixture::new();
        fs::write(fixture.0.join("empty.txt"), "").expect("empty");
        fs::write(fixture.0.join("text.txt"), "希洛\n").expect("text");
        assert_eq!(fixture.read("empty.txt", 0), Ok(json!({"text": ""})));
        assert_eq!(fixture.read("text.txt", 7), Ok(json!({"text": "希洛\n"})));
    }

    #[test]
    fn filesystem_read_rejects_oversize_without_truncating() {
        let fixture = ReadFixture::new();
        fs::write(fixture.0.join("text.txt"), "123456789").expect("text");
        assert_eq!(fixture.read("text.txt", 8), Err("output_limit".into()));
    }

    #[test]
    fn filesystem_read_rejects_invalid_utf8() {
        let fixture = ReadFixture::new();
        fs::write(fixture.0.join("invalid.txt"), [0xff]).expect("invalid text");
        assert_eq!(
            fixture.read("invalid.txt", 8192),
            Err("invalid_utf8".into())
        );
    }

    #[test]
    fn filesystem_read_rejects_large_sparse_file_before_allocation() {
        if let Some(path) = probe_path() {
            assert_eq!(read_probe(&path), Err("output_limit".into()));
            return;
        }
        let fixture = ReadFixture::new();
        let path = fixture.0.join("sparse.txt");
        fs::File::create(&path)
            .expect("sparse file")
            .set_len(4 * 1024 * 1024 * 1024)
            .expect("sparse length");
        let output = run_read_probe(
            "linux::tests::filesystem_read_rejects_large_sparse_file_before_allocation",
            &path,
        );
        assert!(
            output.status.success(),
            "bounded sparse read failed: {} {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
    }

    #[test]
    fn filesystem_read_rejects_fifo_without_waiting_for_a_writer() {
        if let Some(path) = probe_path() {
            assert_eq!(read_probe(&path), Err("non_regular_file".into()));
            return;
        }
        let fixture = ReadFixture::new();
        let path = fixture.0.join("pipe");
        let encoded = CString::new(path.as_os_str().as_bytes()).expect("FIFO path");
        // SAFETY: encoded is a live NUL-terminated path in this test's owned directory.
        assert_eq!(unsafe { libc::mkfifo(encoded.as_ptr(), 0o600) }, 0);
        let output = run_read_probe(
            "linux::tests::filesystem_read_rejects_fifo_without_waiting_for_a_writer",
            &path,
        );
        assert!(
            output.status.success(),
            "FIFO read blocked or was accepted: {} {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
    }

    #[test]
    fn filesystem_read_rejects_nonregular_directory() {
        let fixture = ReadFixture::new();
        fs::create_dir(fixture.0.join("directory")).expect("directory");
        assert_eq!(
            fixture.read("directory", 8192),
            Err("non_regular_file".into())
        );
    }

    #[test]
    fn filesystem_read_preserves_scope_refusal_and_in_scope_symlink() {
        let fixture = ReadFixture::new();
        let outside = ReadFixture::new();
        fs::write(fixture.0.join("text.txt"), "safe").expect("text");
        fs::write(outside.0.join("secret.txt"), "synthetic canary").expect("canary");
        std::os::unix::fs::symlink(fixture.0.join("text.txt"), fixture.0.join("alias"))
            .expect("in-scope symlink");
        std::os::unix::fs::symlink(&outside.0, fixture.0.join("escape")).expect("outside symlink");
        assert_eq!(fixture.read("alias", 8192), Ok(json!({"text": "safe"})));
        assert_eq!(
            fixture.read("escape/secret.txt", 8192),
            Err("scope_denied".into())
        );
        let mut driver = LinuxDriver::new(vec![fixture.0.clone()], 8192).expect("driver");
        assert_eq!(
            driver.execute(
                "filesystem.read",
                &json!({"path": outside.0.join("secret.txt")})
            ),
            Err("scope_denied".into())
        );
    }

    #[test]
    fn scoped_file_driver_rejects_symlink_escape() {
        let base = std::env::temp_dir().join(format!("siro-linux-{}", std::process::id()));
        let root = base.join("root");
        let outside = base.join("outside");
        fs::create_dir_all(&root).expect("root");
        fs::create_dir_all(&outside).expect("outside");
        fs::write(outside.join("secret"), "private").expect("secret");
        std::os::unix::fs::symlink(&outside, root.join("escape")).expect("symlink");
        let mut driver = LinuxDriver::new(vec![root.clone()], 1024).expect("driver");
        assert_eq!(
            driver.execute(
                "filesystem.read",
                &json!({"path": root.join("escape/secret")})
            ),
            Err("scope_denied".into())
        );
        fs::remove_dir_all(base).expect("cleanup");
    }

    fn wait_for_owned_exit(pid: u32) {
        let status_path = PathBuf::from(format!("/proc/{pid}/status"));
        let deadline = Instant::now() + Duration::from_secs(3);
        loop {
            let status = fs::read_to_string(&status_path).expect("owned child status");
            if status.lines().any(|line| line.starts_with("State:\tZ")) {
                return;
            }
            assert!(Instant::now() < deadline, "owned child did not exit");
            thread::sleep(Duration::from_millis(5));
        }
    }

    fn start_managed(driver: &mut LinuxDriver, root: &Path, source: &str) -> u32 {
        let result = driver
            .execute(
                "process.start",
                &json!({"argv": ["/usr/bin/python3", "-c", source], "cwd": root}),
            )
            .expect("start owned child");
        u32::try_from(result["pid"].as_u64().expect("pid")).expect("u32 pid")
    }

    #[test]
    fn non_process_execution_reaps_exited_managed_children() {
        let fixture = ReadFixture::new();
        let mut driver = LinuxDriver::new(vec![fixture.0.clone()], 128).expect("driver");
        let pid = start_managed(&mut driver, &fixture.0, "pass");
        wait_for_owned_exit(pid);
        assert!(driver.managed.contains_key(&pid));
        let listed = driver.execute("filesystem.list", &json!({"path": fixture.0}));
        let completed_remains = !driver.managed.is_empty();
        let zombie_remains = Path::new(&format!("/proc/{pid}")).exists();
        let stopped = driver.execute("process.stop", &json!({"pid": pid}));
        // Clean even against the old driver before reporting the regression.
        if let Some(mut child) = driver.managed.remove(&pid) {
            child.wait().expect("reap test child");
        }
        assert_eq!(listed, Ok(json!({"entries": []})));
        assert!(!completed_remains, "completed child remains managed");
        assert!(!zombie_remains, "completed owned child remains a zombie");
        assert_eq!(stopped, Err("process_not_owned".into()));
    }

    #[test]
    fn managed_child_reap_failure_is_visible_and_keeps_ownership_record() {
        let fixture = ReadFixture::new();
        let mut driver = LinuxDriver::new(vec![fixture.0.clone()], 128).expect("driver");
        let pid = start_managed(&mut driver, &fixture.0, "pass");
        wait_for_owned_exit(pid);
        let mut status = 0;
        // SAFETY: this test deliberately injects ECHILD by reaping only its own known child.
        assert_eq!(
            unsafe { libc::waitpid(pid as i32, &mut status, 0) },
            pid as i32
        );
        assert_eq!(
            driver.execute("filesystem.list", &json!({"path": fixture.0})),
            Ok(json!({"entries": []}))
        );
        assert_eq!(
            driver.execute("process.list", &json!({})),
            Err("process_reap_failed".into())
        );
        assert_eq!(
            driver.execute("process.stop", &json!({"pid": pid})),
            Err("process_reap_failed".into())
        );
        assert!(driver.managed.contains_key(&pid));
        let healthy = start_managed(&mut driver, &fixture.0, "import time; time.sleep(10)");
        assert_eq!(
            driver.execute("process.stop", &json!({"pid": healthy})),
            Ok(json!({"stopped": healthy}))
        );
        assert!(driver.managed.contains_key(&pid));
    }

    #[test]
    fn reap_preserves_live_child_and_refuses_unowned_stop() {
        let fixture = ReadFixture::new();
        let mut driver = LinuxDriver::new(vec![fixture.0.clone()], 128).expect("driver");
        let pid = start_managed(&mut driver, &fixture.0, "import time; time.sleep(10)");
        let mut unrelated = Command::new("/usr/bin/python3")
            .args(["-c", "import time; time.sleep(10)"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("unrelated owned test child");
        let listed = driver.execute("filesystem.list", &json!({"path": fixture.0}));
        let live_is_managed = driver.managed.contains_key(&pid);
        let unowned_stop = driver.execute("process.stop", &json!({"pid": unrelated.id()}));
        let unrelated_status = unrelated.try_wait().expect("unrelated status");
        let stopped = driver.execute("process.stop", &json!({"pid": pid}));
        unrelated.kill().expect("stop unrelated test child");
        unrelated.wait().expect("reap unrelated test child");
        assert_eq!(listed, Ok(json!({"entries": []})));
        assert!(live_is_managed);
        assert_eq!(unowned_stop, Err("process_not_owned".into()));
        assert!(unrelated_status.is_none());
        assert_eq!(stopped, Ok(json!({"stopped": pid})));
    }

    #[test]
    fn reaped_leader_preserves_owned_descendant_group_stop() {
        if let Some(root) = probe_path() {
            // SAFETY: only this disposable test process adopts its own descendants.
            assert_eq!(
                unsafe { libc::prctl(libc::PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) },
                0
            );
            let mut driver = LinuxDriver::new(vec![root.clone()], 1024).expect("driver");
            let pid = start_managed(
                &mut driver,
                &root,
                "import os, pathlib, time\nchild = os.fork()\nif child == 0:\n time.sleep(10)\nelse:\n pathlib.Path('descendant.pid').write_text(str(child))\n",
            );
            wait_for_owned_exit(pid);
            let descendant: i32 = fs::read_to_string(root.join("descendant.pid"))
                .expect("descendant pid")
                .parse()
                .expect("pid number");
            let listed = driver.execute("process.list", &json!({}));
            let leader_reaped = !Path::new(&format!("/proc/{pid}")).exists();
            let stopped = driver.execute("process.stop", &json!({"pid": pid}));
            // Always clean the known test group, including against the old broken driver.
            kill_group(pid);
            let mut status = 0;
            // SAFETY: this subreaper waits only for its known adopted test child.
            assert_eq!(
                unsafe { libc::waitpid(descendant, &mut status, 0) },
                descendant
            );
            assert!(leader_reaped, "group leader remains a zombie");
            assert_eq!(listed, Ok(json!({"pids": [pid]})));
            assert_eq!(stopped, Ok(json!({"stopped": pid})));
            assert!(!Path::new(&format!("/proc/{descendant}")).exists());
            return;
        }
        let fixture = ReadFixture::new();
        let output = run_read_probe(
            "linux::tests::reaped_leader_preserves_owned_descendant_group_stop",
            &fixture.0,
        );
        assert!(
            output.status.success(),
            "descendant ownership probe failed: {} {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
    }

    fn run_output(root: &Path, limit: usize, source: &str) -> Result<Value, String> {
        let mut driver = LinuxDriver::new(vec![root.to_path_buf()], limit).expect("driver");
        driver.execute(
            "process.run",
            &json!({"argv": ["/usr/bin/python3", "-c", source], "cwd": root, "timeout_ms": 1000}),
        )
    }

    #[test]
    fn process_run_rejects_stdout_over_limit_instead_of_returning_a_prefix() {
        let fixture = ReadFixture::new();
        assert_eq!(
            run_output(&fixture.0, 128, "import os; os.write(1, b'x' * 129)"),
            Err("output_limit".into())
        );
    }

    #[test]
    fn process_run_rejects_stderr_over_limit_instead_of_returning_a_prefix() {
        let fixture = ReadFixture::new();
        assert_eq!(
            run_output(&fixture.0, 128, "import os; os.write(2, b'x' * 129)"),
            Err("output_limit".into())
        );
    }

    #[test]
    fn process_run_output_failure_removes_owned_capture_files() {
        let fixture = ReadFixture::new();
        let result = run_output(
            &fixture.0,
            1024,
            "import json, os, pathlib; pathlib.Path('paths.json').write_text(json.dumps([os.readlink('/proc/self/fd/1'), os.readlink('/proc/self/fd/2')])); os.write(1, b'x' * 1025)",
        );
        let paths: Vec<PathBuf> =
            serde_json::from_slice(&fs::read(fixture.0.join("paths.json")).expect("capture paths"))
                .expect("path JSON");
        assert_eq!(result, Err("output_limit".into()));
        assert_eq!(paths.len(), 2);
        assert!(
            paths.iter().all(|path| !path.exists()),
            "capture files leaked"
        );
    }

    #[test]
    fn process_run_preserves_exact_per_stream_limit_and_result_shape() {
        let fixture = ReadFixture::new();
        assert_eq!(
            run_output(
                &fixture.0,
                128,
                "import os; os.write(1, b'x' * 128); os.write(2, b'y' * 128)"
            ),
            Ok(json!({"returncode": 0, "stdout": "x".repeat(128), "stderr": "y".repeat(128)}))
        );
    }

    #[test]
    fn process_run_zero_limit_accepts_empty_and_rejects_any_output() {
        let fixture = ReadFixture::new();
        assert_eq!(
            run_output(&fixture.0, 0, "pass"),
            Ok(json!({"returncode": 0, "stdout": "", "stderr": ""}))
        );
        assert_eq!(
            run_output(&fixture.0, 0, "import os; os.write(1, b'x')"),
            Err("output_limit".into())
        );
    }

    #[cfg(target_pointer_width = "64")]
    #[test]
    fn invalid_output_limit_does_not_create_capture_files() {
        if let Some(root) = probe_path() {
            assert_eq!(std::env::temp_dir(), root);
            assert_eq!(
                run_output(&root, usize::MAX, "pass"),
                Err("invalid_output_limit".into())
            );
            assert_eq!(fs::read_dir(root).expect("capture directory").count(), 0);
            return;
        }
        let fixture = ReadFixture::new();
        let output = run_read_probe(
            "linux::tests::invalid_output_limit_does_not_create_capture_files",
            &fixture.0,
        );
        assert!(
            output.status.success(),
            "invalid-limit capture probe failed: {} {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
    }

    #[test]
    fn process_run_is_bounded_and_managed_processes_are_owned() {
        let base = std::env::temp_dir().join(format!("siro-process-{}", std::process::id()));
        fs::create_dir_all(&base).expect("root");
        let mut driver = LinuxDriver::new(vec![base.clone()], 1024).expect("driver");
        let result = driver
            .execute(
                "process.run",
                &json!({
                    "argv": ["/usr/bin/python3", "-c", "print('safe')"],
                    "cwd": base,
                    "timeout_ms": 1000
                }),
            )
            .expect("run");
        assert_eq!(result["stdout"], "safe\n");
        assert_eq!(
            driver.execute(
                "process.run",
                &json!({"argv": ["/bin/sh", "-c", "echo unsafe"], "cwd": base})
            ),
            Err("shell_requires_separate_capability".into())
        );
        assert_eq!(
            driver.execute(
                "process.run",
                &json!({
                    "argv": ["/usr/bin/python3", "-c", "import time; time.sleep(2)"],
                    "cwd": base,
                    "timeout_ms": 20
                })
            ),
            Err("timeout".into())
        );
        let started = driver
            .execute(
                "process.start",
                &json!({
                    "argv": ["/usr/bin/python3", "-c", "import time; time.sleep(2)"],
                    "cwd": base
                }),
            )
            .expect("start");
        let pid = started["pid"].as_u64().expect("pid");
        let listed = driver.execute("process.list", &json!({})).expect("list");
        assert!(
            listed["pids"]
                .as_array()
                .expect("pids")
                .contains(&json!(pid))
        );
        assert!(driver.execute("process.stop", &json!({"pid": pid})).is_ok());
        assert_eq!(
            driver.execute("process.stop", &json!({"pid": pid})),
            Err("process_not_owned".into())
        );
        fs::remove_dir_all(base).expect("cleanup");
    }
}
