# CP-O01：程序層網路監測（2026-10-23）

**結果：PARTIAL。** 只在 WSL2 Linux 實測，並以取樣方式歸屬；Windows 原生、macOS 標 unsupported；尚未接進監測頁或工具執行。

## 第一版覆蓋盲區（來源：`monitor.describe_tool`）

| 工具 | 現況 | 看不到 |
| --- | --- | --- |
| `browser.navigate+read` | 請求／最終 URL、轉址 | HTTP status、method、子資源清單 |
| 其他 `browser.*` | 只有最終 URL | 頁面互動觸發的請求 |
| `computer.execute` | unobserved | 子程序自己的所有連線 |
| `codex.ask` | unobserved | 外部 agent 的所有連線 |

adapter log 只是工具自述的網路，**不是**完整封包稽核。

## 能力評估

| 平台 | 方法 | 權限 | 結論 |
| --- | --- | --- | --- |
| Linux／WSL2（實測，非 root） | 讀 `/proc/<pid>/fd` 的 socket inode，對 `/proc/net/{tcp,tcp6,udp,udp6}` | 無 | **sampled**：只看得到取樣當下仍持有的連線 |
| Linux 完整稽核（strace／seccomp／eBPF／netfilter owner） | — | 需 ptrace／root／CAP | 不做，不默默提權 |
| Windows 原生／macOS | 無免權限程序歸屬法（ETW、WFP、NetworkExtension 需系統管理權） | 提權 | **unsupported** |

## 實測（`tests/integration/test_process_network.py`，3 PASS，WSL2 6.18）

- 直接 subprocess 持有的外送連線：歸屬到該 process group（pid、remote、port、tcp），其他 group 不混入。
- 連上就關的短連線：取樣看不到（連線確實發生）。所以標 sampled，不能宣稱完整。
- 無 `/proc` 或非 Linux：`probe_capability` 回 unsupported，測試在不支援平台 skip，不假裝通過。
- Ruff、format、mypy 通過。未跑全套 check；Windows 原生未測。

## 沒做

- 沒接進 `computer.execute` 的取樣迴圈，也沒有新的 coverage 值給監測頁；接線需決定取樣頻率並更新 V05 文案，另開卡。
- 不解密 TLS、不抓全機封包、不改權限。

## 回退

刪除 `adapters/process_network.py` 與其測試，無 schema 或行為變更。
