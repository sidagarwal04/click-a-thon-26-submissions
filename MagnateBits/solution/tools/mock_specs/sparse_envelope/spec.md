# Feature spec — Airport Kiosk Assist

## What it does
A self-service kiosk at the airport. A traveller can use it entirely anonymously —
scan a document, read the result, walk away — or sign in partway through and have the
visit attached to their account.

Because the kiosk is a shared physical device, the SDK cannot fill the usual envelope
for an anonymous visit: there is no signed-in account, and the device and geo fields
are suppressed by the kiosk operator's privacy configuration. Roughly two rows in five
therefore arrive with an empty envelope. Some of those rows omit the account key
altogether and some send it as an empty string; both are anonymous.

## User actions (raw events emitted)
- `kiosk_woken` — the kiosk leaves standby (`visit_id`, `kiosk_lane`)
- `scan_started` — a document is placed on the scanner (`scan_kind`)
- `scan_completed` — the scan resolves (`scan_result`, `scan_duration_ms`)
- `assist_requested` — the traveller calls a human agent (`assist_reason`)
- `visit_closed` — the visit ends (`close_reason`)

## Questions the PM will ask
- Distinct travellers assisted per day — counting only real accounts.
- Scan success rate, split by `scan_kind` and by `kiosk_lane`.
- What share of visits are fully anonymous, and do they convert differently?
- Median scan duration, and does calling an agent follow a slow scan?
