# First fixture startup failed

The new wrapper incorrectly removed the non-secret SIRO_CONTEXT_TOKEN_BUDGET_ENABLED setting while filtering credential variable names. Main refused the unsupported synthetic model budget before startup. This was fixture setup failure, not a product PASS or a product regression. The reused Probe.close finally removed its owned temporary tree; the receipt records temporary_removed=true. No Rust runtime was started.
