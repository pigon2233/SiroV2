# T10 WSLg 注音無法輸入修復

日期：2026-10-18。使用者明確回報「注音輸入法根本打不出注音」。先前 T10-IME 的 HTML 組字 Enter 修正只處理已產生 composition event 時的送出競爭，無法替 WSLg 產生注音。這輪使用者指定的 Ubuntu 26.04.1 WSL 原先沒有 IBus／Chewing；WSLg 的 Windows IME 轉送仍未完成，故桌寵 WebKit 輸入框未收到 Windows 注音。參考 [WSLg IME issue](https://github.com/microsoft/wslg/issues/9) 與 [中文輸入案例](https://github.com/microsoft/wslg/issues/955)。

## 修改與安裝

- 在 E 槽 Ubuntu 安裝官方套件 `ibus=1.5.34~rc2-1`、`ibus-chewing=2.1.7-1`、`x11-xkb-utils=7.7+9build1`。最後一項提供 `setxkbmap`；缺少時實際啟動曾回報無法選取注音引擎。版本由 `apt-cache policy`／`dpkg-query -W` 核對，授權由本機 `/usr/share/doc/{ibus,ibus-chewing,x11-xkb-utils}/copyright` 核對，來源見 `docs/DEPENDENCIES.md`。這些是系統套件，沒有修改 Python `uv.lock`。
- `scripts/start-desktop` 在 WSL 確認 IBus 執行檔，沒有 bus 時啟動 daemon，等待 Chewing 引擎可用並選用它，向 GJS/WebKit 傳入 `GTK_IM_MODULE=ibus`、`XMODIFIERS=@im=ibus`；失敗時清楚顯示安裝／服務提示。非 WSL 執行不變。`tests/integration/test_desktop_entry_scripts.py` 加入 bus 已有／尚未有的啟動回歸。
- 使用方法加入 `docs/WSL_SETUP.md`。之前的 Enter composition 修正仍保留。

## 驗收

| 類別 | 命令／實際結果 |
|---|---|
| 系統套件 | `dpkg-query -W ibus ibus-chewing x11-xkb-utils`：三個版本如上；`ibus engine` 為 `chewing`。 |
| 合成 IBus 輸入 | `python3 .siro-data/wsl-setup/probe_chewing.py`：8 個合成鍵全數由引擎處理，觀測到注音／中文字 preedit `北ㄕ`、`北市`，commit `北市`；GLib 探針有非致命 floating-object 警告。此探針不等同真人在 WebKit 打字。 |
| 隔離回歸 | 精確部署快照 `27a4c652b5512748c0bd80e82f62a81037ce3e2a19b6c76b0527188dff24826d` 的 Python 3.12 venv，`pytest -q -p no:cacheprovider tests/integration/test_desktop_entry_scripts.py tests/integration/test_frontend_ime.py`：**42 PASS／7.10s**。Ruff check、format check、`bash -n scripts/start-desktop`：exit 0。 |
| 快照準備 | `refresh_ext4.py`：三方 source identity verified、locked uv sync／compileall／Cargo build exit 0；最終 snapshot/source ID 如上。 |
| 真實 Windows 入口冷啟 | 先以 `ibus exit` 關閉 daemon，確認 `pgrep '^ibus-daemon'` 無結果及 `ibus engine` 無引擎，再從 Windows `Start-SIRO.cmd` 啟動。`check_final_entry.py`：**PASS**，`/health/ready` healthy、唯一 native PID 102270、模型 `ollama:qwen3:4b-instruct`、音訊 `local:faster-whisper-small`、TTS `local:qwen3-tts-0.6b-base:siro-sweet-b-v1`。新 daemon PID 102331；native `/proc/102270/environ` 包含 `GTK_IM_MODULE=ibus`、`XMODIFIERS=@im=ibus`；`ibus engine` 為 `chewing`。服務及桌寵留給使用者運作。 |

初次安裝只含 IBus／Chewing 時，實際 Windows 入口失敗，查得缺 `setxkbmap`；加入 `x11-xkb-utils` 後熱啟通過。第一次冷啟又顯示錯誤的「缺少注音引擎」，查得啟動腳本在 daemon 建立前呼叫 `ibus list-engine`；改為建立 daemon 後輪詢，再做上述真正冷啟驗收。這些失敗均未記為通過。

## 範圍與限制

保留使用者／其他工作已在工作區的變更，未處理私人對話、密鑰、錄音或設備。舊桌寵／後端依精確來源與 PID 確認後正常退出；舊 wrapper／設定／選單備份在 Git 忽略的 `.siro-data/wsl-setup/zhuyin-rollback-20261018/`，資料庫、模型及角色資產維持原處。真實視窗與引擎路徑已通，但仍需使用者以實體鍵盤在 SIRO 輸入框驗收候選字位置與選字手感；沒有把合成按鍵當作真人驗收。未跑完整 `scripts/check`、remote CI，也沒有宣稱 T10 全部完成。
