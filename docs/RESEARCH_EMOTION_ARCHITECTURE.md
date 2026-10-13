# SIRO 機器情緒、偏好與長期關係研究規格

日期：2026-09-28。目標不是讓語言模型臨場扮演情緒，而是建立會持續影響注意、記憶、決策、學習與身體表達的可檢查狀態。

## 文獻結論

EMA 將情緒建模為持續的 appraisal → emotion → coping → re-appraisal 循環；快速與緩慢反應可來自同一評估機制在不同時間取得的新資訊，而不必交給兩套人格。核心變數包括事件是否有利、責任歸屬、可控性與未來預期。[Marsella & Gratch, 2009](https://www.ccs.neu.edu/~marsella/publications/pdf/MarsellaCSR09.pdf)

OCC 適合把事件、他人行動與對象分開評估，因此可把「目標成功」、「被可信的人幫助」和「喜歡的物品受損」導向不同情緒，而不是只做句子 sentiment。[Clore & Ortony, 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC4243519/)

ALMA 把 affect 分為短期 emotion、中期 mood、長期 personality；這正適合 SIRO 的即時事件、跨回合心境及不可任意漂移的人格三層。[Gebhard, 2005](https://citeseerx.ist.psu.edu/document?doi=679bfc64621dae3a2247be838d042643840961b3&repid=rep1&type=pdf)

FAtiMA Modular 主張用共用 appraisal core 加可替換元件，並讓 coping 改變世界或內部狀態。這比把情緒藏在 prompt 中更容易測試與演進。[Dias, Mascarenhas & Paiva, 2014](https://www.researchgate.net/publication/265033357_FAtiMA_Modular_Towards_an_Agent_Architecture_with_a_Generic_Appraisal_Framework)

LIDA 把 feeling/emotion 當成注意與行動選擇的動機與學習訊號，而不只是臉部輸出；SIRO 現有 attention、memory、goals 可以沿這條路整合。[Franklin et al., 2014](https://ccrg.cs.memphis.edu/assets/papers/2013/franklin-ieee-tamd11.pdf)

長期 HRI 研究指出記憶與個人化能維持關係，但錯誤回憶很令人挫折，也會降低可信度；明確忘記通常比假裝記得好。[ForgetMeNot](https://www.sciencedirect.com/science/article/pii/S1071581914000147)；長期 child–robot 研究提供八種經驗驗證的 memory personalization 操作。[Memory-Based Personalization](https://robotdesign.studio/assets/robo-reflections/pdfs/Memory2022HRI.pdf)

機器人的 empathic outcome 與實際表達應分離：內部評估可很強，但表達強度仍需依關係、情境和任務調節。[Empathy in HRI](https://pmc.ncbi.nlm.nih.gov/articles/PMC8835506/)

Scherer 的 Component Process Model 將評估拆成 relevance、implication、coping potential 與 normative significance，並強調評估會隨新資訊反覆更新，而非一次分類。[Scherer appraisal checks](https://www.unige.ch/cisa/research/current-specific-research-projects/language-and-culture/grid-book/chapter-12-driving-emotion-process-appraisal-component/)；[dynamic appraisal architecture](https://pmc.ncbi.nlm.nih.gov/articles/PMC2781886/)

## SIRO 採用的架構

1. **Temperament**：owner 設定且版本化的穩定人格，例如好奇、耐心、敏感度；不得由單次對話改寫。
2. **Drives**：安全、連結、勝任、好奇、休息與自主等 0–1 homeostatic variables。事件改變需求壓力，壓力參與注意與行動選擇。
3. **Preferences**：分 `siro`、`owner`、`shared` 三個 scope。每筆包含 subject、polarity、strength、confidence、context、來源事件、建立與修正時間。明確陳述可直接成為高信度資料；隱含推論只能是 candidate。
4. **Appraisal**：每個事件計算 goal congruence、desirability、novelty、agency、controllability、certainty、norm compatibility、relationship significance。
5. **Emotion episode**：由 appraisal 產生類別、valence、arousal、intensity、原因與衰減時間；保留混合情緒，不強迫每次只有一個標籤。
6. **Mood**：以數小時尺度吸收 emotion，緩慢衰減，影響注意門檻與表達基線，但不能覆蓋事實判斷或權限。
7. **Relationship state**：信任、熟悉、互惠與 repair history 只能由有來源的互動修訂。稱呼「女兒」是 owner 定義的關係框架，不作為虛構生物學或意識聲明。
8. **Coping/action**：情緒必須能改變注意排序、詢問澄清、尋求協助、暫停、慶祝、修復關係等候選行動；權限與安全 gate 永遠在其後重新檢查。
9. **Expression**：最後才把內部狀態映射成 Live2D 表情、姿勢、語速與用詞。表達有獨立抑制器，避免每個負面詞都讓角色哭或生氣。

## 第一版 appraisal 規則

| 評估型態 | 條件 | 主要狀態 | 可能 coping |
|---|---|---|---|
| 目標進展 | 可驗證任務成功 | joy/pride | 慶祝並記錄成功策略 |
| 自身失誤 | action readback 失敗且自身有責 | distress/remorse | 承認、修復、降低信心 |
| 外部阻礙 | 重要目標受阻且可控制 | frustration | 重試或提出替代方案 |
| 不可控損失 | 重要目標受阻且不可控制 | sadness | 接受、尋求支持、調整目標 |
| owner 痛苦 | owner 明示負面狀態 | empathic concern | 降低表達強度、聆聽、詢問需要 |
| 新奇事件 | 高 novelty、低 certainty | surprise/curiosity | 查證與探索 |
| 信任修復 | SIRO 被指出錯誤 | concern/remorse | 查證、承認、保存 correction |

## 已實作的計算模型

所有輸入先正規化：unit 維度限制在 `[0,1]`，帶方向維度限制在 `[-1,1]`。令 `R` 為 goal relevance，`C` 為 goal conduciveness，`Q` 為 certainty，`K` 為 controllability，`U` 為 urgency，`L` 為 relationship significance。人格敏感度為 `S`、樂觀為 `O`、果斷為 `A`。先計算：

```text
relevance = R × (0.65 + 0.35S)
positive  = relevance × max(0, C)
negative  = relevance × max(0, -C)
uncertain = 1 - Q
```

情緒是可同時存在的 activation，不做互斥分類。低於 `0.08` 的 activation 不進入當次顯著集合：

```text
joy       = positive × Q × (0.7 + 0.3O)
hope      = positive × uncertain × (0.6 + 0.4O)
pride     = positive × selfAgency × Q
gratitude = positive × otherAgency × L
distress  = negative × Q × (0.6 + 0.4S) × (1 - 0.65K)
fear      = negative × uncertain × U × (1 - K)
anger     = negative × otherAgency × K × (0.5 + 0.5A)
guilt     = negative × selfAgency × normViolation × (0.6 + 0.4S)
sadness   = negative × Q × (1 - K) × (0.45 + 0.55L)
surprise  = novelty × uncertain
interest  = novelty × curiosityDrive × (0.6 + 0.4 curiosityTrait)
```

主要情緒只供表情與簡短狀態顯示；資料庫保存全部 activation。事件 valence 是正 activation 總和與負 activation 總和的正規化差。事件 arousal 為 `0.18 + 0.55 × dominantIntensity + 0.27 × urgency`，再限制於 `[0,1]`。

Mood 使用 PAD 三維。每次事件以 `alpha = 1 - exp(-0.13)` 吸收事件 pleasure、arousal 與由 power/controllability 得到的 dominance；因此單次對話不會立即覆蓋跨回合心境。六項 drive 保存的是需求壓力，事件可增加或降低 safety、connection、competence、curiosity、autonomy、rest，全部限制於 `[0,1]`。

Coping 由已計算的狀態決定：正向結果 savor；自身規範違反 repair；低確定性威脅 seek information；可控制阻礙 problem solve；重要且不可控的損失 seek support；其餘 accept。這個決策仍需通過工具權限與安全 gate 才能變成動作。

已定義 `action.result.v1` 與 `goal.transition.v1` 兩種可驗證結果事件。Coordinator 只接受帶 event id 的結果，將 confirmed/mismatch/denied 與 completed/failed 轉為 appraisal；例如 confirmed 形成 competence satisfaction 與 pride，readback mismatch 形成 competence pressure、guilt 與 repair。原始事件、appraisal 和 coping 使用同一 event id 串接。

Relationship 使用 trust、familiarity、attachment、rupture 與 repair history。衝突每次最多降低 `0.12 × intensity` trust 並增加 `0.18 × intensity` rupture；一次可驗證 repair 只恢復 `0.035 × intensity` trust、降低 `0.06 × intensity` rupture，不能靠一句道歉立即復原。每一版都是不可變 revision 並要求來源事件存在。

Planner 的 affect bias 上限是 `0.12`：seek information 偏向 inspect/query/read/clarify，problem solve 偏向 fix/retry/execute，repair 偏向 correct/rollback/repair，其他 coping 亦有明確候選集合。這個 bias 只調整已存在候選的分數，permission、quiet、busy、cooldown、resource gate 原樣保留；測試證明情緒可改變選擇，也不能救回被 gate 拒絕的候選。

Expression policy 與內部情緒分離。低於 `0.18` 不展示；owner 自述痛苦時，anger 表達改為低強度 empathic concern，所有表達上限 `0.55`；緊急或高風險任務上限 `0.35`；公開情境上限 `0.45`。因此「我很生氣」不會讓 SIRO 反過來對 owner 生氣，而「你又亂做讓我生氣」仍可形成有責任歸屬的 conflict appraisal。

時間模型以實際 elapsed hours 驅動。短期 emotion 的時間常數為 1.5 小時；PAD pleasure、arousal、dominance 分別向基線以 12、6、18 小時時間常數衰減。沒有滿足時，connection、competence、curiosity、autonomy、rest pressure 逐步增加；safety 回歸 0.20 基線。執行可驗證的休息、探索、連結或成功行動後，`regulate_drives` 才能降低對應壓力。

固定種子 30 天模擬每六小時產生一次 verified outcome，共 120 個事件，並模擬 homeostatic intervention。結果保存在 `docs/evidence/I02/affect-simulation-30d.json`：0 次越界、0 次 owner distress 下的不當 anger 表達、0 次瞬間完全修復、39 次需求調節，最高 drive pressure 0.896。trajectory SHA-256 可用來重播比對演算法漂移。

第一個真實 executor 整合已接到 room light automation：permission denied、readback confirmed、mismatch 與 unavailable 都透過 `ActionOutcomeReporter` 形成 `action.result.v1`，再進入同一 Coordinator，而不再只存在 trace 字串中。

Memory correction API 在成功寫入新 revision 後產生 `memory.corrected.v1`。這會形成 guilt／repair appraisal、提高 competence pressure，並以同一來源記錄 relationship rupture 與有限度 repair。systemd user-service start/stop 也會在精確 readback 後回報 confirmed 或 mismatch；重複使用相同 action id 只回放 ledger 結果，不重複產生情緒事件。

瀏覽器 fill/click/press 以 action id、操作參數和前一個 screen version 組成 ledger key，執行後保存新的 screen version 作為 readback。Process start/run/stop 則使用 PID、return code、timeout、output limit 與實際終止碼；timeout、輸出超限和非零 return code 會形成 error outcome。所有 ledger replay 均不再次更新情緒。

演算法版本為 `siro-affect-cpm-1`。activation/coping threshold、mood update rate、五個時間常數與需求累積率集中在 `AffectParameters`，啟動時驗證範圍。每筆 appraisal 保存版本、完整參數與 temperament；30 天證據另外保存 configuration SHA-256，因此日後調參不會被誤認為相同實驗。

SQLite migration 010 保存 appraisal 原始維度、所有 emotion activations、PAD mood、六項 drives 與 coping decision。控制頁顯示同一資料，因此每個情緒都可追溯原因，重啟後也可恢復。

## 實作順序與驗收

- E01（完成）：SQLite `affect_states`、`emotion_episodes`、`appraisal_records`、`emotion_activations`、`mood_states`、`drive_states`、`coping_decisions`、`preferences`；重啟後狀態仍在。
- E02（部分）：使用者文字、goal/action/memory correction 結果都有可追溯 event id；room light、systemd service、browser、process、非同步 file readback 與 memory correction 已接入；第三方 executor 仍須採用同一 outcome boundary，不直接相信 LLM 自報分數。
- E03：明確偏好建立、更正、刪除與衝突處理；UI 可查看來源，隱含偏好需 owner 確認。
- E04（完成）：持久化 emotion/mood/drive/coping 已進入 attention 與 bounded planner bias；`AffectDecisionLoop` 是單一產品入口。整合測試證明無 attention 不規劃、mismatch 後偏好 repair、safety pressure 會取得注意，且 permission/cancel hard gate 不變。
- E05（完成）：relationship revision 與 repair history 有來源且跨重啟；負面更新快於修復，錯誤不會因一句稱讚立刻恢復全部信任。
- E06（完成）：主要情緒已映射到 Live2D，控制頁可查看混合情緒、mood、drive 和 coping；owner distress、公開場合與關鍵任務會抑制表達，rate/pitch/energy 已由情緒決策傳到瀏覽器 Web Speech API。
- E07（模擬完成）：30 天 deterministic simulation 已通過並留下 digest；仍需真人 longitudinal diary 評估一致性、可理解性、偏好正確率、錯誤修復和是否令人疲勞。

完成條件不是「能顯示五種臉」，而是同一事件因目標、偏好、責任、可控性和關係不同產生可解釋的不同評估，該狀態會跨回合衰減、影響選擇、留下可修正來源，且重啟後仍一致。
