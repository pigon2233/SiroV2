# Runtime Intelligence 邊界稽核證據

日期：2026-10-09，Asia/Taipei。Repository：`/home/jasonliao/文件/Siro/SiroV2`，branch `main`，HEAD `c1d2d41b2afc8844ff46f328043f7d2e8bf3cabe`，有既有未提交變更；本報告沒有將 HEAD 視為目前 dirty tree 的發布版本。

範圍是本機原始碼、現有測試與完全合成的 temporary fixtures。未讀取私人聊天／真正 DB、未呼叫使用者服務 8026、GPU、外部 provider 或實體設備。沒有修改 production source。

## 已執行的相關回歸

```bash
.venv/bin/python -m pytest -q tests/integration/test_tool_catalog.py tests/integration/test_skill_registry.py tests/integration/test_patch_verifier.py tests/integration/test_release_manager.py tests/integration/test_procedural_candidates.py tests/test_proactivity.py tests/integration/test_device_registry.py tests/integration/test_home_assistant.py tests/integration/test_memory_organization.py tests/integration/test_context_summary.py
```

結果：**exit 0；40 passed；3 warnings；9.49s**。Warnings 為既有 Starlette/httpx 與 pypinyin `codecs.open` deprecation。這包括實際 bubblewrap worker 的網路／host fixture／secret environment 拒絕測試；HA 是測試 fixture，不是真 HA。不能由這 40 PASS 推導自主生成技能或正式自我更新安全。

## 已執行的邊界反例

```bash
.venv/bin/python docs/evidence/RI-architecture-2026-10-09/safety_probe.py > docs/evidence/RI-architecture-2026-10-09/safety-probe.json
```

結果：exit 0。[原始結果](safety-probe.json)、[重現程式](safety_probe.py)。`true` 與 `passed` 在此是「反例已重現」，不是該安全能力通過驗收。

| 檢查 | 合成輸入與實際結果 | 已確認根因 | 適用範圍 |
|---|---|---|---|
| 技能 code identity | 只改 `plugin.py`，`manifest_hash` 不變；同 id/version enabled 的 changed-code object 到達 recording supervisor | `load_skill` 只 hash manifest/input/output schema；Dispatcher 只查 id/version enable | 未執行生成程式；證明 registry 與 code integrity 尚未綁定 |
| protected file deletion | diff 修改 `calc.py` 同時刪 authorization fixture；驗證回 `passed`，reported paths 只含 `calc.py` | `_changed_paths` 只取 `+++ b/`，刪除使用 `+++ /dev/null` | 所有檔案都在 temporary fixture；真正 authorization source 未碰觸 |
| copy 不是 sandbox | 候選 `calc.py` 被 trusted check import 後，寫入 copy 外的 temporary sibling marker；驗證仍 `passed` | `subprocess.run` 繼承相同 user/host 權限；cwd 與 copy 不能限制檔案存取 | marker 與整個 fixture 最後移除；原 fixture source 一致 |
| release schema integrity | 原 manifest schema 1–2 在 current_schema=8 不相容；只改 max_schema=8、signature 不變，activation 回 `activated` | HMAC 覆蓋 `version:digest`，沒有 min/max schema | 只有 temporary synthetic release directory；沒有真部署或 DB |

## 結論與未驗證

現有 suite 驗證了各元件既定正向／部分負向行為，未涵蓋上述供應鏈／安全邊界。因此保留既有元件，但**禁止因本次盤點便把任意產生的 skill/patch 接入 production**。先建立窄修復與失敗測試，再依權限、隔離、人工批准 gate 接入。

未執行：真設備、私人資料、正式 release activation/DB rollback、產生任意 skill、Live2D 視覺人工驗收、語音人耳驗收、24 小時 soak。主代理的完整套件與 Codebase Memory MCP 驗證另列，這份報告不提前宣稱其結果。
