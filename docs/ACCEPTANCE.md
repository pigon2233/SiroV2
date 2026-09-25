# 驗收、效能與故障演練

本文件是預定驗收規格。已通過的層級與已知缺口以 `docs/STATUS.md` 和各 `docs/evidence/Txx/` 為準；不能由任務標籤推導未實測的 L2/L3 已通過。每個案例的記錄必須包含日期、commit/dirty state、硬體、軟體版本、profile、命令、輸入 fixture、實際結果和證據位置。

## 1. 三層證據

- L1 deterministic：mock provider、fake clock、合成資料，驗證契約與狀態機。
- L2 real integration：真 broker／真模型／真 renderer／真 OS，驗證介面。
- L3 field：真人語音、實體設備、第二台機器及長時間運行，驗證體驗與環境。

L1 通過不能代替 L2/L3；缺 API key/硬體為 blocked-external。每次只跑本次變更涉及的相關檢查，階段 gate 再跑整合套件；不為文件改動重跑所有模型。

## 2. 必要情境

| ID | 操作／故障注入 | 可觀察的通過條件 | 最低證據 |
|---|---|---|---|
| A01 | 輸入文字，接收串流，結束 turn | delta 有序、只一個 terminal event、trace 可跟到完成 | L1+L2 provider |
| A02 | 回答中取消，再注入舊 provider chunk | 新 turn 正常；舊 generation 全數丟棄；不會復活 | L1 100 次 race |
| A03 | 建立身份及共同事件，重啟三次並換 backend | identity_id/核心不變、事件可查、有正確來源 | L1+兩個真 backend |
| A04 | DB commit 後斷 broker、ack 前 kill consumer、做 replay | outbox 可補送、效果不重複、replay 無真實動作 | L2 broker +故障紀錄 |
| A05 | 一個 UI client 停止讀取，其他 client 繼續 | 阻塞限於該 client、有界記憶體、可以取消 | L2 WS load |
| A06 | UI 反覆斷線/重連 100 次 | 無 sender leak、snapshot 一致、不回放舊 speech | L1+L2 |
| A07 | kill Live2D renderer、工具刻意等待 30 秒 | Core 還能回文字、記憶保留、重啟身體恢復 | L2 真 Live2D |
| A08 | 喇叭播放中真人打斷 | 播放停止、buffer 清空、口型停止、可聽新句 | L3 20 次以上 |
| A09 | 拔麥克風、STT timeout、TTS crash | 明示狀態、仍可打字、無反覆播放/無無限重試 | L2+L3 |
| A10 | 20 組指定 facts/episodes，混入相近干擾 | 正確來源 top-5 命中至少 18 組；不把衝突猜成定論 | L1 固定評測集 |
| A11 | 更正/刪除某記憶、切換使用者 scope | 檢索與摘要不再使用已刪內容，其他 scope 不可見 | L1+DB 還原/索引重建 |
| A12 | Dream 中途 kill，恢復後重做同批 | 無重複 facts；trait 不越界；來源不足維持 candidate | L1 30 天合成資料 |
| A13 | quiet/busy/正在說話／cooldown／正常回家場景 | 前四種不擅自社交發話，正常情境可選發話或安靜並附原因 | L1 7 天+L3 回饋 |
| A14 | 偽造、過期、改 args、撤銷 grant | Runtime 全部拒絕且保留審計；不產生副作用 | L1+L2 runtime |
| A15 | skill infinite loop/OOM/output flood/停用 | worker 被限制或拒絕、Core/Audio 不停止、在途狀態明確 | L2 隔離測試 |
| A16 | 路徑逃逸、symlink、長程序取消、重送 write | scope 外無讀寫；子程序清理；動作不重複 | L2 臨時目录 |
| A17 | 執行桌面操作與測試服務啟停，同時播音 | 狀態 readback 確認、UI/語音可取消；unsupported 明示 | L3 每個宣稱 OS |
| A18 | presence bounce、device offline、重複 command、手動改燈 | 不重複問候／toggle，不把 ack 當真狀態；有效 readback | L3 ESP32+HA |
| A19 | 成功 trace 產生技能，再餵惡意／失敗 trace | 候選可測試、未授權不啟用、不能要求自己的額外 grant | L1+隔離 worker |
| A20 | 安裝坏 release、migration 失敗、activate 中斷 | last-known-good 可啟動、資料一致、已完成動作不重演 | L2 隔離部署 |
| A21 | 記憶體壓力、GPU OOM、雲端 budget=0 | L3 暫停、重型模型停止、control 可用、無越界外送 | L1 注入+L2 實測 |
| A22 | 全新資料目錄安裝；備份還原；graceful stop | 操作可重現，身份/記憶/設定復原，in-flight 有明確狀態 | L2 乾淨環境 |
| A23 | privacy/成本/能力不符候選節點、假廣播節點 | hard filter 不被評分繞過；無可用節點明示失敗 | L1+L2 |
| A24 | 真雙節點推論中斷網，舊節點晚回結果 | lease 過期、新 attempt 隔離、不拼接 token、不覆寫記憶 | L3 兩台機器 |

## 3. 效能 SLO 與量測邊界

下列是初始目標。T00 指定 target hardware，T33 校準；未達需修復或以有理由的決策調整，不能偷偷把平均值當 p95。

| 指標 | 計時起點 → 終點 | 目標 |
|---|---|---|
| body reaction | gateway 收到 intent → 下一個可見狀態 frame | p95 ≤100 ms，本機 |
| cancel playback | audio service 接受 cancel → 停止實際輸出 buffer | p95 ≤150 ms，本機 |
| VAD onset | 標記真值語音起點 → speech-start event | p95 ≤200 ms；另報 false-positive |
| deterministic action | 已授權 request 入 runtime → 本機可驗證結果 | p95 ≤300 ms；排除安裝/長 shell |
| cloud TTFT | adapter 發 request → 第一段可見內容 | p95 ≤2 秒為體驗目標，記 provider/network，不能保證 |
| TTS first audio | 完整首句 ready → 第一段開始播放 | p95 ≤1 秒為體驗目標 |
| 本地設備動作 | gateway 送 command → 目標狀態回讀 | p95 ≤500 ms 為 LAN 目標；實體動作較慢則列設備 profile |
| Core event-loop lag | 排定 tick → 實際執行 tick | p95 ≤20 ms、p99 ≤50 ms，背景負載下 |
| 空閒 Core 記憶體 | 穩態 RSS，不含模型／UI／broker | 起始預算 ≤300 MiB，實測後鎖定 |
| 純控制 stack 記憶體 | Core+runtime+gateway+broker，排除模型/UI | 起始預算 ≤700 MiB，實測後鎖定 |

每個 deterministic latency 至少 100 次，provider 成本較高測試至少 30 次；報樣本數、median、p95、p99（樣本不足時標記估計不穩定）、錯誤率及 cold/warm。同一標準 workload、相同版本，先 warmup 5 分鐘。感測資料／VAD 和 rendering 必須记录真值或量測方法；只量 event 發送時間不能當成物理播放停止時間。

跨機延遲優先由 client monotonic clock 量 round-trip；不將不同主機時鐘相減。功能正確性必須零已知失敗（越權、錯重播、資料毀損尤其如此）；外部 provider 隨機失敗需分別記錄，不隱藏為重試成功。

## 4. 舊 Bridge 問題的專用回歸

此組要在 T10 建立，後續 Audio/Runtime 加入時擴充：

1. 同時發 50 text delta/s、20 telemetry/s、20 ms audio frame、每秒 body intent。
2. 啟動一個刻意阻塞 30 秒的工具 worker，一個慢 UI client。
3. 第 2 秒發 cancel，第 3 秒發新的使用者 turn。
4. 第 5 秒關掉 presentation，再重連；第 10 秒關掉工具 worker。
5. 檢查 control queue 有界、single writer invariant、沒有 concurrent write error、Core loop lag 符合 SLO、cancel 生效、新 turn 可完成。

這是針對使用者描述問題的合成 regression，不代表已重現舊 SIRO 真實 bug；如取得舊碼能重現，再補對應 fixture。

## 5. 長時間運行

v1.0：目標主機連續 24 小時；每小時 10 個合成文字 turn、5 個語音 fixture、20 次 sensor 更新；全天至少 20 次人工互動。每 4 小時注入一種可恢復子程序故障。兩次 Dream、一次 backup、一次 restore 到獨立目錄。

v1.1：同樣 workload 加真第二節點，至少一次斷網/恢復；本機狀態 writer 始終唯一。

合格條件：無未處理 crash、無丟失已 ack 的 durable mutation、無重複危險副作用、無舊音復活、所有權限拒絕有效；warmup 後最後一小時與第一個穩態小時比較，常駐控制程序 RSS 增長 ≤10% 或 50 MiB（取較大者），並說明 cache 行為。模型/renderer 的記憶體另列，不能隱藏在排除項目裡。

## 6. 使用者體驗驗收

完成三輪、每輪至少 15 分鐘：一般聊天與共同事件、被打斷後續聊、房間和電腦混合任務。請使用者用 1–5 分評估稱呼/人格一致、回憶可信、語音自然、主動干擾、錯誤說明。平均 ≥4 是初始期望；若未達，列具體失敗例與改進任務，不能透過自評替代使用者感受。

另逐條執行 [EXPERIENCE.md](EXPERIENCE.md) 的 setup、Companion、Memory、Permissions、System walkthrough；v1.1 加 Devices 與 distributed node。依 [SECURITY_PRIVACY.md](SECURITY_PRIVACY.md) 驗證 disclosure record、retention、刪除、kill switches、local-only 網路阻斷、secret/log/evidence 脫敏。人工體驗不能取代這些可觀察控制。

## 7. 發布 checklist

- [ ] 所有宣稱能力有相對應 task 和 A-case 證據。
- [ ] 乾淨安裝、啟動、停止、診斷可重現。
- [ ] 實際 body/audio/model/OS/device 測試完成；未測平台明确排除。
- [ ] 私人資料、token、原始錄音沒有進 Git 或公開 logs。
- [ ] Setup、權限、記憶與 System 流程無需開發者口頭指導即可完成。
- [ ] local-only、kill switches、retention/deletion 與 secret scan 有實際證據。
- [ ] 取消、權限、重送、unknown outcome、backup/restore 通過。
- [ ] SLO 報告列硬體、版本、樣本及冷熱狀態。
- [ ] last-known-good 和 DB 回退演練完成。
- [ ] 長時間運行及使用者體驗驗收完成。
- [ ] v1.1 額外具備 A23/A24、真雙節點證據。
- [ ] 所有延期／研究項目明列，不暗示已實現。

## 8. 證據範本

```text
Task / case:
Commit / dirty diff:
Date / environment / profile:
Command:
Fixture / expected:
Actual / exit code:
Measurement boundary / sample count:
Evidence paths:
Mock vs real:
Known gaps:
Result: PASS | FAIL | BLOCKED-EXTERNAL
```
