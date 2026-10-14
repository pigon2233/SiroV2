# FIX-020 independent final source review

2026-10-14（Asia/Taipei）。Independent reviewer只讀production/tests；按root要求新增此JSON與報告，不commit、不修改其他檔案。沒有私人資料、live8026、模型/GPU或formal deployment操作。

## Result and binding

在以下起訖相同bytes，**沒有找到新的confirmed scoped blocker**：

| File | Before / after SHA256 |
|---|---|
| `src/siro/core/releases.py` | `c959036b436e817d96db14a971b430c02b2b8c096dee00586e3cdf98de36003e` |
| `tests/integration/test_release_tree_identity.py` | `386ade71c60ce2b80cca3de444a8311d807a6ab4e3d7ebb331e79896e8703c72` |

這是FIX-020 identity修復的source review與22個實際scoped cases，不是完整repo、loader／runtime handoff或產品發布驗收。若production bytes改變，須重新綁定此結論。

## Findings

v2先加入固定domain與8-byte file count，再逐檔編碼UTF8 POSIX relative path byte length／path、content length／exact content。這個framing能唯一解碼file boundaries，確實修掉已量測的v1相同串／不同檔案內容問題；不是靠更換hash名稱或凍結錯誤identity。Path.parts順序與空檔／資源／Unicode都已有本卡案例。

`_verified`只接受明確v2 tag，其他format在hashing前拒絕。原canonical HMAC payload包含format欄位，故v2算法與完整version/schema/digest決策共同綁定；v1 tag、None／absent、unknown copied tag或換用錯誤digest算法都不能fallback授權。Stage仍重驗model dump，`signing_payload`亦重新驗證canonical欄位；非法model copy不先觸發資料／copy／healthcheck effects。

實際AST對公開f3f94c1比較：舊 `_digest`與 `ReleaseManifest.signing_payload`完全相同；ReleaseManager只有 `_verified`改動與 `_digest_v2`新增，其他11個原methods相同。原v1固定JSON/HMAC vector仍通過。沒有新增receipt rewrite、auto-resign、source格式猜測或資料回退；v1不能execution是明示的相容性安全更正，需要新版本明確重新批准。

## Actual verification

下列三次已真實執行，未為寫報告重跑：

| Command | Result |
|---|---|
| `.venv/bin/pytest -q tests/integration/test_release_tree_identity.py` | EXIT0；15 PASS／0.33s |
| `.venv/bin/pytest -q tests/integration/test_release_manifest_signing.py::test_canonical_payload_has_independent_fixed_bytes_and_signature tests/integration/test_release_manifest_signing.py::test_unvalidated_model_copy_cannot_bypass_entry_validation` | EXIT0；5 PASS／0.46s |
| `.venv/bin/pytest -q tests/integration/test_release_manifest_signing.py::test_readable_legacy_manifest_is_not_a_signature_fallback` | EXIT0；2 PASS／0.49s |

合計22個cases：原encoding歧義、獨立wire vector、boundary／path／count／empty／resource／Unicode、tag/algorithm混淆、legacy stage與selector／rollback零效果、v2正常staging與後續tamper，以及原canonical/copy/absent/None契約。此review未把正在更新的legacy positive fixtures當新production漏洞。

## Additional independent launch-selection fixture review

Root更新的 `tests/integration/test_release_launch_selection.py` SHA為 `b58abb536a5156661ec42c77d911672a9233b4971c1288653f7cb85785958e86`。其 `source_digest` helper使用獨立bytearray組wire後一次hashlib.sha256，不呼叫production ReleaseManager／`_digest`／`_digest_v2`。其wire遵循D56 domain／count／length／排序契約，receipt明確改v2。

對公開f3f94c1 AST比較，原22個assert nodes全部相同；diff僅更新fixture helper與format tag，没有降低原shape／alias／readonly／retention等斷言。這段是唯讀source核對，沒有另跑該fixture的pytest，也不宣稱其完整launcher acceptance PASS。

## Gates retained

這個小修復沒有解決parent驗簽後mutableimport、host destination alias、interpreter／venv／dependency identity、未知old/unmanagedwriter、人工批准maintenance→runtime lease handoff或bwrap TERM／Gateway drain。來源檔案identity不涵蓋empty directories、permissions或host dependencies。RI-005仍PARTIAL，這些source／lifecycle gates保持。

完整regression、exact rollback與new-head remote CI由root另驗；其他OS、powerloss、formal deployment與FIX002/005/006產品品質不由本review代證。[機器可讀結果](independent-review.json)。
