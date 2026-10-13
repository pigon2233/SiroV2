# T38 驗收證據

日期：2026-09-26｜結果：PASS（L1 + loopback A23 L2 simulator）

修正 local-only 可能選到 LAN 的缺陷；location hard filter 現在先於成本，並加入 latency estimate、
cost+latency selection、EMA calibration 與 decision trace。假 local/LAN 節點證明 local-only 不離機、
trusted-LAN 可選較便宜 LAN、budget 不被繞過。T39 才量真實遠端硬體。
