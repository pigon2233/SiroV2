# SIRO Skill 開發指南

T22 contract version 1 只接受本機 Python entrypoint，格式為 `python:module:function`。每個 skill 目錄需要 `manifest.json`、輸入 schema 與輸出 schema；可執行的最小範例在 `samples/skills/echo`。

Registry 以 `(id, version)` 保存 manifest hash、路徑和 enabled/disabled 狀態。新安裝預設 disabled，每個新 job 在啟動 worker 前重新查詢狀態。manifest 的未知欄位、不支援的 contract/network 或不合格版本都會被拒絕。

Worker 每個 job 建立一個獨立 process，在載入 plugin 前套用 Linux `RLIMIT_AS` 與 `RLIMIT_CPU`。Supervisor 另外限制 wall-clock timeout、stdout bytes 和 stderr 回傳；取消會終止 worker。輸入在啟動前驗證，輸出在接受前驗證。

contract version 1 的 schema 是有界 JSON object subset：`properties`、`required`、`additionalProperties` 與基本 `type`。不要使用未實作的 JSON Schema keyword。

Linux resource limits 不是完整 sandbox；目前 worker 只允許受信任、由專案安裝的 skill。`network: denied` 是相容性要求，這個階段不聲稱已對惡意第三方程式達成 kernel-level network/filesystem isolation；未受信任 skill 必須等後續 sandbox backend 再啟用。

執行專案 gate：

```bash
./scripts/check
```
