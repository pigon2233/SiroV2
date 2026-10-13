# T36 驗收證據

日期：2026-09-26｜結果：PASS（L1 + loopback L2 simulator）

`NodeRegistry` 驗證預先配對 key、heartbeat TTL、privacy ceiling、未知節點拒絕與撤銷。另加入 atomic
JSON registry、設定範例、location/protocol/capability/hardware profile，以及 version/memory/queue heartbeat。
假 local＋LAN 雙節點經真 loopback transport 驗證；同機 simulator 不取代 T39 真雙節點。
