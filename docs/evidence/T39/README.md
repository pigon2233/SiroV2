# T39 真實雙節點與失聯演練

狀態：BLOCKED-EXTERNAL

需要一台不同於本機的已配對 Linux 主機、可用 LAN、以及一個可執行 model 或 speech worker。不可用同一台主機的兩個程序代替。

執行前：在兩台主機安裝同版本 lockfile，為 worker 建立唯一 `node_id` 和 paired key；Core 端以
`NodeRegistry.pair` 預先加入其 profile，privacy ceiling 不高於 owner 指定範圍。

演練順序：

1. worker heartbeat 後，用 `ComputeRouter` 送一個有 model profile 的 job。
2. worker 執行中斷 LAN，待 lease 到期後在可用節點建立新 epoch。
3. 恢復舊 worker，刻意送回舊 epoch 結果；`JobLeases.accept_result` 必須拒絕。
4. 重啟 worker、取消一個在途 job，量測 LAN round-trip 和 input bytes。
5. 保存兩台主機版本、node IDs（不可保存 key）、時戳、epoch、結果、取消與 latency。

目前本機只完成 T36–T38 的 L1 registry/lease/router。沒有第二節點、LAN 斷網證據或遠端模型，因此
A24 和 T39 不能宣告完成。
