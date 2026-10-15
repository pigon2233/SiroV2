# RT-013-FIX-01 — bounded filesystem.read leaf

Date: 2026-10-14. Contract: D57. This is the Rust prerequisite for the first owner-approved document task; it does not establish that the product goal loop is complete.

## Problem and smallest repair

The original Linux driver used `fs::read` before checking `output_limit`. A regular oversized file could allocate its full length first; a FIFO could block waiting for a writer. The Python workspace pre-stat and bounded RPC response do not make that Rust operation bounded before allocation.

Only `runtime/siro-runtime/src/linux.rs` changes. The read branch retains the existing canonical-root checks, opens with `O_NONBLOCK | O_NOFOLLOW`, checks the opened FD's metadata for a regular file and accepted length, then reads at most `output_limit + 1` bytes and rejects excess or invalid UTF-8. The `{text: ...}` result, configured output limit and scope refusal remain unchanged. Valid symlinks that resolve inside the root retain the old behavior. Other capabilities, the subprocess-output helper, dependencies, locks and toolchain stay byte-identical.

## Actual verification

The seven new unit cases cover empty/zero-limit and exact-limit UTF-8 results, oversize refusal without truncation, invalid UTF-8, a 4 GiB sparse file, a FIFO without a writer, a directory, and outside/in-root symlink scope compatibility. The original two Linux test functions and their assertions remain byte-identical; the original six workspace tests remain enabled.

Before the production repair, `cargo test --workspace --locked filesystem_read -- --nocapture` returned EXIT 101: **4 PASS / 3 FAIL**, 4.363 seconds including compilation. The sparse-file child had an owned 128 MiB address-space limit and returned `out of memory` instead of `output_limit`; no 4 GiB allocation was permitted in the parent. The FIFO child remained blocked until the test's 3-second deadline, then was killed and joined. Directory refusal returned the old OS error. These are deliberate RED results, not successful cancellation/product demonstrations. See `red-tests.log` and `red-result.json`.

After repair, the same seven cases passed: **7 PASS / 0 FAIL**, 0.773 seconds including compilation (test body 0.01 seconds). Both dedicated owned child probes completed and were joined. See `green-tests.log` and `green-result.json`.

Final checks all returned EXIT 0:

- `cargo fmt --all -- --check`: 0.097 seconds.
- `cargo build --workspace --locked`: 0.305 seconds.
- `cargo test --workspace --locked`: **13 PASS / 0 FAIL / 0 ignored**, 0.192 seconds (test body 0.04 seconds).
- `cargo clippy --workspace --all-targets --locked -- -D warnings`: 0.578 seconds.

These are real Rust/Linux file and child-process tests using owned synthetic temporary data. No provider, private data, live Gateway, model, device, deployment or whole product acceptance was exercised here. The checks and source identity are recorded in `checks-result.json`; source/old-test/lock preservation and zero remaining `siro-read-leaf-*` fixture directories are recorded in `preservation-rollback.json`.

## Source identity and rollback

Original whole-file SHA256: `4970bb5c83119542fb72e9bf2fd8f0a972f03c30ed8eba27faffcc17ea122539`.

Final whole-file SHA256: `336d34244c4adf3f2252dc7283f9540018de689a10de3f0b38220da878609520`.

`repair.patch` contains the single-file change and tests. `production-repair.patch` contains only the import/read-branch repair. In an owned disposable source copy, the latter reversed exactly to the original production prefix while preserving all final tests, then reapplied to the exact final whole-file hash. The disposable copy was removed and the working source was unchanged. No production rollback was performed and no test rerun is claimed for this disposable reverse/reapply check.

Operational rollback first withdraws the new goal caller and drains its owned work. Preserve the existing read authorization and additive task data; do not expose the old unbounded read as an approved autonomous fallback. This receipt covers source rollback only, not a runtime deployment or data rollback.

## Limits

- The unchanged `filesystem.list` still collects names before its result-size check. The D57 task does not use listing or recursion.
- `O_NOFOLLOW` constrains the final opened component after the existing canonicalization; this patch does not solve malicious parent-directory replacement or all path TOCTOU races.
- `O_NONBLOCK` avoids FIFO-open waiting; it is not a latency guarantee for every regular-file filesystem or a universal IO cancellation mechanism.
- The streaming cap limits bytes even if the opened regular file grows after metadata validation. No deterministic growth-race test or concurrent hostile mutation guarantee is claimed.
- Full owner `computer.execute` remains unchanged and is not an autonomous sandbox.

## Official API references

The standard library documents [Unix OpenOptionsExt::custom_flags](https://doc.rust-lang.org/std/os/unix/fs/trait.OpenOptionsExt.html#tymethod.custom_flags), [metadata on an open File](https://doc.rust-lang.org/std/fs/struct.File.html#method.metadata), and [Read::take's byte limit](https://doc.rust-lang.org/std/io/trait.Read.html#method.take). These stable APIs were compiled and tested with the repository's unchanged pinned Rust 1.97.1.
