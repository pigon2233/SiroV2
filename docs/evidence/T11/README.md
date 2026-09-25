# T11 驗收證據

日期：2026-09-24

## 真實第三方稽核

- Repository：`https://github.com/moeru-ai/airi`
- Commit：`595ea7260d95d25a654572cfdd52e96cb9441290`
- License：根目錄 MIT License，Copyright 2024-PRESENT Neko Ayaka。
- 已直接檢查 `server-sdk`、`server-shared`、`plugin-protocol`、Stage speech bus、Stage renderer 與 Live2D expression tools。
- 結論：公開外部 protocol 沒有 speech playback、emotion、cancel renderer commands；四項直接外控無法在不修改 AIRI Stage 的情況下完成。重現命令與檔案位置見 `docs/ADR-embodiment.md`。

## Spike 驗收

```bash
uv run pytest tests/contract/test_body_adapter.py -vv
scripts/check
```

測試覆蓋 speech、emotion、cancel message mapping，以及 renderer offline 時立即失敗且不殘留訊息。完成 T11 時 `scripts/check` 為 57 passed、3 個明示 opt-in 的 real-provider tests skipped。

## 驗收層級

- L1：SIRO body contract 與最小 Web adapter，合成 transport。
- Research：AIRI 真實 source/license/API 稽核與可重現阻礙。
- 尚未完成：真實 Live2D renderer、角色資產、畫面與 kill/reconnect；屬 T12。
