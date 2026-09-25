# T12 部分實作證據

日期：2026-09-24

狀態：BLOCKED-EXTERNAL（合法 Live2D SDK Core 與模型資產）

## 已完成

- `/ws/body` 使用 T10 的短效 loopback session 與 Origin 檢查。
- `WebSocketBodyTransport` 維持單一 renderer owner、單 writer、有界佇列；重連會取消舊 writer 並丟棄舊 session queue。
- adapter 在 renderer offline 或 queue/transport failure 時立即回傳失敗，不讓 renderer 阻塞 Core。
- `/body` 是可實際連線的 renderer shell，處理 speech/emotion/cancel；畫面明示 placeholder，不冒充 Live2D。
- 真實 Uvicorn + in-app browser 已顯示 `renderer online · placeholder, not Live2D`，server log 記錄 HTTP session 與 WebSocket accepted。
- A07 L1：kill renderer 後 Core 仍完成文字 turn、召回 SQLite source-backed memory；健康 renderer 重連後收到新的 generation。
- asset manifest 強制記錄 source/license/acceptance/checksum，拒絕路徑逃逸與檔案竄改；實體資產目錄已排除 Git。

## 驗證

```text
scripts/check
61 passed, 3 skipped (real providers require explicit opt-in), 1 dependency deprecation warning
```

## 外部阻礙

官方 [Cubism Web Samples license](https://github.com/Live2D/CubismWebSamples/blob/develop/LICENSE.md) 將 Framework/Samples、專有 Cubism Core、sample models 分成不同授權。官方 [SDK manual](https://docs.live2d.com/en/cubism-sdk-manual/cubism-sdk-for-web/) 也說明 Cubism Core 不在 GitHub，必須從官方 SDK distribution 取得。不能從其他 repo 複製 Core 或把 sample model 當成一般 MIT asset。

要完成 L2，owner 需同意適用的 Live2D 條款並從官方來源取得 SDK，並選定一個授權允許本專案測試/展示的模型。取得前不得將 placeholder 或 mock 算作 A07 真 Live2D。
