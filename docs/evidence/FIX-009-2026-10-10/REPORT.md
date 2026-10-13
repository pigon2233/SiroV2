# FIX-009 — 完整發布 manifest 簽署

Status：DONE / VERIFIED（完整簽署的局部修復；沒有 deployment）。2026-10-10，main / c1d2d41 dirty baseline。來源為 T32 與 2026-10-09 review，分類 REQUIRED_FIX / HIGH，IMPLEMENTATION_BUG、BAD_INTERFACE、TEST_GAP；沒有證據改標 REGRESSION。

## 已重現與修復

原 schema1..2 包不相容於 schema8；只改 max_schema=8、沿用舊 version:digest HMAC，真 temporary staging 回 activated。新 expected-rejection 測試修前明確失敗，不只因缺新 API 失敗。[修前 log](tests-before.log)；原兩個 staging/rollback tests 原先 PASS，證明既有 green 沒覆蓋此漏洞。[原基線](original-tests-before.log)。

只改 releases.py：加入 signing_format="siro-release-manifest-v1" 與完整 canonical UTF-8 JSON payload，HMAC-SHA256 綁 format、version、source_sha256、min_schema、max_schema，排除 signature。固定排序／compact separators／ensure_ascii／無末端 newline。Positive schema bounds 嚴格整數且 min<=max；入口重新校驗 model_copy/construct 繞過 validation 的資料。實際 bundle digest 仍比對。

缺 format/null 的 legacy artifact 可 parse，但驗簽拒絕；unknown format/fields 拒絕。不 fallback 舊 HMAC、不自動升級信任或重簽。可信 owner 維護時才可重新檢查 bundle 與完整 schema 後重簽，本卡沒有操作任何既有 artifact/key。repo 沒有 signing CLI；原 CLI parsing 不需改。D39／CONTRACTS 已先寫，測試先 RED 再改 source。

保留 compatibility-first status：不相容回 incompatible_schema，其餘 invalid_manifest；invalid wire parsing 拒絕。原 stage/copy/healthcheck/backup/active/LKG/rollback 全部保持，不把整個發布系統重做。

## 驗收

| 驗證 | 實際結果 | 範圍 |
|---|---|---|
| 新34 cases，exact old production | 19 FAIL /15 PASS | 第一例真 activated 反例；其餘涵新格式，修前未知欄位的15 PASS不代表已驗 strict bounds |
| 新舊 release tests | 36 PASS /0.36s | 獨立固定 bytes/HMAC vector、JSON order、各決策欄位 tamper、legacy/old HMAC、invalid types/range/format/field、model_copy、bundle變更、合法不相容、真 temp staging/SQLite/CLI |
| 拒絕無副作用 | PASS | health/backup/copy/atomic spies零次，active/LKG/tree/DB bytes不變；全部合成 temporary fixtures |
| 全套離線 | 863 PASS /5 real_provider 未選 /3既有warnings，111.19s | 原 voice/session/browser/RI-002 等回歸；不是完整真人產品验收 |
| format/lint/mypy/schema | PASS；222格式檔／212 mypy來源 | 沒有依賴、lock、HTTP/WS/DB schema变动 |
| 精確三檔 temp 回退與重套 | SHA PASS | 單一 production、修改 old fixture、新 test；不是 HEAD reset、live release或 DB restore |
| 保存既有來源 | 226 中只 production與fixture两檔改變 | 其餘 SHA不變；未讀私聊、WAV、keys或重啟8026 |
| Scoped secret scan | 0 最終 finding | 初次1 finding為公開合成 HMAC fixed vector；明確 annotation，保留 initial scan |

測試範圍重疊，不將36與863相加。完整回歸跑完後僅改合成固定 vector 的 scanner annotation，沒有執行語意或 production 變更；格式/lint/type與專項已核對。第二 agent 提供修前設計稽核；修後第二 agent 不可用，故只有 root source/caller review與實跑，不冒稱額外獨立 post-review。[source review](source-review.json)。

## 未解除的 gate

FIX-009 的 unsigned schema 漏洞 gate 已解除；**發布 promotion 仍需 RI-005 的 launcher consume、人工批准、single-writer maintenance 與最新資料保留回退**。原 whole-DB rollback test 只驗原行為，會回復舊資料，不能稱 data-preserving。FIX-007 package identity、untrusted checks 的真 OS 隔離／可信 check allowlist 保留。FIX-002 有用搜尋、FIX-005 語音延遲／人耳與FIX-006理解仍未完成。

既有 bundle digest/copy TOCTOU／symlink語意不在本卡修復或安全認證範圍；不能因 signature PASS 當作任意候選已安全可發布。沒有 launcher、正式服務、device/provider/GPU、人耳或部署驗收；沒有架構重新設計。

## 回退與證據

先保持 promotion disabled，再只對匹配本卡 after SHA 的精確 [repair.patch](repair.patch) 做 reverse check／reverse；保留 manifest/bundle/audit，不回復 live DB。若恢復舊驗簽 binary，仍禁止 promotion，旧漏洞不是兼容 fallback。本次只在 temporary tree reverse/reapply。[rollback](rollback.json)。

[baseline](baseline.json)、[preservation](preservation.json)、[checks](checks.json)、[專項](tests-after.log)、[完整回歸](full-suite.log)、[最終掃描](secret-scan.json)。下一張：FIX-007，沿既有 registry/dispatcher 修完整 approved package identity；不新增自主執行 owner 或 registry。
