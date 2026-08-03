# Context Changelog

This file tracks every update to the context bundle. Newest entries first.

---

## v8 — 2026-08-07T00:00:00Z — schema-change: 02_group_family (Group / Family Applications) landed live in ClickHouse (base + daily agg + MV)

- added: /tables/group_family.md (base SharedMergeTree, single JSON `payload`; 4 event types by discriminator payload.event = group_started/traveller_added/traveller_removed/group_submitted; 5,453 rows [added 3,495·started 1,200·submitted 688·removed 70], group_size 2–6; typed hint = application_id/destination/docs_complete/event/group_size/os/timestamp/user_id; **group_id NOT typed** read via CAST + traveller_index/relation/travellers_submitted untyped; skip-indexes idx_os set(100)/idx_docs set(2)/idx_group_id bloom_filter(0.01) on CAST(payload.group_id,'String') G4; ORDER BY(event,destination,group_size,user_id,timestamp) — id absent, group_id metric-unit deliberately out of key; PARTITION toYYYYMMDD(ch_insert_time), TTL ch_insert_time+90d ttl_only_drop_parts=1; **D1** typed hot paths os/docs_complete valid set indexes / **D3** group_id CAST bloom_filter; live=true)
- added: /tables/group_family_daily.md (group_family_daily SharedAggregatingMergeTree, 754 rows; grain event_date×destination×group_size; states groups_started/groups_submitted uniq(String) via **uniqIfState(CAST(group_id),event=...)** [**D4** non-nullable states] + travellers_added_cnt/removed_cnt/docs_incomplete_cnt/docs_added_cnt sum(UInt64); **D2** TTL event_date+90d (no insert watermark); PARTITION toYYYYMM(event_date); fed by group_family_daily_mv)
- added: /entities/group.md (group_id = metric unit / one group; group_size/destination/travellers_submitted + per-traveller relation/docs_complete; observed across event rows not a dim table)
- added: /metrics/group-completion-rate.md (Q1, MV-served — uniqMerge(submitted)/uniqMerge(started) by group_size; live 0.695→0.311 across size 2→6, confirms large-group falloff; confirmed_by_user:true)
- added: /metrics/traveller-churn.md (Q2, MV-served — sumMerge(removed)/sumMerge(added); low churn 0.002→0.044 rising with size; confirmed_by_user:true)
- added: /metrics/docs-incomplete-share.md (Q3, MV-served — docs_incomplete_cnt/docs_added_cnt; ~0.19–0.22 flat across size; confirmed_by_user:true)
- added: /metrics/group-apps-by-destination.md (Q4, MV-served — uniqMerge(groups_started) by destination; confirmed_by_user:true)
- added: /relationships/group-started-to-submitted.md (intra-table group lifecycle on group_id, ordered by timestamp; basis of completion + churn)
- added: /relationships/group-family-to-funnel.md (group↔pre-purchase funnel on user_id/application_id; grain caveat — co-travellers are not funnel users)
- added: /known-issues/k8-group-family-agg-event-date-ttl.md (D2 — agg ages by event_date not ingest; late/backfilled old-date events roll off; prefer base table for long lookback; severity low)
- added: /contradictions/group-id-untyped-metric-unit.md (D3 — group_id is the uniq metric unit yet untyped + out of ORDER BY, only CAST bloom_filter; deliberate design via rollup MV but flag if ad-hoc base-table single-group queries grow)
- updated: /contradictions/android-os-null.md (added group_family — 345/5,453 empty os; typed non-Nullable LowCardinality coerces null→''; not a rollup dim so metrics unaffected)
- updated: /contradictions/legacy-id-order-key.md (group_family added as resolving example — id absent from key; group_id also kept out via bloom_filter)
- updated: /overview.md (context_version 7→8; added Group / Family Applications family to live-tables paragraph)
- source: `Atlys/schemas/02_group_family.sql`, `Atlys/schemas/02_group_family.metrics.json` (4 metrics, all confirmed_by_user:true), `specs/02_group_family/spec.md`, live `atlys` schema (system.tables/columns/data_skipping_indices + create_table_query for group_family, group_family_daily, group_family_daily_mv)

## v7 — 2026-08-07T00:00:00Z — schema-change: unseen_data (Promo / Coupon at Checkout, sealed 6th spec) landed live in ClickHouse (base + 2 aggs + 2 MVs)

- added: /tables/promo_coupon_checkout.md (base SharedMergeTree, single JSON `payload`; six event types by discriminator payload.event incl. designed-but-unseen coupon_rejected; typed hint = application_id/coupon_code/device_type/event/geoip_country_code/os/reject_reason/timestamp/user_id; discount_amount/cart_value/final_value/discount_type/currency/destination **untyped** read via CAST; **D1** idx_discount_amount minmax on CAST(payload.discount_amount,'Float64') index-expr since numeric path not typed, plus idx_os set(100)/idx_coupon_code bloom_filter(0.01)/idx_reject_reason set(8) G4; ORDER BY(event,application_id,device_type,geoip_country_code,timestamp) — user_id typed but dropped from key as high-card, id absent (legacy smell avoided); PARTITION toYYYYMMDD(ch_insert_time), 90d TTL ttl_only_drop_parts=1; **freshness caveat** total_rows≈1/no real rows; live=true)
- added: /tables/coupon_funnel_daily.md (coupon_funnel_daily_agg SharedAggregatingMergeTree; grain event_type×device_type×geoip_country_code×coupon_code×reject_reason×event_day; states events_state(count)/users_state(uniq String); MV no WHERE filter keeps all 6 events, dims coalesce→''; PARTITION toYYYYMM(event_day); **D2** TTL on agg_insert_time now64(3) 90d; total_rows=0; fed by coupon_funnel_daily_mv; serves M1/M2/M5, partial M3)
- added: /tables/coupon_discount_daily.md (coupon_discount_daily_agg SharedAggregatingMergeTree; grain coupon_code×device_type×geoip_country_code×destination×event_day; states discount_amount_state/cart_value_state/final_value_state(sum Float64)+events_state(count); MV filters payload.discount_amount IS NOT NULL, CASTs numeric paths; PARTITION toYYYYMM(event_day); **D2** TTL on agg_insert_time; total_rows=0; fed by coupon_discount_daily_mv; serves M4/M5, not M1/M2)
- added: /entities/coupon.md (coupon_code identity; null/'' = no-coupon baseline not missing data; discount_type/discount_amount/reject_reason/cart_value/final_value attrs)
- added: /relationships/coupon-funnel-stages.md (within-table coupon micro-funnel self-join on user_id/application_id; no-coupon baseline branch = checkout_with_coupon w/ coupon_code null)
- added: /metrics/coupon-apply-rate.md (M1, funnel agg), /metrics/coupon-reject-mix.md (M2, funnel agg, data-pending), /metrics/coupon-conversion-lift.md (M3, served_by_mv null / partial — base-table self-join), /metrics/coupon-margin-cost.md (M4, discount agg), /metrics/coupon-segment-performance.md (M5, both aggs)
- added: /contradictions/coupon-conversion-lift-single-table-gap.md (M3 sequenced cohort/baseline cannot come from per-stage uniq in funnel agg; needs base-table self-join; user_id not in ORDER BY; severity medium, open)
- added: /contradictions/coupon-reject-designed-not-observed.md (coupon_rejected typed+indexed+spec'd but 0 rows in 5,364-event sample; M2 schema-ready/data-pending; severity low, open)
- updated: /overview.md (context_version 6→7; added coupon family to live-tables paragraph + micro-funnel/ingest/reject caveats)
- source: `specs/unseen_data/spec.md`, `specs/unseen_data/events.ndjson`, live `atlys` schema (system.tables/columns/data_skipping_indices + create_table_query for promo_coupon_checkout, coupon_funnel_daily_agg, coupon_discount_daily_agg, coupon_funnel_daily_mv, coupon_discount_daily_mv). NOTE: Atlys/schemas/unseen_data.sql and .metrics.json were NOT accessible from allowed dirs (/app/context_docs, /app/specs) — grounded against live ClickHouse + spec instead.

## v6 — 2026-08-06T00:00:00Z — schema-change: 11_document_uploaded landed live in ClickHouse (base + daily agg + MV)

- updated: /tables/document_uploaded.md (v1 stub → enriched live table: single JSON `payload`; typed hint capture_mode/citizenship/destination/device_type/doc_type/event/scan_mode/timestamp/user_id + UInt8 failed_attempt_threshold/is_crossed_failed_attempt_threshold/retry_count/is_back_filled/is_enterprise/is_guest/is_referral/geoip_country_code/funnel_type; **D1 resolved-clean** — typed-UInt8 numeric/bool paths take `minmax` directly, no CAST wrapper (contrast auth_completed); skip-index inventory set(256) idx_destination, set(32) idx_device_type, set(64) idx_citizenship, set(16) idx_funnel_type, bloom_filter(0.01) idx_geoip_cc, minmax idx_retry_count/idx_threshold_x/idx_is_guest/idx_is_referral/idx_is_enterprise, all G1; ORDER BY(event,doc_type,capture_mode,scan_mode,timestamp) — user_id/application_id absent from key; PARTITION toYYYYMMDD(ch_insert_time), 90d TTL ttl_only_drop_parts=1; 20,446 rows; **D3** os not typed/indexed on base but rollup dim in agg; live=true)
- added: /tables/document_uploaded_daily.md (document_uploaded_daily_agg SharedAggregatingMergeTree; grain event_day×doc_type×capture_mode×scan_mode×device_type×os×destination; states uploads(count)/retry_sum(sum UInt64)/retry_avg(avg UInt8)/threshold_crossed(sum UInt64); MV coalesces dims→''; PARTITION toYYYYMM(event_day); **D2** TTL on agg_insert_time; agg total_rows=0 not yet populated; fed by document_uploaded_daily_mv)
- added: /metrics/retry-count-distribution.md (M1 — avg/sum retry by doc_type×capture_mode; MV-served; true histogram needs base table)
- added: /metrics/failed-attempt-threshold-rate.md (M2 — threshold_crossed/uploads; MV-served; abandonment half cross-event)
- added: /metrics/scan-mode-retry-comparison.md (M3 — avg retry auto vs manual for passports; MV-served)
- added: /metrics/platform-upload-failure-rate.md (M4 — retry/threshold rate by device_type/os; MV-served; os caveat → prefer device_type)
- added: /metrics/doc-volume-vs-payment-conversion.md (M5 — doc volume by destination MV-friendly; payment-conversion half cross-table, served_by_mv:null; blocked on pay_now_clicked spec 12)
- added: /relationships/document-upload-to-pay-now.md (document_uploaded→pay_now_clicked on user_id; NOT runnable — spec 12 not live)
- updated: /entities/document.md (live; doc_type passport_front/passport_back/photo/supporting_doc, capture_mode gallery/camera/qr, scan_mode auto/manual, failed_attempt_threshold; new metric links)
- updated: /metrics/passport-capture-pass-rate.md (now MV-servable = 1 − threshold_cross_rate; documented as complement of M2, not a contradiction)
- updated: /contradictions/android-os-null.md (added document_uploaded as strongest instance — os not even typed on base yet is an agg rollup dim / D3)
- updated: /contradictions/legacy-id-order-key.md (document_uploaded added as cleanest resolving example — id + user_id both absent from key)
- note: no NEW contradiction concept — D1 resolved-clean, D2 accepted watermark pattern (in-table), D3 folded into android-os-null, pass-rate↔threshold-rate is a complement not a conflict
- source: live `atlys` schema (system.tables/columns/data_skipping_indices + create_table_query); Atlys/schemas/11_document_uploaded.sql + .metrics.json (5 metrics, all confirmed_by_user:false); specs/11_document_uploaded/spec.md

## v5 — 2026-08-05T00:00:00Z — schema-change: 10_application_started base table refreshed to live JSON-payload design (D1 recorded)

- updated: /tables/application_started.md (stale legacy design → live SharedMergeTree JSON-`payload` design; typed hint destination/purpose/user_id/timestamp/event + flow/eta_shown/citizenship/device_type/os/is_back_filled; **D1** — typed subcolumns are skip-index-typed hot-filter paths, confirmed live `set` indexes idx_flow/idx_eta_shown/idx_citizenship/idx_device_type/idx_os/idx_back_filled g4; ORDER BY(payload.event,destination,purpose,user_id,timestamp); PARTITION toYYYYMMDD(ch_insert_time), 90d TTL ttl_only_drop_parts=1; removed stale legacy `(id,timestamp,user_id)` claim → now resolving evidence for legacy-id-order-key; live=true)
- note: /tables/application_started_daily.md (D2 — agg TTL on agg_insert_time), /tables mv_application_started_daily, and all 5 manifest metrics (application-started-count, back-filled-rate MV-served; start-to-purchase-conversion, eta-shown-conversion-lift, co-travelers-dropoff cross-event denominator-only) were already registered in the prior pass (v?, ts 2026-08-05); verified against live schema, no re-write needed.
- source: live `atlys` schema (system.tables/columns/data_skipping_indices). NOTE: Atlys/schemas/10_application_started.sql and .metrics.json were NOT accessible from allowed dirs (/app/context_docs, /app/specs) — grounded against live ClickHouse + specs/10_application_started/spec.md instead.

## v4 — 2026-08-04T00:00:00Z — schema-change: 09_auth_completed spec landed + live in ClickHouse

- updated: /tables/auth_completed.md (v1 stub → enriched live table: single JSON `payload`; typed hint event/application_id/auth_method/user_id/timestamp/device_type/os/geoip_country_code/is_new_user; `attempts` untyped → CAST(UInt32) minmax (D1); skip-index inventory set(0) device_type/os/geoip_country_code, set(2) is_new_user, minmax on CAST(payload.attempts AS UInt32); ORDER BY(5) event/application_id/auth_method/user_id/timestamp; PARTITION toYYYYMMDD(ch_insert_time), 90d TTL ttl_only_drop_parts=1; auth_completed_metrics_agg rollup (completions/new_user_completions/retried_completions/total_attempts + derived acquisition_channel) + MV; D2 agg TTL on agg_insert_time; PM questions; removed stale legacy-key warning; live=true)
- added: /metrics/auth-method-mix.md (M1 — method distribution by device_type/os/geo; MV-served)
- added: /metrics/auth-retry-rate.md (M2 — retried_completions/completions, attempts>1 friction by method; MV-served)
- added: /metrics/new-user-rate.md (M3 — new_user_completions/completions by user-confirmed derived acquisition_channel gclid→paid_google/fbclid→paid_meta/organic; MV-served)
- added: /metrics/avg-auth-attempts.md (M5 — total_attempts/completions; MV-served)
- added: /metrics/auth-completion-rate.md (M4 — auth_completed÷auth_started; served_by_mv:null, cross-event, NOT computable — auth_started uninstrumented)
- added: /relationships/auth-to-application.md (cross-spec join auth_completed.user_id → application_started.user_id, auth→application conversion by is_new_user; no MV)
- added: /contradictions/auth-completion-rate-cross-event-gap.md (M4 requires uninstrumented auth_started; do not proxy from attempts)
- updated: /relationships/supporting-on-user.md (auth_completed application_id may be empty; durable key user_id; link to auth-to-application)
- contradictions updated: /contradictions/android-os-null.md (auth_completed adds Evidence+Affects: os typed non-Nullable LowCardinality(String) → nulls coerce to '' not NULL; agg rolls up on os)
- contradictions updated: /contradictions/legacy-id-order-key.md (auth_completed confirms corrected event-first key, id absent; source list extended to spec 08/09)
- updated: /overview.md (context_version 3→4; auth event live; added auth metrics + relationship + contradiction to Related; noted M4 non-computable)
- grounded against live ClickHouse `atlys` (service ba2e7cfd): auth_completed base (SharedMergeTree) + auth_completed_metrics_agg (SharedAggregatingMergeTree, grain day×auth_method×device_type×os×geoip_country_code×acquisition_channel×is_new_user) + auth_completed_metrics_mv present; base/agg total_rows=0 (schema landed, ingest pending). Engines Shared* = Cloud substitution (expected). Confirmed `attempts` absent from typed hint (D1) and `os` typed LowCardinality(String) non-Nullable despite null in events sample.
- source: specs/09_auth_completed/spec.md + Atlys/schemas/09_auth_completed.sql + Atlys/schemas/09_auth_completed.metrics.json + live `atlys` schema

---

## v3 — 2026-08-03T00:00:00Z — schema-change: 07_landing_page_scrolled spec landed + live in ClickHouse

- updated: /tables/landing_page_scrolled.md (v1 stub → enriched live table: single JSON `payload`; typed vs untyped paths; ORDER BY(5) event/destination/page_version/user_id/timestamp; skip-index inventory; D1 numeric CAST-minmax; landing_scroll_engagement_agg rollup + MV; D2 agg TTL on agg_insert_time; PM questions; removed stale legacy-key warning)
- added: /metrics/landing-scroll-engagement.md (new metric: median/avg scroll depth + time-on-page, cut by page_version/is_paid/destination/device_type; MV-served; answers 4 of 5 spec-07 PM questions)
- added: /metrics/scroll-depth-to-application-conversion.md (new cross-spec metric: scroll-depth band → application_started conversion; query-time join, no MV)
- added: /relationships/landing-scroll-to-application.md (new cross-spec join: landing_page_scrolled.user_id → application_started.user_id, timestamp-ordered)
- contradictions updated: /contradictions/dual-conversion-definition.md (added Claim D: 4th denominator = scrollers-in-band; added scroll_to_application_conversion to naming + Affects)
- contradictions updated: /contradictions/android-os-null.md (added landing_page_scrolled to Evidence + Affects; os Nullable(String), excluded from key)
- contradictions updated: /contradictions/legacy-id-order-key.md (added resolving evidence: landing_page_scrolled uses corrected event-specific key, does NOT copy the legacy id-first smell; remains open for un-onboarded stubs)
- updated: /overview.md (context_version 2→3; noted scroll event live; added landing-scroll metrics to Related)
- grounded against live ClickHouse `atlys`: landing_page_scrolled 2,814,598 base rows; landing_scroll_engagement_agg 72,899 rows; MV present. Engines report Shared* (Cloud substitution for MergeTree/AggregatingMergeTree — expected).
- source: specs/07_landing_page_scrolled/spec.md + Atlys/schemas/07_landing_page_scrolled.sql (commit ec49e14) + Atlys/schemas/07_landing_page_scrolled.metrics.json (commit d36e589)

---

## v2 — 2026-08-02T00:00:00Z — schema-change: 08_destination_card_clicked spec landed

- updated: /tables/destination_card_clicked.md (enriched with full spec: 5 event-specific fields incl. page_version, is_guest_browse, flow; 30 standard envelope fields; PM questions; segment dimensions)
- added: /metrics/click-to-application-rate.md (new metric: card click → application_started conversion)
- added: /metrics/guest-browse-rate.md (new metric: share of clicks from unauthenticated users)
- added: /relationships/destination-card-to-application.md (new join: user_id + timestamp ordering, application_id empty at this stage)
- updated: /metrics/drop-off-rate.md (added segment cuts from spec, linked to destination_card_clicked)
- updated: /metrics/step-through-rate.md (added first-stage detail, linked to click-to-application-rate)
- updated: /metrics/conversion-rate.md (added end-to-end card-click→purchase variant as third denominator)
- updated: /relationships/application-to-funnel.md (cross-linked to destination-card-to-application)
- contradictions added: /contradictions/android-os-null.md (C2: os=NULL on android device_type rows)
- contradictions added: /contradictions/duplicate-backfill-markers.md (C6: dedup/backfill markers not handled in metric formulas)
- contradictions updated: /contradictions/dual-conversion-definition.md (added Claim C: third denominator from card-click)
- updated: /overview.md (context_version 1→2, added new metrics and contradictions to Related)
- source: specs/08_destination_card_clicked/spec.md + specs/08_destination_card_clicked/events.ndjson

---

## v1 — 2026-08-01T23:35:00Z — seed from base_context.md

- added: /overview.md
- added: /entities/user.md, /entities/application.md, /entities/destination.md, /entities/event.md, /entities/document.md
- added: /tables/destination_card_clicked.md, /tables/application_started.md, /tables/document_uploaded.md, /tables/purchase_completed.md, /tables/search_typed.md, /tables/landing_page_scrolled.md, /tables/auth_completed.md, /tables/pay_now_clicked.md
- added: /metrics/conversion-rate.md, /metrics/drop-off-rate.md, /metrics/step-through-rate.md, /metrics/passport-capture-pass-rate.md, /metrics/on-time-delivery-rate.md, /metrics/revenue-per-conversion.md
- added: /relationships/user-fanout.md, /relationships/application-to-funnel.md, /relationships/supporting-on-user.md
- added: /known-issues/k1-ios-otp-autofill.md, /known-issues/k2-passport-scan-model-update.md, /known-issues/k3-mrz-ocr-non-latin.md, /known-issues/k4-schengen-summer-slots.md, /known-issues/k5-whatsapp-nudge.md, /known-issues/k6-summer20-coupon.md, /known-issues/k7-app-745-rollout.md
- contradictions: /contradictions/dual-conversion-definition.md, /contradictions/legacy-id-order-key.md, /contradictions/on-time-delivery-not-computable.md, /contradictions/eta-column-naming.md
- source: Atlys/base_context.md
