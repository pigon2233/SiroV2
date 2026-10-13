# FIX-016 — CI toolchain bootstrap review

審查日期：2026-10-13（Asia/Taipei）。唯讀審查；本 reviewer 未修改 production、workflow、toolchain、lockfiles，未 commit 或 push。來源為工作區原檔、實際 GitHub job log，以及官方文件。

## Confirmed failure

[GitHub run 38356354040 / job 115160055433](https://github.com/pigon2233/SiroV2/actions/runs/38356354040/job/115160055433) 對應既有 `d1f5d07` source checkpoint。這次失敗由 push 觸發；不能把它記成已有 PR 的驗收結果。

直接透過 GitHub connector 讀取 decoded job log，確認：

- `2026-10-13T06:22:52.8133448Z Using CPython 3.14.7`。
- Rust `1.97.1-x86_64-unknown-linux-gnu` 自動安裝時，只下載三個 components。
- `2026-10-13T06:23:05.4589994Z error: 'cargo-fmt' is not installed for the toolchain '1.97.1-x86_64-unknown-linux-gnu'.`
- job exit 1；log 提示加入 `rustfmt`。

`scripts/check:30` 在 build/test/clippy 前執行 `cargo fmt --all -- --check`，且有 `set -euo pipefail`。因此本次 job 沒有執行後面的 Rust tests 或 Python regression；不能用本機歷史 PASS 補稱這次 CI PASS。

## Root cause and smallest correction

`rust-toolchain.toml:1` 當時僅包含 `[toolchain]`、`channel = "1.97.1"`、`profile = "minimal"`，沒有 components。官方 rustup Book 說明 minimal 只有 cargo、rustc、rust-std；rustfmt/clippy 屬於額外 components，`components` array 會加入 profile 的集合。[rustup profiles](https://rust-lang.github.io/rustup/concepts/profiles.html)、[toolchain file settings](https://rust-lang.github.io/rustup/overrides.html#components)。

本機 `rustup component list --installed` 已有 cargo、rust-std、rustc、rustfmt、clippy；active toolchain 正是 repo override 的 1.97.1。`docs/DEPENDENCIES.md:37` 也記載 minimal 加 rustfmt/clippy。故本機具備額外工具，遮住了 fresh CI bootstrap 不完整的缺陷。

確認的修復範圍：在既有 `rust-toolchain.toml` 新增一行：

```toml
components = ["rustfmt", "clippy"]
```

保留 Rust `1.97.1`、minimal profile、`Cargo.lock`、workspace dependencies，以及 fmt/build/test/clippy 的全部檢查。無須加第二個 Rust setup action、更新棧、移除 check、改 production 或換成 default/complete profile。

問題分類：`REQUIRED_FIX` / `MEDIUM`，來源 `MISSING_INTEGRATION`、`INCOMPLETE_TASK`、`TEST_GAP`。root cause 已確認為 repository bootstrap declaration 缺少驗收入口所需 components；沒有 runtime architecture drift 證據。

## Python selection — not the failed invariant

`.github/workflows/check.yml:19` 先 `uv python install 3.12`，但 `.python-version:1` 已固定 minor 3.14；`pyproject.toml:10` 與 `uv.lock:3` 允許 `>=3.12,<3.15`。job 隨後選 CPython 3.14.7 是這個 project request 的正常結果，並不是未知 fallback，也不是 Rust failure 的原因。

官方 uv 說明 `.python-version` 決定 default version request；`uv python install` 不指定 target 時會讀該檔。project requirements 只限制可接受範圍，不會覆蓋明確 version request。[uv Python version files and installation](https://docs.astral.sh/uv/concepts/python-versions/#python-version-files)。

可以做最小 workflow hygiene：將預裝行改為 `uv python install`，由同一份既有 pin 選版本。這會移除無用的額外 3.12 download，保持實際執行 minor 3.14；不要為修 Rust bootstrap 將 `.python-version` 改成 3.12、擴 Python matrix、或重鎖依賴。若不做此 hygiene，也不會留下已確認的執行失敗；不得把它當另一個阻擋項。

## Required verification and rollback

本 reviewer 沒有安裝/移除任何 toolchain component，也沒有執行 fresh-home reproduction 或修改後 CI。以下是修復必需的驗收，狀態為待執行：

1. 隔離臨時 `RUSTUP_HOME`，原 minimal manifest 重現缺少 cargo-fmt；不能移除使用者現有 components 製造 RED。
2. 同一 pinned version / minimal profile 加 explicit components 後，確認 rustfmt/clippy 安裝、fmt/build/test/clippy 通過。
3. 原 `scripts/check` 整體完成，保留原 strict lint/type/schema/secret scan；後續檢查若揭露其他缺陷，逐項記錄並局部修復，不跳過門檻。
4. push 修復後核對該 head 的 fresh GitHub run/job 結果；舊 failed run 保留為 before evidence。若有 PR，另外附上其精確 head 的 checks。
5. 比較 `Cargo.lock`、`.python-version`、`uv.lock` 和全部 production source bytes 保持。

Rollback 只回復 toolchain manifest 的新增 components；若採 Python hygiene，另回復 workflow 單行。回退 source 不會解除 CI failure gate。既有工具安裝及 production data 不需要 rollback。

## Review conclusion

已確認的必要修復是 toolchain components declaration。Python 預裝不一致只允許沿用現有 pin 的局部 hygiene；無證據要求改 Python pin 或 production 架構。此 review 支持最小修復方案，不能取代修改後本機或 GitHub 的實際驗收結果。

## Completed probe and final read-only review

Actual isolated empty-tool-home official bootstrap is now PASS; toolchain-probe.json/log confirms original minimal missing fmt/clippy, manifest-only components auto-provision, both version checks success, temporary root removed and original pin/lock bytes retained. This supersedes the earlier pending-probe statements, preserving them as review chronology. Final four-file review found no actionable issue: precise path/blob/line/type/fingerprint/is_verifiedFalse binding, unchanged checks/production/pins/locks. Final helper/test/toolchain/check binding is recorded in preservation-and-rollback.json. Complete pipeline and remote Actions are owned separately by root; this review does not claim them passed.
