# PERF-01 桌寵少佔 GPU，不改畫質與回應速度

- Task：Windows 桌寵（Electron `desktop-win` + 頁內 VRM iframe）在主人 8GB GPU 幾乎滿的機器上覺得頓。只做不改畫質、幀率上限、回應速度的減負。玻璃模糊可以換成實底。
- Owner／session：Cursor cloud agent，2026-11-13 UTC。
- 狀態：實作完成，待主人在 Windows 上看手感。本檔是交接，不是鎖。
- Base SHA：`e65f2d8026175684a7feb4125832da5d81b1bfcf`（`origin/main`）。開始時本機 `main` 停在 `c40ab48`，已 fast-forward。
- Branch：`cursor/pet-gpu-perf-391c`。實作 commit：`5bd182648967a3dd64557e93c44cc19a89608797`。Worktree：這個 cloud agent checkout。
- 推送：使用者這次明確要求對 `main` 開 PR。這是對 `docs/AI_COLLABORATION.md`「不得 push」的偏離，只針對這個分支與這一個 PR。不合併、不部署。
- 當時開放 PR：#8、#10、#12（桌寵頁／動作，內容已在這次的 `main` 上）、#11（主人的 VRM 模型）。沒有改那些分支，也沒有改電腦操控檔。

## 允許修改

- `desktop-win/main.js`、`desktop-win/click-mask.js`（新）、`desktop-win/click-mask.test.js`（新）
- `desktop-win/gpu-preference.js`（新）、`desktop-win/gpu-preference.test.js`（新）
- `scripts/set-pet-gpu-preference.ps1`（新）、`Start-SIRO-VRM-Win.cmd`（啟動前寫登錄）
- `README.md`
- `src/siro/services/presentation/static/pet.js`、`pet.css`
- `renderers/vrm/src/main.js`（只加幀鉤子與 alpha 遮罩；pixel ratio、MSAA、30／20 fps 判斷沒改）
- `tests/integration/test_desktop_web.py`
- `docs/STATUS.md` 開頭一節、本交接

## 排除

`desktop-win/computer-*`、`input-helper.ps1`、`src/siro/services/computer_use/`、`src/siro/core/computer.py`。Ollama `keep_alive`、TTS 暖機／閒置／裝置沒改。模型仍常駐。沒有改幀率上限或貼圖／描邊。

## 行為

1. **點擊穿透。** 以前每 700ms `capturePage()` 整扇透明視窗，主程序掃每一個像素的 alpha（> 16 算不透明，4px 一格，游標再向外擴一格）。現在角色 iframe 在 `renderer.render` 之後，把已經畫好的畫面縮到 4 CSS 像素一格、每格 2×2 取樣，alpha 仍 > 16 才算命中，用 WebGL2 pixel pack buffer 非同步讀回，大約晚兩個已畫出的影格。閒置（呼吸、坐下循環）2.5 秒一次；走路、拖曳，或一段非循環動作（揮手、坐下過渡）進行時，每兩個已畫出的影格一次。頁面把這張格子貼上圓鈕、更多面板、對話、氣泡、錯誤與狀態字的矩形，經既有的 `siro.desktop` 送到主程序。主程序套用後不再整窗擷取；只有遮罩還沒到，或視窗改了大小卻超過 2.5 秒沒有新遮罩，才退回 `capturePage()`。載入當下仍會擷取一次，讓角色出來之前點得到。
2. **游標。** 命中測試仍每 50ms 在主程序做（`getCursorScreenPoint`，不進頁面）。`executeJavaScript` 的 `pointerUpdate` 改成：進入或離開可點區立刻送；其餘要移動至少 8px，而且最快 100ms 一次。頁面裡的 hover／摸頭仍走原本的 DOM 事件（視窗沒有忽略滑鼠時）。看向桌面游標的 `cursorSeen` 仍收到座標，慢速移動不會因為每步都小於 40px 而被這次改動弄成完全不看。拖曳 `setPosition` 從 8ms 改成 16ms。散步仍是 16ms。
3. **嘴型。** `pet.js` 不再為嘴型另開 60Hz `requestAnimationFrame`。說話時請 renderer 在它真正畫出的影格（桌寵 30fps，站著閒置 20fps）回 `siro.renderer.frame`，頁面用同一份 60Hz 音量包絡取當下樣本。renderer 還沒回幀時，用 30Hz `setTimeout` 補，對齊桌寵幀率上限，不另外排一個 60Hz 合成幀。近重複的樣本仍略過，但最久 150ms 會再送一次，短於 renderer 0.25 秒沒收到就閉嘴的判斷。控制台 `index.html` 的嘴型迴圈沒改。
4. **玻璃。** `pet.css` 裡圓鈕、更多面板、對話的 `backdrop-filter` 移除。圓鈕改 `rgba(16, 14, 24, 0.88)`，懸停 `rgba(62, 48, 84, 0.94)`，更多展開 `rgba(92, 58, 120, 0.94)`。更多面板與對話改 `rgba(16, 14, 24, 0.94)`。頁面背景仍透明。按鈕 id 沒變。
5. **顯卡。** 桌寵預設走內顯，獨立顯卡留給 TTS 與對話模型。`SIRO_PET_GPU` 未設或 `low-power`：Chromium `force_low_power_gpu`（`app.ready` 之前），WebGL `powerPreference: 'low-power'`。`high-performance` 或 `discrete`：不加強制，WebGL 改 `high-performance`。`default`：兩者都不設。不關硬體加速，不改 ANGLE（Windows 仍是 D3D11），pixel ratio／MSAA／幀率上限不變。啟動器在 `electron.exe` 啟動前寫 `HKCU\Software\Microsoft\DirectX\UserGpuPreferences`（值名稱是那支 `electron.exe` 的完整路徑）：預設只在還沒有值時寫 `GpuPreference=1;`，明確的 `low-power` 寫 1，`high-performance`／`discrete` 寫 2，`default` 不寫。Electron 進程裡再套用一次，只影響下一次直接啟動。

## 預期省下的工作（設計估計，不是主人機器上的量測）

以大約 360×800 CSS、devicePixelRatio 1.25 的桌寵視窗粗算。舊路徑約每 0.7 秒從 GPU 讀回整窗（約 450×1000×4 ≈ 1.8MB）並在主程序掃完全部像素，閒置時也一樣，大約 2.6MB/s，而且會讓透明視窗做一次完整合成讀回。新路徑在閒置時約每 2.5 秒讀一張 2× 格子（約 180×400×4 ≈ 288KB，約 0.12MB/s），讀回留在 renderer，主程序不再掃位圖。揮手或走路的那一兩秒會密一些（約每兩個影格一張小圖），但是小圖、非同步，而且只在剪影真的在變時發生。游標注入從移動中最多約 20 次／秒降到最多 10 次／秒。拖曳移動視窗的次數約減半。說話時頁面不再為嘴型排 60Hz 幀。三層 backdrop blur 不再每幀向桌面取樣。

這些數字是從程式路徑推的，不是那張 8GB 卡上的 nvidia-smi 或影格時間。

## 驗收

- `node --test desktop-win/click-mask.test.js desktop-win/gpu-preference.test.js`：11 passed。遮罩測試同上。顯卡測試覆蓋預設內顯、`high-performance`／`discrete`、`default`、不蓋掉已有的登錄值，以及非 Windows 不寫登錄。
- `node --check`：`desktop-win/main.js`、`click-mask.js`、`gpu-preference.js`、`pet.js`、`renderers/vrm/src/main.js` 通過。
- `uv sync --locked --only-group dev --no-install-project --no-default-groups`，然後 `uv run --no-sync pytest tests/integration/test_desktop_web.py tests/integration/test_win_launcher.py`：42 passed。含角色遮罩、嘴型、CSS、pixel ratio 與 30／20 fps，以及 `powerPreference` 只在 `gpu=` 查詢出現時接上。
- `uv run --no-sync ruff check` 與 `ruff format --check` `tests/integration/test_desktop_web.py`：通過。
- 沒有跑完整 `scripts/check`。這環境原本沒有專案 venv；只 `uv sync --locked --only-group dev --no-install-project`。mypy 需要 `pydantic.mypy`，沒有裝專案本體所以沒跑。cargo 在機器上，但沒有改 Rust，沒有重跑。全套 pytest 會進到已知的 skill／profile／computer-use 失敗，這次沒有為了它們重跑。

## 未能在 Windows 上確認

- Electron 透明視窗上，縮小後的 alpha 是否蓋住頭髮與描邊（門檻與一格膨脹與舊版相同，但是 2×2 平均，不是逐像素）。
- 點擊穿透晚大約兩個影格，摸得到角色、點得穿旁邊的桌面。
- 視線與 hover 在節流之後仍像以前。
- 嘴型跟得上聲音。
- 實底圓鈕／面板在主人桌面上看起來是否夠接近原來的磨砂。
- 若 WebGL blit 或 pixel buffer 在那台 Electron 上失敗，主程序會退回每 2.5 秒一次整窗擷取（仍少於原來的 700ms），直到遮罩成功。
- `electron.exe` 是否真的落在 Intel UHD Graphics 770，而不是 RTX 3050。Chromium 的 `force_low_power_gpu` 在混合顯卡上有時不夠，所以啟動器另外寫 Windows 的每程式 GPU 偏好；這台機器還沒跑過。

## 回退

撤掉這個分支即可。點擊穿透回到每 700ms 整窗擷取，游標回到每 4px 注入，拖曳回到 8ms，嘴型回到 60Hz，玻璃模糊回來。若登錄裡已經寫了這支 `electron.exe` 的 `GpuPreference`，撤程式不會自動刪掉那一筆；可在 Windows 顯示設定的圖形選項裡移除，或設 `SIRO_PET_GPU=default` 後自行刪除該值。
