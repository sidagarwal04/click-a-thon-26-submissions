
# Event spec — Document Uploaded

## What it does
Fired each time a user successfully uploads a document during the application
form. Captures the document type, how it was captured, whether auto-scan was
used, and retry/failure information. Document friction is a major drop-off point
between `application_started` and `pay_now_clicked`.

## Event name
`document_uploaded`

## Emitted fields (beyond the standard envelope)
| Field | Type | Description |
|---|---|---|
| `doc_type` | string | Type of document uploaded (`passport_front`, `passport_back`, `photo`, `supporting_doc`) |
| `capture_mode` | string | How the user provided the document (`gallery`, `camera`, `qr`) |
| `scan_mode` | string | OCR/parse mode used (`auto`, `manual`) |
| `retry_count` | uint8 | Number of failed upload attempts before this success |
| `failed_attempt_threshold` | uint8 | Max retries allowed before fallback is offered (typically 3) |
| `is_crossed_failed_attempt_threshold` | uint8 | 1 if user hit the threshold and was offered a fallback |

## Standard envelope fields present
`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`,
`device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`,
`geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`,
`locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`,
`is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`,
`is_back_filled`, `duplicate_id`

## Questions the PM will ask
- What is the `retry_count` distribution by `doc_type` and `capture_mode`?
  Which combination causes the most friction?
- What share of uploads hit `is_crossed_failed_attempt_threshold = 1`, and
  does this predict application abandonment?
- Does `scan_mode = auto` succeed (lower retries) compared to `manual` for
  passport documents?
- Is there a platform (iOS vs Android) where document upload fails more often?
- Which destinations require the most document types, and does doc volume
  correlate with lower payment conversion?
