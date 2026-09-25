# ADR：角色身體採最小 Web renderer

- 狀態：Accepted
- 日期：2026-09-24
- 任務：T11

## 決策

SIRO 採用自己的 `BodyAdapter` 契約與最小 Web renderer。AIRI 保留為參考實作，現階段不作為外部身體程序。Core 只送出 speech、emotion、cancel 等可丟棄的呈現意圖；renderer 不持有 Identity、Memory 或 Conversation 資料庫。

這個決策完成的是接入選型與控制邊界，不代表 Live2D 已完成。T12 必須用授權清楚的真實 Live2D 資產通過動作、故障隔離與重連驗收。

## AIRI 稽核結果

稽核來源為 [moeru-ai/airi](https://github.com/moeru-ai/airi)，鎖定 commit `595ea7260d95d25a654572cfdd52e96cb9441290`。根目錄 `LICENSE` 是 MIT License，Copyright 2024-PRESENT Neko Ayaka。若未來複製或修改 AIRI 程式碼，發行物必須保留其 copyright 與 license notice；本次 spike 沒有複製 AIRI 程式碼。

鎖定版本的 `@proj-airi/server-sdk` 能連到外部 WebSocket server，並支援 extension/module announce。公開 `plugin-protocol` 包含 `input:text`、`input:text:voice`、`input:voice`、生成輸出、Spark 與 context 事件，但沒有直接 speech playback、emotion 或 cancel renderer 命令。

AIRI Stage 內部確實有需要的原語：

- `packages/stage-ui/src/services/speech/bus.ts` 定義 speech start/token/flush/end/cancel，但使用瀏覽器 BroadcastChannel。
- `packages/stage-ui/src/components/scenes/Stage.vue` 透過 Vue store/queue 控制 Live2D motion，並只對 VRM 暴露 `setExpression`。
- `packages/stage-ui-live2d/src/tools/expression-tools.ts` 操作 Stage 內部 expression store。

因此外部程序無法在不修改 AIRI Stage 的情況下可靠完成四項控制。把文字送入 `input:text` 會啟動 AIRI 的聊天流程，不能保證逐字呈現、取消既有 generation 或直接控制表情，也會讓 AIRI 形成第二個對話核心。

## 可重現阻礙

```bash
git clone --filter=blob:none --no-checkout https://github.com/moeru-ai/airi.git
cd airi
git checkout 595ea7260d95d25a654572cfdd52e96cb9441290
git show HEAD:LICENSE | head -20
git show HEAD:packages/plugin-protocol/src/types/events.ts \
  | rg -n 'speech|emotion|cancel|input:text|output:gen-ai|spark:|context:update'
```

結果只有 input/output/Spark/context 等公開協定項目；`speech`、`emotion`、`cancel` 沒有對應的外部 body command。再比對上述三個 Stage 內部檔案即可重現邊界差異。

## 最小 spike

`src/siro/ports/body.py` 定義穩定的 speech、emotion、cancel 與 status 邊界。`MinimalWebBodyAdapter` 把前三項映射成 version 1 renderer message；斷線時立即回傳 `False`，不阻塞 Core，也不累積可能在重連後錯誤播放的過期呈現。contract tests 展示三種操作和 offline 行為。

## 依賴與資產

T11 新增零個 runtime dependency，也不需要角色或聲音資產。T12 需要：

- 授權允許本專案使用與展示的 Live2D Cubism 3/4 模型，並保存來源、作者、授權文字與再散布限制；
- Live2D Web runtime/SDK 的版本與授權稽核；
- renderer-side WebSocket transport、emotion mapping、idle/gesture/look target 與 reconnect；
- 真實畫面證據和 renderer kill/restart 測試。

角色模型與 Live2D SDK 的授權彼此獨立，兩者都必須核實。未取得合法資產前可完成故障隔離和假 renderer contract，但不能宣告 T12 的真 Live2D 驗收通過。

## 後果

此選擇避免把第二套人格、模型和記憶管線帶入 SIRO，也讓 renderer 故障不影響文字 Core。代價是 SIRO 必須維護小型 renderer 與 Live2D runtime 整合。若 AIRI 未來提供有版本、可認證且涵蓋 speech/emotion/cancel/status 的外部 body API，可以在不改 Core 的情況下新增另一個 `BodyAdapter`。
