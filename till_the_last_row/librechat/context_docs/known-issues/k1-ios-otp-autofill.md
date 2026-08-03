---
type: known-issue
title: K1 — iOS WebKit OTP autofill regression
description: OTP field fails to autofill on recent iOS builds.
issue_id: K1
status: open
timestamp: 2026-08-01
tags: [known-issue, ios, payment]
---

# Symptom

On recent iOS builds the payment OTP field fails to autofill, and some users abandon at the pay step.

# Exposure

Payment-heavy geos (Gulf card users) are most exposed.

# Watch

`pay_now_clicked → purchase_completed` for iOS.

# Source

`base_context.md` §5.
