# 自己的研究筆記進記憶與對話歷史（NOT PUSHED，等記憶分支合併）

Owner 決定（2026-10-23）：她自己的研究筆記進記憶**自動通過**，不需要 owner 審核或按鈕；owner 的目標是自己做得越少越好。

## 範圍
- 只存短摘要：題目、來源網址與標題，以及她已自動貼出的事實；不存網頁正文（網頁文字是不受信任輸入）。
- 來源事件是她自己的研究 run；記憶標明來源為 `self_research`，可在記憶頁看到並撤銷／刪除。
- 只有已自動分享（`self-notes-shared.json`）的筆記才寫，且需有真實來源。
- 分享進正式對話歷史：另需動 run journal 契約，併入同一卡，先寫 DECISIONS。

## 為何尚未實作
main 沒有候選記憶機制；它在 Codex 未合併的分支（`codex/memory-runtime-integration-20261022`、`codex/memory-mem03-candidates-20261020`），那套預設要 owner 審核。目前 `src/siro/core/memory.py` 也有其他人的未提交修改。
等這些分支合併後，在其上加「`self_research` 來源自動通過」的規則，並補 DECISIONS 與測試。

## 驗收
- 注入測試：筆記含「忽略先前指令」之類文字時，記憶只含題目與網址。
- 撤銷後不再出現在回憶與提示。
- 沒有來源或沒分享的筆記不寫入。
