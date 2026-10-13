use crate::rpc::OsDriver;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::fs;
use std::io::{self, Read, Write};
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

    fn run_process(&self, arguments: &Value) -> Result<Value, String> {
        let mut command = self.command(arguments)?;
        let timeout_ms = arguments
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(3_000)
            .min(120_000);
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        let stdout_path = std::env::temp_dir().join(format!("siro-out-{nonce}"));
        let stderr_path = std::env::temp_dir().join(format!("siro-err-{nonce}"));
        let stdout = fs::File::create(&stdout_path).map_err(|error| error.to_string())?;
        let stderr = fs::File::create(&stderr_path).map_err(|error| error.to_string())?;
        command.stdout(stdout).stderr(stderr);
        let file_limit = u64::try_from(self.output_limit).map_err(|_| "invalid_output_limit")?;
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
        let stdout = read_bounded(&stdout_path, self.output_limit)?;
        let stderr = read_bounded(&stderr_path, self.output_limit)?;
        cleanup(&stdout_path, &stderr_path);
        Ok(json!({
            "returncode": status.code(),
            "stdout": stdout,
            "stderr": stderr,
        }))
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
        match capability {
            "filesystem.read" => {
                let path = self.existing(&Self::path(arguments, "path")?)?;
                let bytes = fs::read(path).map_err(|error| error.to_string())?;
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
                self.managed
                    .retain(|_, child| child.try_wait().ok().flatten().is_none());
                Ok(json!({"pids": self.managed.keys().copied().collect::<Vec<_>>()}))
            }
            "process.stop" => {
                let pid_u64 = arguments
                    .get("pid")
                    .and_then(Value::as_u64)
                    .ok_or("missing pid")?;
                let pid = u32::try_from(pid_u64).map_err(|_| "invalid_pid")?;
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

    #[test]
    fn process_run_is_bounded_and_managed_processes_are_owned() {
        let base = std::env::temp_dir().join(format!("siro-process-{}", std::process::id()));
        fs::create_dir_all(&base).expect("root");
        let mut driver = LinuxDriver::new(vec![base.clone()], 1024).expect("driver");
        let result = driver
            .execute(
                "process.run",
                &json!({
                    "argv": ["/usr/bin/python3.14", "-c", "print('safe')"],
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
                    "argv": ["/usr/bin/python3.14", "-c", "import time; time.sleep(2)"],
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
                    "argv": ["/usr/bin/python3.14", "-c", "import time; time.sleep(2)"],
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
