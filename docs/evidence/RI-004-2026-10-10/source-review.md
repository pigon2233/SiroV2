# D44 independent source review

Read-only reviewer：ri004_contract_research；root repairs。範圍 service／Gateway／actual-page UI 與 D44，不稱正式 worker certification。

1. Catalog order defect：typed match 在第一個 loop 提早 return，後方 computer.execute 未被提示。兩種 order 反例修前1FAIL/1PASS（catalog-order-before.log）；full-snapshot alternative prepass 局部修復→兩者PASS。分類 MINOR_FIX／IMPLEMENTATION_BUG，已在本卡解決，不留未完成 FIX task。
2. Failure code mismatch：service傳 verification_failed/rejected_report，UI只接受 binding_mismatch，安全拒絕但遺失可讀 failed evidence。统一 binding_mismatch；actual service forged UUID payload→actual page failed review/export，false authority flags保留。分類 MINOR_FIX／MISSING_INTEGRATION，已解決。

Follow-up：上述已清除；無剩餘 confirmed scoped blocker。單一 owned job／noqueue、offloop preparation/cleanup／repeatedcancel join、captured plugin→proposal／independent tests、無 host import／model／registry mutation／autoenable均檢視。信任來源是固定 template與 trusted verifier，不把候選 stdout 當批准。

Gateway second owner review與32 tests確認同一 catalog composition、strict ingress/gates、tools-off與shutdown nested cleanup。Frontend33 tests確認safe render/export、不一致authority拒絕、stale cancel／unknown network／reconnect無重送。實際Chrome23 checks及full1127與exact6 source rollback由root／另一agent執行，證據見REPORT；mock、真OS與產品鏈的界線分別列明。

No original design error confirmed。REJECT新增 planner／全域 state manager／第二registry；enabled generated skill worker與release/DB回退仍RED gate，這不是未修的本卡程式漏洞。
