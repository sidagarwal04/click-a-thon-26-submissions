# Feature spec — Managed Booking Flow

## What it does
An eight-step assisted booking flow. The traveller picks an itinerary, books an
appointment slot, fills traveller details, uploads documents, is offered insurance,
pays, and receives a confirmation. Every step is strictly sequential: the product
will not render step N+1 until step N has emitted.

Two steps carry structured sub-objects rather than flat fields. The document scan
result and the payment instrument are each nested two levels deep, because the
upstream services return them that way and the SDK forwards the object verbatim.

## User actions (raw events emitted)
- `itinerary_viewed` — traveller opens an itinerary (`booking_id`, `destination`)
- `slot_selected` — picks an appointment slot (`slot_window`)
- `traveller_details_entered` — completes the personal-details form
- `document_uploaded` — uploads a document; carries a nested scan result
  (`document.kind`, `document.scan.quality_score`, `document.scan.page_count`)
- `insurance_offered` — an insurance add-on is shown (`insurance_tier`)
- `payment_initiated` — payment begins; carries a nested instrument
  (`payment.method`, `payment.card.network`, `payment.card.issuer_country`,
  `payment.amount_minor`)
- `payment_authorized` — the PSP authorises (`auth_latency_ms`)
- `booking_confirmed` — confirmation is issued

## Questions the PM will ask
- Step-through rate for all eight steps, and where the largest single drop sits.
- Does `payment.card.network` predict authorisation success?
- Does a low `document.scan.quality_score` predict abandonment at the next step?
- Authorisation latency by `device_type` and by `destination`.
