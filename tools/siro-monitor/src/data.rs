//! Read-only collection of progress data. Never writes anything.

use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use regex::Regex;
use serde::Deserialize;

const TPE_OFFSET: i64 = 8 * 3600;

#[derive(Clone, Deserialize)]
#[serde(default)]
pub struct Config {
    /// Windows path of the WSL home folder, e.g. \\wsl.localhost\Ubuntu\home\<user>
    pub wsl_home: String,
    /// Paths below are relative to wsl_home (or absolute Windows paths).
    pub train_run: String,
    pub corpus_dir: String,
    pub prep_progress: String,
}

impl Default for Config {
    fn default() -> Self {
        let user = std::env::var("USERNAME").unwrap_or_else(|_| "user".into());
        Self {
            wsl_home: format!(r"\\wsl.localhost\Ubuntu\home\{user}"),
            train_run: "tts-train/runs/mix-v2".into(),
            corpus_dir: ".local/share/siro/tts-corpus/siro-sweet-b-v2".into(),
            prep_progress: "tts-train/data/prep_progress.json".into(),
        }
    }
}

impl Config {
    /// siro-monitor.toml next to the exe, then in the working directory; else defaults.
    pub fn load() -> Self {
        let mut places = Vec::new();
        if let Ok(exe) = std::env::current_exe() {
            if let Some(dir) = exe.parent() {
                places.push(dir.join("siro-monitor.toml"));
            }
        }
        places.push(PathBuf::from("siro-monitor.toml"));
        places
            .iter()
            .find_map(|p| fs::read_to_string(p).ok())
            .and_then(|text| toml::from_str(&text).ok())
            .unwrap_or_default()
    }

    fn path(&self, rel: &str) -> PathBuf {
        let p = Path::new(rel);
        if p.is_absolute() || rel.starts_with(r"\\") {
            return p.to_path_buf();
        }
        let mut out = PathBuf::from(&self.wsl_home);
        for part in rel.split('/') {
            out.push(part);
        }
        out
    }
}

#[derive(Clone, Default)]
pub struct Snapshot {
    pub updated: String,
    pub prep: Section,
    pub corpus: Section,
    pub train: TrainSection,
}

#[derive(Clone, Default)]
pub struct Section {
    pub state: String,
    pub fraction: Option<f32>,
    pub rows: Vec<(String, String)>,
    pub last_error: Option<String>,
}

#[derive(Clone, Default)]
pub struct TrainSection {
    pub state: String,
    pub fraction: Option<f32>,
    pub rows: Vec<(String, String)>,
    /// [step, mel, kl, dur, gen, disc]
    pub loss: Vec<[f64; 6]>,
    pub samples: Vec<SampleGroup>,
}

#[derive(Clone)]
pub struct SampleGroup {
    pub step: u64,
    pub items: Vec<SampleItem>,
}

#[derive(Clone)]
pub struct SampleItem {
    pub text: String,
    pub path: String,
}

pub fn collect(cfg: &Config) -> Snapshot {
    let gpu = gpu_line();
    let mut train = collect_train(cfg);
    let mut corpus = collect_corpus(cfg);
    let mut prep = collect_prep(cfg);
    for rows in [&mut train.rows, &mut corpus.rows, &mut prep.rows] {
        rows.push(("顯卡".into(), gpu.clone()));
    }
    Snapshot { updated: fmt_time(now_secs(), "%H:%M:%S"), prep, corpus, train }
}

// ---------------------------------------------------------------- time helpers
fn now_secs() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0)
}

fn mtime(p: &Path) -> Option<i64> {
    fs::metadata(p).ok()?.modified().ok()?.duration_since(UNIX_EPOCH).ok().map(|d| d.as_secs() as i64)
}

/// Days since 1970-01-01 for a civil date (Howard Hinnant's algorithm).
fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * (m + if m > 2 { -3 } else { 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (yoe + era * 400 + i64::from(m <= 2), m, d)
}

/// Taipei wall-clock "YYYY-MM-DD HH:MM:SS" (or with a +08:00 / T) -> unix seconds.
fn parse_tpe(text: &str) -> Option<i64> {
    let re = Regex::new(r"(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d):(\d\d)").ok()?;
    let c = re.captures(text)?;
    let n = |i: usize| c[i].parse::<i64>().ok();
    let days = days_from_civil(n(1)?, n(2)?, n(3)?);
    Some(days * 86_400 + n(4)? * 3600 + n(5)? * 60 + n(6)? - TPE_OFFSET)
}

/// Format unix seconds in Taipei time. Supports "%m/%d %H:%M" and "%H:%M:%S".
fn fmt_time(secs: i64, pattern: &str) -> String {
    let local = secs + TPE_OFFSET;
    let (_, mo, d) = civil_from_days(local.div_euclid(86_400));
    let s = local.rem_euclid(86_400);
    let (h, mi, se) = (s / 3600, s % 3600 / 60, s % 60);
    pattern
        .replace("%m", &format!("{mo:02}"))
        .replace("%d", &format!("{d:02}"))
        .replace("%H", &format!("{h:02}"))
        .replace("%M", &format!("{mi:02}"))
        .replace("%S", &format!("{se:02}"))
}

pub fn thousands(n: u64) -> String {
    let s = n.to_string();
    let mut out = String::new();
    for (i, ch) in s.chars().enumerate() {
        if i > 0 && (s.len() - i) % 3 == 0 {
            out.push(',');
        }
        out.push(ch);
    }
    out
}

fn eta_row(left_secs: f64) -> (String, String) {
    let when = now_secs() + left_secs as i64;
    (
        "預計完成".into(),
        format!("{}（台北，約 {:.1} 小時後）", fmt_time(when, "%m/%d %H:%M"), left_secs / 3600.0),
    )
}

fn tail(p: &Path, bytes: u64) -> String {
    use std::io::{Read, Seek, SeekFrom};
    let Ok(mut f) = fs::File::open(p) else { return String::new() };
    let len = f.metadata().map(|m| m.len()).unwrap_or(0);
    let _ = f.seek(SeekFrom::Start(len.saturating_sub(bytes)));
    let mut buf = Vec::new();
    let _ = f.read_to_end(&mut buf);
    String::from_utf8_lossy(&buf).into_owned()
}

// ------------------------------------------------------------------- GPU
fn gpu_line() -> String {
    let mut cmd = std::process::Command::new("nvidia-smi");
    cmd.args(["--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"]);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: no console flash every 5 s
    }
    match cmd.output() {
        Ok(out) => {
            let text = String::from_utf8_lossy(&out.stdout);
            let v: Vec<u64> = text.trim().split(", ").filter_map(|x| x.trim().parse().ok()).collect();
            if v.len() >= 3 {
                format!("{} / {} MiB，使用率 {}%", thousands(v[0]), thousands(v[1]), v[2])
            } else {
                "讀不到".into()
            }
        }
        Err(_) => "讀不到（找不到 nvidia-smi）".into(),
    }
}

// ------------------------------------------------------------------ training
fn collect_train(cfg: &Config) -> TrainSection {
    let run = cfg.path(&cfg.train_run);
    let mut t = TrainSection::default();
    let log_path = run.join("train.log");
    let Ok(text) = fs::read_to_string(&log_path) else {
        t.state = if run.exists() { "準備開始".into() } else { "還沒有訓練".into() };
        t.rows.push(("資料夾".into(), run.display().to_string()));
        return t;
    };
    let re = Regex::new(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)[^\t]*\t[^\t]*\tINFO\t\[([^\]]+)\]\s*$").unwrap();
    let mut rows: Vec<(i64, [f64; 6])> = Vec::new(); // (time, [step, mel, kl, dur, gen, disc])
    for line in text.lines() {
        let Some(c) = re.captures(line) else { continue };
        let vals: Vec<f64> = c[2].split(',').filter_map(|x| x.trim().parse().ok()).collect();
        if vals.len() < 8 {
            continue;
        }
        let step = vals[6];
        while rows.last().is_some_and(|r| r.1[0] >= step) {
            rows.pop(); // resume restarts at an epoch boundary: drop re-trained points
        }
        let time = parse_tpe(&c[1]).unwrap_or(0);
        rows.push((time, [step, vals[3], vals[5], vals[4], vals[1], vals[0]]));
    }
    let console = tail(&run.join("console.log"), 40_000);
    let per_epoch: Option<u64> = Regex::new(r"\d+/(\d+) \[")
        .unwrap()
        .captures_iter(&console)
        .last()
        .and_then(|c| c[1].parse().ok());
    let epochs: Option<u64> = fs::read_to_string(run.join("train_config.json"))
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v["train"]["epochs"].as_u64());
    let total = match (epochs, per_epoch) {
        (Some(e), Some(p)) => Some(e * p),
        _ => None,
    };
    let last_console = console.trim_end().lines().last().unwrap_or("").to_string();
    let age = now_secs() - mtime(&log_path).unwrap_or(0);
    t.state = if last_console.starts_with("=== exit 0") {
        "已完成".into()
    } else if run.join("STOP").exists() {
        "已暫停".into()
    } else if age < 600 {
        "訓練中".into()
    } else {
        "沒有在跑（10 分鐘沒有新紀錄）".into()
    };
    if let Some((_, last)) = rows.last() {
        let step = last[0] as u64;
        match total {
            Some(total) => {
                t.fraction = Some(step as f32 / total as f32);
                t.rows.push(("步數".into(), format!("{} / {}（{:.1}%）", thousands(step), thousands(total), 100.0 * step as f64 / total as f64)));
            }
            None => t.rows.push(("步數".into(), thousands(step))),
        }
        t.rows.push((
            "loss".into(),
            format!("mel {:.2}　kl {:.2}　dur {:.2}　gen {:.2}　disc {:.2}", last[1], last[2], last[3], last[4], last[5]),
        ));
        let recent = &rows[rows.len().saturating_sub(8)..];
        if recent.len() >= 2 {
            let (t0, s0) = (recent[0].0, recent[0].1[0]);
            let (t1, s1) = (recent[recent.len() - 1].0, recent[recent.len() - 1].1[0]);
            if s1 > s0 && t1 > t0 {
                let sec = (t1 - t0) as f64 / (s1 - s0);
                t.rows.push(("速度".into(), format!("約 {sec:.2} 秒／步")));
                if let (Some(total), "訓練中") = (total, t.state.as_str()) {
                    t.rows.push(eta_row(total.saturating_sub(step) as f64 * sec));
                }
            }
        }
    }
    if let Some((step, path)) = newest_checkpoint(&run) {
        let when = mtime(&path).map(|s| fmt_time(s, "%m/%d %H:%M")).unwrap_or_default();
        t.rows.push(("最新存檔".into(), format!("G_{step}.pth（{when}）")));
    }
    t.loss = rows.into_iter().map(|r| r.1).collect();
    t.samples = samples(&run);
    t
}

fn newest_checkpoint(run: &Path) -> Option<(u64, PathBuf)> {
    fs::read_dir(run)
        .ok()?
        .filter_map(|e| e.ok())
        .filter_map(|e| {
            let name = e.file_name().to_string_lossy().into_owned();
            let step = name.strip_prefix("G_")?.strip_suffix(".pth")?.parse::<u64>().ok()?;
            Some((step, e.path()))
        })
        .max_by_key(|(s, _)| *s)
}

fn samples(run: &Path) -> Vec<SampleGroup> {
    let Ok(dir) = fs::read_dir(run.join("samples")) else { return Vec::new() };
    let mut groups: Vec<SampleGroup> = dir
        .filter_map(|e| e.ok())
        .filter_map(|e| {
            let name = e.file_name().to_string_lossy().into_owned();
            let step = name.strip_prefix("G_")?.parse::<u64>().ok()?;
            let path = e.path();
            let texts: Vec<String> = fs::read_to_string(path.join("sentences.txt"))
                .map(|s| s.lines().map(str::to_string).collect())
                .unwrap_or_default();
            let items: Vec<SampleItem> = (1..=3)
                .map(|i| SampleItem {
                    text: texts.get(i - 1).cloned().unwrap_or_else(|| format!("第 {i} 句")),
                    path: path.join(format!("{i}.wav")).display().to_string(),
                })
                .collect();
            items.iter().all(|it| Path::new(&it.path).exists()).then_some(SampleGroup { step, items })
        })
        .collect();
    groups.sort_by(|a, b| b.step.cmp(&a.step));
    groups
}

// ------------------------------------------------------------------- corpus
fn collect_corpus(cfg: &Config) -> Section {
    let dir = cfg.path(&cfg.corpus_dir);
    let mut c = Section::default();
    let plan: Option<serde_json::Value> =
        fs::read_to_string(dir.join("plan.json")).ok().and_then(|s| serde_json::from_str(&s).ok());
    let Some(plan) = plan else {
        c.state = "沒有語料製作".into();
        c.rows.push(("資料夾".into(), dir.display().to_string()));
        return c;
    };
    let total_sent = plan["total_sentences"].as_u64().unwrap_or(0);
    let k = plan["candidates_per_sentence"].as_u64().unwrap_or(0);
    let total_cand = plan["total_candidates"].as_u64().unwrap_or(total_sent * k);
    let mut gen_times = Vec::new();
    let (mut scored, mut passed) = (0u64, 0u64);
    if let Ok(text) = fs::read_to_string(dir.join("progress.jsonl")) {
        for line in text.lines() {
            let Ok(v) = serde_json::from_str::<serde_json::Value>(line) else { continue };
            if v.get("areas").is_some() {
                scored += 1;
                passed += u64::from(v["passed"].as_bool().unwrap_or(false));
            } else if let Some(t) = v["time"].as_str().and_then(parse_tpe) {
                gen_times.push(t);
            }
        }
    }
    let generated = gen_times.len() as u64;
    let run_log = tail(&dir.join("run.log"), 4000);
    let done_line = run_log.lines().rev().find(|l| l.starts_with("=== "));
    c.state = match done_line {
        Some(l) if l.starts_with("=== done") => "已完成".into(),
        Some(l) if l.contains("failed") => format!("失敗：{l}"),
        _ if generated >= total_cand && total_cand > 0 => "打分中".into(),
        _ if gen_times.last().is_some_and(|t| now_secs() - t < 300) => "生成中".into(),
        _ => "沒有在跑".into(),
    };
    if total_cand > 0 {
        c.fraction = Some(generated as f32 / total_cand as f32);
    }
    c.rows.push(("要生成的句數".into(), thousands(total_sent)));
    c.rows.push(("候選".into(), format!("已生成 {} / {}", thousands(generated), thousands(total_cand))));
    if scored > 0 {
        c.rows.push((
            "已打分".into(),
            format!("{}，通過 {}，淘汰 {}", thousands(scored), thousands(passed), thousands(scored - passed)),
        ));
    }
    let recent = &gen_times[gen_times.len().saturating_sub(50)..];
    if recent.len() >= 2 && recent[recent.len() - 1] > recent[0] {
        let per = (recent[recent.len() - 1] - recent[0]) as f64 / (recent.len() - 1) as f64;
        c.rows.push(("速度".into(), format!("約 {per:.1} 秒／候選")));
        if c.state == "生成中" {
            c.rows.push(eta_row(total_cand.saturating_sub(generated) as f64 * per));
        }
    }
    c
}

// --------------------------------------------------------------------- prep
#[derive(Deserialize, Default)]
#[serde(default)]
struct PrepProgress {
    stage: String,
    done: u64,
    total: u64,
    errors: u64,
    last_error: Option<String>,
    started: String,
    updated: String,
    finished: bool,
    failed: Option<String>,
}

fn collect_prep(cfg: &Config) -> Section {
    let path = cfg.path(&cfg.prep_progress);
    let mut s = Section::default();
    let Some(p) = fs::read_to_string(&path).ok().and_then(|t| serde_json::from_str::<PrepProgress>(&t).ok())
    else {
        s.state = "沒有資料準備紀錄".into();
        s.rows.push(("進度檔".into(), path.display().to_string()));
        return s;
    };
    let updated = parse_tpe(&p.updated).unwrap_or(0);
    s.state = if let Some(f) = &p.failed {
        format!("失敗：{f}")
    } else if p.finished {
        "已完成".into()
    } else if now_secs() - updated > 300 {
        "停住了（5 分鐘沒有更新）".into()
    } else {
        "進行中".into()
    };
    if p.total > 0 {
        s.fraction = Some(p.done as f32 / p.total as f32);
    }
    s.rows.push(("目前步驟".into(), p.stage.clone()));
    s.rows.push(("已處理".into(), format!("{} / {}", thousands(p.done), thousands(p.total))));
    s.rows.push(("錯誤數".into(), thousands(p.errors)));
    if let Some(start) = parse_tpe(&p.started) {
        let elapsed = updated - start;
        if p.done > 0 && elapsed > 0 {
            let per = elapsed as f64 / p.done as f64;
            s.rows.push(("速度".into(), format!("約 {:.1} 句／秒", 1.0 / per)));
            if s.state == "進行中" {
                s.rows.push(eta_row(p.total.saturating_sub(p.done) as f64 * per));
            }
        }
        s.rows.push(("開始".into(), fmt_time(start, "%m/%d %H:%M")));
    }
    s.last_error = p.last_error;
    s
}
