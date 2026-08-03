# Feature spec — Express Checkout (test fixture)

## User actions (raw events emitted)
- `express_checkout_shown` — button rendered
- `express_checkout_selected` — user taps Express
- `saved_method_used` — saved instrument loaded
- `otp_entered` — OTP submitted
- `express_payment_confirmed` — payment succeeds (nested `payment`)