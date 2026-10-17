# 新版 Windows／WSL 執行驗證

日期：2026-10-17，Asia/Taipei。起始 HEAD `dc7382e429684c8ae6d3fe844be109cbf2d27a66`，起始工作區乾淨。範圍為新機執行檢查／T34 相關驗證，不宣稱整張 T34、完整桌寵或正式發布完成。

## 結論

**PARTIAL：離線後端與真 Chromium 控制頁可執行；完整 Companion／桌寵 BLOCKED-EXTERNAL。**

使用者確認目前也沒有 Live2D 模型／SDK與原本模型連線設定。專案內 `models/`、`.env.local` 與 pinned tokenizer 目錄不存在；沒有下載角色／模型或擅自選用雲端憑證。WSL 缺 GJS／GTK3／WebKitGTK 桌面依賴。正式入口真實拒絕缺設定，不能將離線固定回覆當成模型成功。

## 環境與本次修復

- Ubuntu26.04.1／WSL2；Python3.12.14、uv0.12.18、Cargo1.97.1、Node22.22.1；GPU查詢RTX3050／8192MiB。
- `uv pip check --python /home/pepepig/.local/share/siro/venv-py312/bin/python`：99套件相容，exit0。
- Linux環境與編譯cache在 E 槽的 Ubuntu虛擬磁碟；source仍在Windows掛載目錄。
- 新版覆蓋先前Git換行規則，`scripts/start`等重新變成CRLF；實際失敗 `env: bash\\r: No such file or directory`。補回 `.gitattributes` 的 `scripts/* text eol=lf`，只正規化scripts換行，未改啟動／模型／DB邏輯。正規化後 `git diff --exit-code -- scripts` exit0，`git diff --check` exit0。
- 本機ignored `.siro-data/wsl-setup/run.sh` 維持 `UV_PYTHON=3.12`、外置venv／cache，並加 `SIRO_RUNTIME_BINARY=$CARGO_TARGET_DIR/debug/siro-runtime`，使用現有launcher override，避免外置Cargo產物和repo預設路徑不一致。未改正式launcher或release契約。

## 實跑命令與結果

在Windows專案目錄，命令前綴為：

```powershell
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh <command>
```

此helper是本機檔案；重建時需明確設定Linux PATH、UV_PYTHON=3.12、UV_PROJECT_ENVIRONMENT、CARGO_TARGET_DIR、SIRO_RUNTIME_BINARY與Linux cache。

### Python／合成整合

首輪命令：

```text
pytest -q tests/integration/test_operational_cli.py tests/integration/test_desktop_host.py tests/integration/test_desktop_web.py tests/contract/test_rate_limit_recovery.py tests/integration/test_rate_limit_recovery_main.py tests/integration/test_speech_plan.py
```

**62 PASS／2 FAIL／19.53s／exit1**，啟停兩失敗均受CRLF影響。

換行修正後，同上加 `tests/integration/test_companion_launcher.py tests/integration/test_signed_companion_launcher.py`：**73 PASS／1 FAIL／25.14s／exit1**。一個既有Starlette/httpx deprecation warning。桌面交接、限流與語音計畫是合成測試，不是真角色／真provider／原聲線驗收。

失敗為原 `test_t34_start_stop_health_and_pid_cleanup` 的5秒readiness gate。獨立重驗operational＋兩launcher檔：**14 PASS／1 FAIL／14.00s／exit1**。直接呼叫原函式只將被丟棄stdout/stderr改為捕捉，仍5.402s失敗、捕捉輸出空；診斷helper捕獲exception後exit0不代表測試PASS。依runbook停止同症狀重測，不放寬原門檻；詳見 [blocker](blocker.md)。

### Rust／真 Linux runtime

```text
cargo build --workspace --locked
cargo test --workspace --locked
```

build exit0／28.90s；test編譯2.14s，**24 PASS／0 FAIL／0 SKIP／0.45s**，main／doc tests均0項。依原Cargo.lock下載既有依賴；未更動Cargo.lock。

### 真 HTTP／真 Chromium，離線合成資料

本機 `verify_20261017.py` 使用自有temporary data／random loopback port／`scripts/start --demo`，進行session認證、只保留安全runtime route欄位，以真Chromium載入頁面並送出一則合成文字：

- `/health/ready` 200，這次4.084s，僅此單樣本低於5秒，不能用它洗掉上面的測試失敗。Probe計時前曾跑launcher缺模型檢查並共用Python cache，不列為冷啟動量測。
- runtime model route `offline`；頁面標題 `SIRO · 對話`、輸入可用、JS page errors0。
- browser收到預期離線合成回覆；不是LLM／真provider成功。
- `/desktop` 503，符合沒有已準備renderer的實際狀態。
- stop exit0、wrapper143、PID file刪除。探測未捕捉到 `Application shutdown complete`，不宣稱該log證明graceful；事後 `ss`／`ps` 確認沒有測試gateway／uv／start程序或listener殘留。
- 原始安全結果：[runtime.json](runtime.json)。stdout log為空：[demo-server.log](demo-server.log)。

同一腳本先真實執行正式入口並記錄：

- `bash scripts/start-runtime-product`：exit1，清楚顯示「尚未設定對話模型」，無靜默demo。
- `bash scripts/start-desktop`：exit2，清楚顯示缺GJS／GTK3／WebKitGTK4.1。

第一個證據helper在Git HEAD查詢遇Windows／WSL ownership差異，Git查詢exit128、helper於服務啟動前exit1；改成僅該命令 `git -c safe.directory=<exact project> rev-parse HEAD` 後續驗，未更動全域safe.directory。

## 還不能執行的部分

1. 對話模型及provider連線設定不存在；未呼叫外部provider、未產生付費請求。
2. Cubism SDK、Live2D模型／貼圖／renderer／授權manifest不存在；未下載或假造授權接受紀錄。
3. GJS／GTK3／WebKitGTK桌寵依賴未裝；WSLg透明視窗／compositor／native輸入／WebKit sandbox未實測。
4. `start-desktop`與`install-desktop`仍固定`.venv/bin/python`；目前該目錄是前輪未完成的3.14環境。真正接桌寵前需沿既有uv環境統一，不能把外置3.12的PASS外推此入口。
5. 原聲線／TTS模型與參考音訊未接，真人聽驗／收音／播放未跑；本機可見GPU不代表Torch／聲音可用。
6. 原5秒啟動測試仍失敗，根因UNKNOWN，未以掛載效能或SQLite鎖的假設定案。

未跑完整scripts/check／全部Python／remoteCI／24小時／設備／正式發布；未修改私人資料、權限、DB schema或provider政策。下一步先選定並準備合法模型／角色素材與provider設定，再以本機環境接正式產品；啟動gate依blocker另做有量測邊界的定位。
