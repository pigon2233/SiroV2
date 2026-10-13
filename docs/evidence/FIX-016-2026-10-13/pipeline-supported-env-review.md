# FIX-016 — supported CI sandbox environment review

2026-10-13（Asia/Taipei）。唯讀研究；未修改 production、tests、workflow、runtime profile 或 host policy。沒有啟動 SIRO、讀取私人資料、安裝 host package 或執行下载的 package。公開 package metadata/content 的暫存目錄已移除，讀取 subprocess 全部 joined。

## Confirmed mismatch

`remote-cfgtest-failed.log` 對應 [run 38389536976 / job 115269605525](https://github.com/pigon2233/SiroV2/actions/runs/38389536976/job/115269605525)、head `2324b35`。其中 52 個失敗涉及 skill candidate/activation/worker 的實際隔離接入；另有 102 個 sandbox 測試因環境缺少既有 profile 的工具而 skipped。stderr 與 SQLite numeric 各一項由其他 reviewer 處理，本文件不合併或猜其 root cause。

`src/siro/adapters/isolated_python.py:18` 明確使用 Linux x86_64 native `/usr/bin/python3.14`、`/usr/lib/python3.14`、動態 loader 和六個共享庫（包含 `libseccomp.so.2`）。`skill_worker.py:147` 與 `patch_verification.py:241` 從 OS default path 找 bwrap。uv managed CPython3.14 或 setup-python toolcache 並不提供這套 native mount layout，不能藉新 fallback 讓測試假通過。

## Official supported image

GitHub 已於 2026-09-17 將 Ubuntu26.04 x64/Arm64 標為 GA，可用 explicit `ubuntu-26.04` label。[官方 GA 公告](https://github.com/actions/runner-images/issues/14747)。截至本次研究，`ubuntu-latest` 仍為24.04；切26.04公告目標在11月。[官方 label migration](https://github.com/actions/runner-images/issues/14748)。使用 x64 label，因本 profile 明確限制 x86_64。

官方 Ubuntu2604 image 20260927.149.1 列 system Python3.14.4；安裝腳本從 Ubuntu apt 安裝 system Python。這符合既有 native path 的來源，不需要 PPA、手工複製 uv interpreter 或改 runtime mounts。[官方 image inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2604-Readme.md)、[官方 Python image provisioning](https://github.com/actions/runner-images/blob/main/images/ubuntu/scripts/build/install-python.sh)。新的 hosted job 仍須核對實際 image revision與 native interpreter，不能用文件代替驗收。

## Ubuntu packages and AppArmor

直接讀取 [Ubuntu26.04 main package index](https://archive.ubuntu.com/ubuntu/dists/resolute/main/binary-amd64/Packages.xz) 確認 python3.14／完整 stdlib、bubblewrap0.11.1、libseccomp2 皆在官方 main archive；詳細版本／dependency／package URL 保存於 `pipeline-supported-env-packages.json`。這是 GA base pocket 的 metadata，CI應使用 apt 的 signed index 與正常 security updates，不手工下載 deb 安裝，也不將所查 base version硬鎖成永遠不更新。

AppArmor可對 unprivileged userns 建立額外限制，需要 application-specific profile。[Ubuntu AppArmor contract](https://documentation.ubuntu.com/security/security-features/privilege-restriction/apparmor/#apparmor-unprivileged-user-namespace-restrictions)。實際讀取官方 `apparmor` deb確認它自帶 `/etc/apparmor.d/bwrap-userns-restrict`；不需要 `apparmor-profiles` 額外包。此 profile只讓 `/usr/bin/bwrap` 使用所需 namespaces/capabilities，child透過 stacking禁止 capabilities。上游亦提供同一規則。[官方上游 bwrap profile](https://gitlab.com/apparmor/apparmor/-/blob/master/profiles/apparmor/profiles/extras/bwrap-userns-restrict)。

若 runner實際出現 AppArmor deny，採用該官方已安裝 profile並在 ephemeral job中 reload它；不要關閉整個 AppArmor、降低 `apparmor_restrict_unprivileged_userns` sysctl、讓 bwrap setuid、改成 root跑 tests 或移除 isolation flags。image label不是 userns可用性的保證；真正現有負向測試才是驗收。

## Smallest workflow correction proposal

僅在 `.github/workflows/check.yml`：

```diff
-    runs-on: ubuntu-latest
+    runs-on: ubuntu-26.04
```

在 `scripts/check` 前加入 ephemeral runner prerequisites：

```yaml
- name: Install supported Linux sandbox prerequisites
  run: |
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends python3.14 bubblewrap libseccomp2 apparmor
    /usr/bin/python3.14 -I -S -c 'import ctypes,sys; assert sys.version_info[:2] == (3,14); ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libseccomp.so.2")'
    bwrap --version
```

apt安裝／官方 AppArmor profile的 default loading須由新job核對。若 profile並未載入且實際 deny，最小接續是 `sudo apparmor_parser -r /etc/apparmor.d/bwrap-userns-restrict`，只 reload這一個官方profile並保持其他規則；不是 silent fallback或環境門檻的放寬。

`uv python install 3.12` 可另採既有review允許的 `uv python install` hygiene，讓 `.python-version` 仍選3.14；它不是本次 sandbox缺失的 root cause，也不能取代native apt interpreter。Rust1.97.1、uv0.12.18、兩份lockfiles、NATS2.15.0、全部原 scripts/check gates保持。

## Acceptance and rollback

新 cloud run須在其 exact head證明：native path/架構/共享庫完整；bwrap實際 namespace與sandbox執行成功；既有 host-file/environment/network/fork/exec／seccomp／cleanup負向案例執行並通過；102個環境skip全部消失，僅原5個 opt-in provider測試允許 skipped。不得加 marker排除、改tests條件、mock隔離或production fallback。

先確認兩項獨立 stderr/numeric失敗已完成局部修復，然後讓完整既有 `scripts/check` 跑到schema與secret gate，核對job conclusion。此research不是修改後驗收，cloud supported-env結果為 **NOT_RUN**。若26.04實際宿主環境仍不符合，保留實際失敗與 deny log，再修ephemeral provisioning；不把unsupported環境宣稱安全。

Rollback僅回復 workflow label與新增prerequisite step；production source/data不涉及。舊24.04不足profile的 CI不能因source rollback被宣稱已驗收。
