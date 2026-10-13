# Detached / duplicate code

「未接 Gateway」不等於可以刪除。以下全部保留；沒有證據支持把整個 subsystem 判定 dead。

| 候選 | 現有 caller / 活動路徑 | 分類與證據 | 處置 |
|---|---|---|---|
| FailoverModel | contract tests；main 不 instantiate | detached product integration；adapters/models/failover.py | KEEP |
| core/router、governor、nodes/jobs | tests/compute demo；main 不 instantiate | 獨立完整元件，產品 detached | KEEP |
| AffectDecisionLoop、AffectAwarePlanner | test_affect_outcomes | 與 IntegratedCompanion 直接 appraise 並存 | KEEP，勿宣稱主 loop 已使用 |
| ConsolidationScheduler | test_consolidation | 無 Gateway startup registration | KEEP |
| ProactivityRules / room controller | tests、scripts/t29_room_demo.py | 獨立 demo 可到達，產品未接 | KEEP |
| LocalRuntimeClient / scoped computer adapters | boundary/driver tests | Python Gateway direct subprocess 為目前產品路徑 | KEEP；權限邊界待分析 |
| process.start executor / application_tool | main 有註冊；legacy shortcuts 可呼叫 | 模型 catalog 未列出，非全域 unreachable | KEEP |
| legacy keyword shortcuts | create_app legacy_shortcuts=True tests | 正式 default=False | LEGACY_OR_UNUSED（僅正式 profile 範圍） |
| GroqOrpheus / synthesize_or_fallback / SpeechPlayback | audio pipeline tests、real opt-in | 主頁用 render HTTP/Qwen；不是當前 TTS main | KEEP 相容/測試路徑 |
| Edge/Kokoro | Qwen assets 不在時 startup fallback | 仍可到達，不能標 dead | KEEP |
| ModelMessage serializer | adapter contract tests | ConversationEngine 尚不傳 messages | 未接入的既有變更；不要继续改 |
| OfflineDemoModel | no model env 時 main fallback + CLI demo | 正式可達，明確是 offline behavior | KEEP |

靜態掃描所有 Python imports 與 symbols 見 SOURCE_INVENTORY.json。未在 Gateway import closure 的 module 只列為調查候選；dynamic import、scripts、CLI 和 tests 可能仍使用它。不以 grep 零結果作刪除授權。

TODO/pass 搜尋未找到主要功能的 NotImplemented stub；例外類別空 body 合法。ESP32 source 存在但未燒錄驗證不能叫 dead，也不能叫 VERIFIED_COMPLETE。
