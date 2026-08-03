# Context layer diff - deep_linear

Run `003389e657fb4958a0d999a278b021bc` | context v8 -> v9

## What changed

Context layer moved **v8 -> v9**: 173 added, 0 updated, 0 superseded, 10 contradictions, 7 gaps.

### Added

- **`business_def.deep_linear.funnel` v1** (business_def) - deep_linear funnel: Ordered steps on `atlys.f_deep_linear_events`: itinerary_viewed -> slot_selected -> traveller_details_entered -> document_uploaded -> insurance_offered -> payment_initiated -> payment_authorized -> booking_confirmed (step order source: spec). Segment dimensions: device_type, os, city, geoip_country_code, destination, app_version, client_lib, payment_card_network, payment_method, insurance_tier. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, client_lib, destination, device_type, event, f_deep_linear_events, geoip_country_code, insurance_tier, os, payment_card_network, payment_method]_
- **`column.agg_deep_linear_auth_latency_daily.auth_count_state` v1** (column_doc) - agg_deep_linear_auth_latency_daily.auth_count_state: auth_count_state AggregateFunction(count) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, auth_count_state]_
- **`column.agg_deep_linear_auth_latency_daily.card_network` v1** (column_doc) - agg_deep_linear_auth_latency_daily.card_network: card_network LowCardinality(String) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, card_network]_
- **`column.agg_deep_linear_auth_latency_daily.day` v1** (column_doc) - agg_deep_linear_auth_latency_daily.day: day Date on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, day]_
- **`column.agg_deep_linear_auth_latency_daily.destination` v1** (column_doc) - agg_deep_linear_auth_latency_daily.destination: destination LowCardinality(String) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, destination]_
- **`column.agg_deep_linear_auth_latency_daily.device_type` v1** (column_doc) - agg_deep_linear_auth_latency_daily.device_type: device_type LowCardinality(String) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, device_type]_
- **`column.agg_deep_linear_auth_latency_daily.latency_avg_state` v1** (column_doc) - agg_deep_linear_auth_latency_daily.latency_avg_state: latency_avg_state AggregateFunction(avg, UInt32) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, latency_avg_state]_
- **`column.agg_deep_linear_funnel_daily.bookings_state` v1** (column_doc) - agg_deep_linear_funnel_daily.bookings_state: bookings_state AggregateFunction(uniq, String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, bookings_state]_
- **`column.agg_deep_linear_funnel_daily.day` v1** (column_doc) - agg_deep_linear_funnel_daily.day: day Date on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, day]_
- **`column.agg_deep_linear_funnel_daily.destination` v1** (column_doc) - agg_deep_linear_funnel_daily.destination: destination LowCardinality(String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, destination]_
- **`column.agg_deep_linear_funnel_daily.device_type` v1** (column_doc) - agg_deep_linear_funnel_daily.device_type: device_type LowCardinality(String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, device_type]_
- **`column.agg_deep_linear_funnel_daily.event` v1** (column_doc) - agg_deep_linear_funnel_daily.event: event LowCardinality(String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, event]_
- **`column.agg_deep_linear_funnel_daily.events_state` v1** (column_doc) - agg_deep_linear_funnel_daily.events_state: events_state AggregateFunction(count) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, events_state]_
- **`column.agg_deep_linear_funnel_daily.users_state` v1** (column_doc) - agg_deep_linear_funnel_daily.users_state: users_state AggregateFunction(uniq, String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, users_state]_
- **`column.agg_double_fanout_funnel_daily.app_version` v1** (column_doc) - agg_double_fanout_funnel_daily.app_version: app_version LowCardinality(String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, app_version]_
- **`column.agg_double_fanout_funnel_daily.city` v1** (column_doc) - agg_double_fanout_funnel_daily.city: city LowCardinality(String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, city]_
- **`column.agg_double_fanout_funnel_daily.day` v1** (column_doc) - agg_double_fanout_funnel_daily.day: day Date on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, day]_
- **`column.agg_double_fanout_funnel_daily.event` v1** (column_doc) - agg_double_fanout_funnel_daily.event: event LowCardinality(String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, event]_
- **`column.agg_double_fanout_funnel_daily.events_state` v1** (column_doc) - agg_double_fanout_funnel_daily.events_state: events_state AggregateFunction(count) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, events_state]_
- **`column.agg_double_fanout_funnel_daily.topic` v1** (column_doc) - agg_double_fanout_funnel_daily.topic: topic LowCardinality(String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, topic]_
- **`column.agg_double_fanout_funnel_daily.uniq_entities` v1** (column_doc) - agg_double_fanout_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, uniq_entities]_
- **`column.agg_double_fanout_funnel_daily.uniq_users` v1** (column_doc) - agg_double_fanout_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, uniq_users]_
- **`column.agg_mutation_heavy_funnel_daily.day` v1** (column_doc) - agg_mutation_heavy_funnel_daily.day: day Date on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, day]_
- **`column.agg_mutation_heavy_funnel_daily.event` v1** (column_doc) - agg_mutation_heavy_funnel_daily.event: event LowCardinality(String) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, event]_
- **`column.agg_mutation_heavy_funnel_daily.events_state` v1** (column_doc) - agg_mutation_heavy_funnel_daily.events_state: events_state AggregateFunction(count) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, events_state]_
- **`column.agg_mutation_heavy_funnel_daily.item_category` v1** (column_doc) - agg_mutation_heavy_funnel_daily.item_category: item_category LowCardinality(String) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, item_category]_
- **`column.agg_mutation_heavy_funnel_daily.items_after` v1** (column_doc) - agg_mutation_heavy_funnel_daily.items_after: items_after UInt8 on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, items_after]_
- **`column.agg_mutation_heavy_funnel_daily.sum_basket_value_minor` v1** (column_doc) - agg_mutation_heavy_funnel_daily.sum_basket_value_minor: sum_basket_value_minor AggregateFunction(sum, Decimal(18, 4)) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, sum_basket_value_minor]_
- **`column.agg_mutation_heavy_funnel_daily.uniq_entities` v1** (column_doc) - agg_mutation_heavy_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, uniq_entities]_
- **`column.agg_mutation_heavy_funnel_daily.uniq_users` v1** (column_doc) - agg_mutation_heavy_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, uniq_users]_
- **`column.agg_sparse_envelope_funnel_daily.app_version` v1** (column_doc) - agg_sparse_envelope_funnel_daily.app_version: app_version LowCardinality(String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, app_version]_
- **`column.agg_sparse_envelope_funnel_daily.avg_scan_duration_ms` v1** (column_doc) - agg_sparse_envelope_funnel_daily.avg_scan_duration_ms: avg_scan_duration_ms AggregateFunction(avg, UInt32) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, avg_scan_duration_ms]_
- **`column.agg_sparse_envelope_funnel_daily.city` v1** (column_doc) - agg_sparse_envelope_funnel_daily.city: city LowCardinality(String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, city]_
- **`column.agg_sparse_envelope_funnel_daily.day` v1** (column_doc) - agg_sparse_envelope_funnel_daily.day: day Date on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, day]_
- **`column.agg_sparse_envelope_funnel_daily.event` v1** (column_doc) - agg_sparse_envelope_funnel_daily.event: event LowCardinality(String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, event]_
- **`column.agg_sparse_envelope_funnel_daily.events_state` v1** (column_doc) - agg_sparse_envelope_funnel_daily.events_state: events_state AggregateFunction(count) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, events_state]_
- **`column.agg_sparse_envelope_funnel_daily.geoip_country_code` v1** (column_doc) - agg_sparse_envelope_funnel_daily.geoip_country_code: geoip_country_code LowCardinality(String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, geoip_country_code]_
- **`column.agg_sparse_envelope_funnel_daily.uniq_entities` v1** (column_doc) - agg_sparse_envelope_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, uniq_entities]_
- **`column.agg_sparse_envelope_funnel_daily.uniq_users` v1** (column_doc) - agg_sparse_envelope_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, uniq_users]_
- **`column.f_deep_linear_events.app_version` v1** (column_doc) - f_deep_linear_events.app_version: app_version LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: app_version, f_deep_linear_events]_
- **`column.f_deep_linear_events.auth_latency_ms` v1** (column_doc) - f_deep_linear_events.auth_latency_ms: auth_latency_ms UInt32 on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: auth_latency_ms, f_deep_linear_events]_
- **`column.f_deep_linear_events.booking_id` v1** (column_doc) - f_deep_linear_events.booking_id: booking_id String on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: booking_id, f_deep_linear_events]_
- **`column.f_deep_linear_events.city` v1** (column_doc) - f_deep_linear_events.city: city LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: city, f_deep_linear_events]_
- **`column.f_deep_linear_events.client_lib` v1** (column_doc) - f_deep_linear_events.client_lib: client_lib LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_deep_linear_events]_
- **`column.f_deep_linear_events.destination` v1** (column_doc) - f_deep_linear_events.destination: destination LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: destination, f_deep_linear_events]_
- **`column.f_deep_linear_events.device_type` v1** (column_doc) - f_deep_linear_events.device_type: device_type LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: device_type, f_deep_linear_events]_
- **`column.f_deep_linear_events.document_kind` v1** (column_doc) - f_deep_linear_events.document_kind: document_kind LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: document_kind, f_deep_linear_events]_
- **`column.f_deep_linear_events.document_scan_page_count` v1** (column_doc) - f_deep_linear_events.document_scan_page_count: document_scan_page_count UInt8 on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: document_scan_page_count, f_deep_linear_events]_
- **`column.f_deep_linear_events.document_scan_quality_score` v1** (column_doc) - f_deep_linear_events.document_scan_quality_score: document_scan_quality_score Nullable(Float64) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: document_scan_quality_score, f_deep_linear_events]_
- **`column.f_deep_linear_events.event` v1** (column_doc) - f_deep_linear_events.event: event LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: event, f_deep_linear_events]_
- **`column.f_deep_linear_events.geoip_country_code` v1** (column_doc) - f_deep_linear_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, geoip_country_code]_
- **`column.f_deep_linear_events.id` v1** (column_doc) - f_deep_linear_events.id: id String on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, id]_
- **`column.f_deep_linear_events.insurance_tier` v1** (column_doc) - f_deep_linear_events.insurance_tier: insurance_tier LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, insurance_tier]_
- **`column.f_deep_linear_events.os` v1** (column_doc) - f_deep_linear_events.os: os LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, os]_
- **`column.f_deep_linear_events.payment_amount_minor` v1** (column_doc) - f_deep_linear_events.payment_amount_minor: payment_amount_minor Decimal(18, 4) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, payment_amount_minor]_
- **`column.f_deep_linear_events.payment_card_issuer_country` v1** (column_doc) - f_deep_linear_events.payment_card_issuer_country: payment_card_issuer_country LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, payment_card_issuer_country]_
- **`column.f_deep_linear_events.payment_card_network` v1** (column_doc) - f_deep_linear_events.payment_card_network: payment_card_network LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, payment_card_network]_
- **`column.f_deep_linear_events.payment_method` v1** (column_doc) - f_deep_linear_events.payment_method: payment_method LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, payment_method]_
- **`column.f_deep_linear_events.slot_window` v1** (column_doc) - f_deep_linear_events.slot_window: slot_window LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, slot_window]_
- **`column.f_deep_linear_events.timestamp` v1** (column_doc) - f_deep_linear_events.timestamp: timestamp DateTime64(3) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, timestamp]_
- **`column.f_deep_linear_events.user_id` v1** (column_doc) - f_deep_linear_events.user_id: user_id String on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, user_id]_
- **`column.f_double_fanout_events.app_version` v1** (column_doc) - f_double_fanout_events.app_version: app_version LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: app_version, f_double_fanout_events]_
- **`column.f_double_fanout_events.board_id` v1** (column_doc) - f_double_fanout_events.board_id: board_id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: board_id, f_double_fanout_events]_
- **`column.f_double_fanout_events.city` v1** (column_doc) - f_double_fanout_events.city: city LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: city, f_double_fanout_events]_
- **`column.f_double_fanout_events.client_lib` v1** (column_doc) - f_double_fanout_events.client_lib: client_lib LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_double_fanout_events]_
- **`column.f_double_fanout_events.device_type` v1** (column_doc) - f_double_fanout_events.device_type: device_type LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: device_type, f_double_fanout_events]_
- **`column.f_double_fanout_events.event` v1** (column_doc) - f_double_fanout_events.event: event LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: event, f_double_fanout_events]_
- **`column.f_double_fanout_events.geoip_country_code` v1** (column_doc) - f_double_fanout_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, geoip_country_code]_
- **`column.f_double_fanout_events.id` v1** (column_doc) - f_double_fanout_events.id: id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, id]_
- **`column.f_double_fanout_events.os` v1** (column_doc) - f_double_fanout_events.os: os LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, os]_
- **`column.f_double_fanout_events.reaction` v1** (column_doc) - f_double_fanout_events.reaction: reaction LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, reaction]_
- **`column.f_double_fanout_events.reply_id` v1** (column_doc) - f_double_fanout_events.reply_id: reply_id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, reply_id]_
- **`column.f_double_fanout_events.reply_kind` v1** (column_doc) - f_double_fanout_events.reply_kind: reply_kind LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, reply_kind]_
- **`column.f_double_fanout_events.thread_id` v1** (column_doc) - f_double_fanout_events.thread_id: thread_id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, thread_id]_
- **`column.f_double_fanout_events.timestamp` v1** (column_doc) - f_double_fanout_events.timestamp: timestamp DateTime64(3) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, timestamp]_
- **`column.f_double_fanout_events.topic` v1** (column_doc) - f_double_fanout_events.topic: topic LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, topic]_
- **`column.f_double_fanout_events.user_id` v1** (column_doc) - f_double_fanout_events.user_id: user_id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, user_id]_
- **`column.f_double_fanout_events.visibility` v1** (column_doc) - f_double_fanout_events.visibility: visibility LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, visibility]_
- **`column.f_mutation_heavy_events.app_version` v1** (column_doc) - f_mutation_heavy_events.app_version: app_version LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: app_version, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.basket_id` v1** (column_doc) - f_mutation_heavy_events.basket_id: basket_id String on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: basket_id, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.basket_value_minor` v1** (column_doc) - f_mutation_heavy_events.basket_value_minor: basket_value_minor Decimal(18, 4) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: basket_value_minor, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.city` v1** (column_doc) - f_mutation_heavy_events.city: city LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: city, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.client_lib` v1** (column_doc) - f_mutation_heavy_events.client_lib: client_lib LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.device_type` v1** (column_doc) - f_mutation_heavy_events.device_type: device_type LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: device_type, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.event` v1** (column_doc) - f_mutation_heavy_events.event: event LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: event, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.geoip_country_code` v1** (column_doc) - f_mutation_heavy_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, geoip_country_code]_
- **`column.f_mutation_heavy_events.id` v1** (column_doc) - f_mutation_heavy_events.id: id String on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, id]_
- **`column.f_mutation_heavy_events.item_category` v1** (column_doc) - f_mutation_heavy_events.item_category: item_category LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, item_category]_
- **`column.f_mutation_heavy_events.item_id` v1** (column_doc) - f_mutation_heavy_events.item_id: item_id String on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, item_id]_
- **`column.f_mutation_heavy_events.items_after` v1** (column_doc) - f_mutation_heavy_events.items_after: items_after UInt8 on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, items_after]_
- **`column.f_mutation_heavy_events.os` v1** (column_doc) - f_mutation_heavy_events.os: os LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, os]_
- **`column.f_mutation_heavy_events.position_from` v1** (column_doc) - f_mutation_heavy_events.position_from: position_from UInt8 on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, position_from]_
- **`column.f_mutation_heavy_events.position_to` v1** (column_doc) - f_mutation_heavy_events.position_to: position_to UInt8 on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, position_to]_
- **`column.f_mutation_heavy_events.timestamp` v1** (column_doc) - f_mutation_heavy_events.timestamp: timestamp DateTime64(3) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, timestamp]_
- **`column.f_mutation_heavy_events.user_id` v1** (column_doc) - f_mutation_heavy_events.user_id: user_id String on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, user_id]_
- **`column.f_sparse_envelope_events.app_version` v1** (column_doc) - f_sparse_envelope_events.app_version: app_version LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: app_version, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.assist_reason` v1** (column_doc) - f_sparse_envelope_events.assist_reason: assist_reason LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: assist_reason, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.city` v1** (column_doc) - f_sparse_envelope_events.city: city LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: city, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.client_lib` v1** (column_doc) - f_sparse_envelope_events.client_lib: client_lib LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.close_reason` v1** (column_doc) - f_sparse_envelope_events.close_reason: close_reason LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: close_reason, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.device_type` v1** (column_doc) - f_sparse_envelope_events.device_type: device_type LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: device_type, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.event` v1** (column_doc) - f_sparse_envelope_events.event: event LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: event, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.geoip_country_code` v1** (column_doc) - f_sparse_envelope_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, geoip_country_code]_
- **`column.f_sparse_envelope_events.id` v1** (column_doc) - f_sparse_envelope_events.id: id String on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, id]_
- **`column.f_sparse_envelope_events.kiosk_lane` v1** (column_doc) - f_sparse_envelope_events.kiosk_lane: kiosk_lane LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, kiosk_lane]_
- **`column.f_sparse_envelope_events.os` v1** (column_doc) - f_sparse_envelope_events.os: os LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, os]_
- **`column.f_sparse_envelope_events.scan_duration_ms` v1** (column_doc) - f_sparse_envelope_events.scan_duration_ms: scan_duration_ms UInt32 on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, scan_duration_ms]_
- **`column.f_sparse_envelope_events.scan_kind` v1** (column_doc) - f_sparse_envelope_events.scan_kind: scan_kind LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, scan_kind]_
- **`column.f_sparse_envelope_events.scan_result` v1** (column_doc) - f_sparse_envelope_events.scan_result: scan_result LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, scan_result]_
- **`column.f_sparse_envelope_events.timestamp` v1** (column_doc) - f_sparse_envelope_events.timestamp: timestamp DateTime64(3) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, timestamp]_
- **`column.f_sparse_envelope_events.user_id` v1** (column_doc) - f_sparse_envelope_events.user_id: user_id String on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, user_id]_
- **`column.f_sparse_envelope_events.visit_id` v1** (column_doc) - f_sparse_envelope_events.visit_id: visit_id String on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, visit_id]_
- **`column.mv_deep_linear_auth_latency_daily.auth_count_state` v1** (column_doc) - mv_deep_linear_auth_latency_daily.auth_count_state: auth_count_state AggregateFunction(count) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: auth_count_state, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.card_network` v1** (column_doc) - mv_deep_linear_auth_latency_daily.card_network: card_network LowCardinality(String) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: card_network, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.day` v1** (column_doc) - mv_deep_linear_auth_latency_daily.day: day Date on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: day, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.destination` v1** (column_doc) - mv_deep_linear_auth_latency_daily.destination: destination LowCardinality(String) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: destination, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.device_type` v1** (column_doc) - mv_deep_linear_auth_latency_daily.device_type: device_type LowCardinality(String) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: device_type, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.latency_avg_state` v1** (column_doc) - mv_deep_linear_auth_latency_daily.latency_avg_state: latency_avg_state AggregateFunction(avg, UInt32) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: latency_avg_state, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_funnel_daily.bookings_state` v1** (column_doc) - mv_deep_linear_funnel_daily.bookings_state: bookings_state AggregateFunction(uniq, String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: bookings_state, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.day` v1** (column_doc) - mv_deep_linear_funnel_daily.day: day Date on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.destination` v1** (column_doc) - mv_deep_linear_funnel_daily.destination: destination LowCardinality(String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: destination, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.device_type` v1** (column_doc) - mv_deep_linear_funnel_daily.device_type: device_type LowCardinality(String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: device_type, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.event` v1** (column_doc) - mv_deep_linear_funnel_daily.event: event LowCardinality(String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.events_state` v1** (column_doc) - mv_deep_linear_funnel_daily.events_state: events_state AggregateFunction(count) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.users_state` v1** (column_doc) - mv_deep_linear_funnel_daily.users_state: users_state AggregateFunction(uniq, String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_deep_linear_funnel_daily, users_state]_
- **`column.mv_double_fanout_funnel_daily.app_version` v1** (column_doc) - mv_double_fanout_funnel_daily.app_version: app_version LowCardinality(String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: app_version, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.city` v1** (column_doc) - mv_double_fanout_funnel_daily.city: city LowCardinality(String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: city, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.day` v1** (column_doc) - mv_double_fanout_funnel_daily.day: day Date on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.event` v1** (column_doc) - mv_double_fanout_funnel_daily.event: event LowCardinality(String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.events_state` v1** (column_doc) - mv_double_fanout_funnel_daily.events_state: events_state AggregateFunction(count) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.topic` v1** (column_doc) - mv_double_fanout_funnel_daily.topic: topic LowCardinality(String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_double_fanout_funnel_daily, topic]_
- **`column.mv_double_fanout_funnel_daily.uniq_entities` v1** (column_doc) - mv_double_fanout_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_double_fanout_funnel_daily, uniq_entities]_
- **`column.mv_double_fanout_funnel_daily.uniq_users` v1** (column_doc) - mv_double_fanout_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_double_fanout_funnel_daily, uniq_users]_
- **`column.mv_mutation_heavy_funnel_daily.day` v1** (column_doc) - mv_mutation_heavy_funnel_daily.day: day Date on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.event` v1** (column_doc) - mv_mutation_heavy_funnel_daily.event: event LowCardinality(String) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.events_state` v1** (column_doc) - mv_mutation_heavy_funnel_daily.events_state: events_state AggregateFunction(count) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.item_category` v1** (column_doc) - mv_mutation_heavy_funnel_daily.item_category: item_category LowCardinality(String) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: item_category, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.items_after` v1** (column_doc) - mv_mutation_heavy_funnel_daily.items_after: items_after UInt8 on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: items_after, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.sum_basket_value_minor` v1** (column_doc) - mv_mutation_heavy_funnel_daily.sum_basket_value_minor: sum_basket_value_minor AggregateFunction(sum, Decimal(18, 4)) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_mutation_heavy_funnel_daily, sum_basket_value_minor]_
- **`column.mv_mutation_heavy_funnel_daily.uniq_entities` v1** (column_doc) - mv_mutation_heavy_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_mutation_heavy_funnel_daily, uniq_entities]_
- **`column.mv_mutation_heavy_funnel_daily.uniq_users` v1** (column_doc) - mv_mutation_heavy_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_mutation_heavy_funnel_daily, uniq_users]_
- **`column.mv_sparse_envelope_funnel_daily.app_version` v1** (column_doc) - mv_sparse_envelope_funnel_daily.app_version: app_version LowCardinality(String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: app_version, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.avg_scan_duration_ms` v1** (column_doc) - mv_sparse_envelope_funnel_daily.avg_scan_duration_ms: avg_scan_duration_ms AggregateFunction(avg, UInt32) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: avg_scan_duration_ms, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.city` v1** (column_doc) - mv_sparse_envelope_funnel_daily.city: city LowCardinality(String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: city, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.day` v1** (column_doc) - mv_sparse_envelope_funnel_daily.day: day Date on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.event` v1** (column_doc) - mv_sparse_envelope_funnel_daily.event: event LowCardinality(String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.events_state` v1** (column_doc) - mv_sparse_envelope_funnel_daily.events_state: events_state AggregateFunction(count) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.geoip_country_code` v1** (column_doc) - mv_sparse_envelope_funnel_daily.geoip_country_code: geoip_country_code LowCardinality(String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: geoip_country_code, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.uniq_entities` v1** (column_doc) - mv_sparse_envelope_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_sparse_envelope_funnel_daily, uniq_entities]_
- **`column.mv_sparse_envelope_funnel_daily.uniq_users` v1** (column_doc) - mv_sparse_envelope_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_sparse_envelope_funnel_daily, uniq_users]_
- **`entity.deep_linear.entity_key` v1** (entity) - deep_linear entity key: booking_id: The grain of `atlys.f_deep_linear_events` is `booking_id` (confidence 0.80); secondary keys: user_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.80, refs: booking_id, f_deep_linear_events, user_id]_
- **`gap.data_quality.f_deep_linear_events.user_id_join` v1** (gap) - data_quality: f_deep_linear_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_deep_linear_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_deep_linear_events, search_typed, user_id]_
- **`gap.data_quality.f_double_fanout_events.user_id_join` v1** (gap) - data_quality: f_double_fanout_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 10.1% of `f_double_fanout_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_double_fanout_events, search_typed, user_id]_
- **`gap.data_quality.f_mutation_heavy_events.user_id_join` v1** (gap) - data_quality: f_mutation_heavy_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_mutation_heavy_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_mutation_heavy_events, search_typed, user_id]_
- **`gap.data_quality.f_sparse_envelope_events.user_id_join` v1** (gap) - data_quality: f_sparse_envelope_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 38.1% of `f_sparse_envelope_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_sparse_envelope_events, search_typed, user_id]_
- **`relationship.f_deep_linear_events.segment_join` v1** (relationship) - f_deep_linear_events -> existing tables (segment-level only): `f_deep_linear_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (2 shared values), `city` (4 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_deep_linear_events]_
- **`relationship.f_double_fanout_events.segment_join` v1** (relationship) - f_double_fanout_events -> existing tables (segment-level only): `f_double_fanout_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (2 shared values), `city` (4 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_double_fanout_events]_
- **`relationship.f_mutation_heavy_events.segment_join` v1** (relationship) - f_mutation_heavy_events -> existing tables (segment-level only): `f_mutation_heavy_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (2 shared values), `city` (4 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_mutation_heavy_events]_
- **`relationship.f_sparse_envelope_events.segment_join` v1** (relationship) - f_sparse_envelope_events -> existing tables (segment-level only): `f_sparse_envelope_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (2 shared values), `city` (4 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, destination_card_clicked, f_sparse_envelope_events]_
- **`table.agg_deep_linear_auth_latency_daily` v1** (table_doc) - agg_deep_linear_auth_latency_daily: Auto-documented from the live schema: 6 columns; 15 rows at first observation. Columns: day, device_type, destination, card_network, latency_avg_state, auth_count_state. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily]_
- **`table.agg_deep_linear_funnel_daily` v1** (table_doc) - agg_deep_linear_funnel_daily: Auto-documented from the live schema: 7 columns; 120 rows at first observation. Columns: day, event, device_type, destination, events_state, bookings_state, users_state. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily]_
- **`table.agg_double_fanout_funnel_daily` v1** (table_doc) - agg_double_fanout_funnel_daily: Auto-documented from the live schema: 8 columns; 204 rows at first observation. Columns: day, event, topic, city, app_version, events_state, uniq_entities, uniq_users. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily]_
- **`table.agg_mutation_heavy_funnel_daily` v1** (table_doc) - agg_mutation_heavy_funnel_daily: Auto-documented from the live schema: 8 columns; 146 rows at first observation. Columns: day, event, items_after, item_category, events_state, uniq_entities, uniq_users, sum_basket_value_minor. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily]_
- **`table.agg_sparse_envelope_funnel_daily` v1** (table_doc) - agg_sparse_envelope_funnel_daily: Auto-documented from the live schema: 9 columns; 75 rows at first observation. Columns: day, event, city, geoip_country_code, app_version, events_state, uniq_entities, uniq_users, avg_scan_duration_ms. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily]_
- **`table.f_deep_linear_events` v1** (table_doc) - f_deep_linear_events: Auto-documented from the live schema: 22 columns; 3,165 rows at first observation; ORDER BY (event, timestamp, booking_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: Never lead with `id` (3165 distinct, useless for pruning) or `booking_id` alone (560 distinct but only meaningful once event is fixed). ORDER BY (event, timestamp, booking_id): event has only 8 values and every PM question ('step-through rate', 'largest drop', 'does network predict auth success') filters or groups by event first, so it prunes hard; timestamp is second because all questions are time-windowed (the observed window is a single day, but production queries run over months); booking_id last co-locates each booking's 8-step sequence within an event+time slice, which is what windowFunnel-style step analysis over the funnel needs.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, booking_id) read 139,552 B / 3,167 rows; straw-man ORDER BY (timestamp, booking_id) read 139,552 B / 3,167 rows. At sample volume (3,167 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: id, event, timestamp, booking_id, user_id, app_version, client_lib, device_type, os, city, geoip_country_code, destination, slot_window, document_kind, document_scan_quality_score, document_scan_page_count, insurance_tier, payment_method, payment_card_network, payment_card_issuer_country, payment_amount_minor, auth_latency_ms. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events]_
- **`table.f_double_fanout_events` v1** (table_doc) - f_double_fanout_events: Auto-documented from the live schema: 17 columns; 2,575 rows at first observation. Columns: app_version, board_id, city, client_lib, device_type, event, geoip_country_code, id, os, reaction, reply_id, reply_kind, thread_id, timestamp, topic, user_id, visibility. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events]_
- **`table.f_mutation_heavy_events` v1** (table_doc) - f_mutation_heavy_events: Auto-documented from the live schema: 17 columns; 3,720 rows at first observation. Columns: app_version, basket_id, basket_value_minor, city, client_lib, device_type, event, geoip_country_code, id, item_category, item_id, items_after, os, position_from, position_to, timestamp, user_id. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events]_
- **`table.f_sparse_envelope_events` v1** (table_doc) - f_sparse_envelope_events: Auto-documented from the live schema: 17 columns; 2,110 rows at first observation. Columns: app_version, assist_reason, city, client_lib, close_reason, device_type, event, geoip_country_code, id, kiosk_lane, os, scan_duration_ms, scan_kind, scan_result, timestamp, user_id, visit_id. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events]_
- **`table.mv_deep_linear_auth_latency_daily` v1** (table_doc) - mv_deep_linear_auth_latency_daily: Auto-documented from the live schema: 6 columns. Columns: day, device_type, destination, card_network, latency_avg_state, auth_count_state. _[source: context_agent, confidence 1.00, refs: mv_deep_linear_auth_latency_daily]_
- **`table.mv_deep_linear_funnel_daily` v1** (table_doc) - mv_deep_linear_funnel_daily: Auto-documented from the live schema: 7 columns. Columns: day, event, device_type, destination, events_state, bookings_state, users_state. _[source: context_agent, confidence 1.00, refs: mv_deep_linear_funnel_daily]_
- **`table.mv_double_fanout_funnel_daily` v1** (table_doc) - mv_double_fanout_funnel_daily: Auto-documented from the live schema: 8 columns. Columns: day, event, topic, city, app_version, events_state, uniq_entities, uniq_users. _[source: context_agent, confidence 1.00, refs: mv_double_fanout_funnel_daily]_
- **`table.mv_mutation_heavy_funnel_daily` v1** (table_doc) - mv_mutation_heavy_funnel_daily: Auto-documented from the live schema: 8 columns. Columns: day, event, items_after, item_category, events_state, uniq_entities, uniq_users, sum_basket_value_minor. _[source: context_agent, confidence 1.00, refs: mv_mutation_heavy_funnel_daily]_
- **`table.mv_sparse_envelope_funnel_daily` v1** (table_doc) - mv_sparse_envelope_funnel_daily: Auto-documented from the live schema: 9 columns. Columns: day, event, city, geoip_country_code, app_version, events_state, uniq_entities, uniq_users, avg_scan_duration_ms. _[source: context_agent, confidence 1.00, refs: mv_sparse_envelope_funnel_daily]_

### Updated

_nothing updated_

### Superseded

_nothing superseded_

### Contradictions found

#### [HIGH] 'conversion (note)' and 'Conversion rate' divide by different populations

- **Kind:** `definition_conflict` (detected by rule)
- **The context claims:** The context defines the same metric subject ['conversion'] twice. [a] metric.conversion@v1 'conversion (note)': numerator='`purchase_completed` users' -> table `purchase_completed`; denominator='users who started an application (`application_started`)' -> table `application_started` | [b] metric.conversion_rate@v2 'Conversion rate': numerator='completed purchases' -> table `purchase_completed` (matched 2 word(s) in the phrase); denominator='**sessions**' -> proxy: column `app_session_id` on `destination_card_clicked` (no table is named for 'session')
- **The data says:** The two definitions have different denominators, so they cannot both be the number reported as this metric. Executed: definition [a] = 0.045546, definition [b] = 0.007065 (0.16x apart) over the same window.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion`, `metric.conversion_rate`
- **Proposed resolution:** Pick one denominator and version it. Recommended: keep both but rename -- 'conversion (note)' (denominator: 'users who started an application (`application_started`)') and 'Conversion rate' (denominator: '**sessions**') -- so every report states which it used via Finding.metric_definition_used.

Verification SQL:

```sql
SELECT
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.purchase_completed) AS num_a,
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.application_started) AS den_a,
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.purchase_completed) AS num_b,
  (SELECT uniqIf(ifNull(app_session_id, ''), ifNull(app_session_id, '') != '') FROM atlys.destination_card_clicked) AS den_b,
  round(num_a / den_a, 6) AS rate_a,
  round(num_b / den_b, 6) AS rate_b,
  round(rate_b / rate_a, 2) AS ratio_b_over_a
```

Result: `[{"num_a": 7054, "den_a": 154877, "num_b": 7054, "den_b": 998469, "rate_a": 0.045546, "rate_b": 0.007065, "ratio_b_over_a": 0.16}]`

#### [HIGH] `f_deep_linear_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_deep_linear_events` has 3165 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 340 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 2), ('city', 4), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_deep_linear_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=2, city=4, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_deep_linear_events
```

Result: `[{"new_rows": 3165, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 340, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_double_fanout_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_double_fanout_events` has 2575 rows, of which 260 (10.1%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1251 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 2), ('city', 4), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_double_fanout_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=2, city=4, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_double_fanout_events
```

Result: `[{"new_rows": 2575, "anonymous_rows": 260, "anonymous_frac": 0.101, "distinct_identities": 1251, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_mutation_heavy_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_mutation_heavy_events` has 3720 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 420 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 2), ('city', 4), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_mutation_heavy_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=2, city=4, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_mutation_heavy_events
```

Result: `[{"new_rows": 3720, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 420, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_sparse_envelope_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_sparse_envelope_events` has 2110 rows, of which 803 (38.1%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 372 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 2), ('city', 4)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_sparse_envelope_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=2, city=4

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_sparse_envelope_events
```

Result: `[{"new_rows": 2110, "anonymous_rows": 803, "anonymous_frac": 0.3806, "distinct_identities": 372, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `visa_issuance_eta_days` is documented on application_started but does not exist

- **Kind:** `schema_mismatch` (detected by rule)
- **The context claims:** [entity.application@v1] 'Application' references column `visa_issuance_eta_days` on application_started.
- **The data says:** system.columns returns 0 rows for that column in scope and 0 anywhere in `atlys`. Nearest actual column(s): application_started.eta_shown Nullable(String). The context also declares it as 'integer' (Int...), but the nearest real column is Nullable(String) -- different NAME and different TYPE.
- **Verified against the database:** **yes**
- **Entries affected:** `entity.application`, `metric.on_time_delivery_rate`
- **Proposed resolution:** Rewrite the entry to use `application_started.eta_shown` (Nullable(String)) if that is the intended field, and note the type difference; otherwise mark the field as not instrumented.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND table IN ('application_started') AND name = 'visa_issuance_eta_days') AS claimed_column_exists,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS claimed_column_anywhere,
  (SELECT arrayStringConcat(arraySort(groupArray(concat(table, '.', name, ' ', type))), ' | ') FROM system.columns WHERE database = 'atlys' AND ((table = 'application_started' AND name = 'eta_shown'))) AS nearest_actual_columns
```

Result: `[{"claimed_column_exists": 0, "claimed_column_anywhere": 0, "nearest_actual_columns": "application_started.eta_shown Nullable(String)"}]`

#### [HIGH] 'Conversion rate' is not computable as defined

- **Kind:** `uncomputable_metric` (detected by rule)
- **The context claims:** [metric.conversion_rate@v2] 'Conversion rate' = completed purchases ÷ **sessions**. Its DENOMINATOR is 'sessions'.
- **The data says:** 'sessions' resolves to nothing in the schema: 0 tables and 0 exactly-named columns. Only app_session_id exists, and a column cannot be counted as an occurrence without a start/end event. The headline number therefore cannot be reproduced from these tables as written.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion_rate`
- **Proposed resolution:** Report this metric against a denominator that exists, and state the substitution in every finding. Until then it is excluded from ContextStore.metric_catalog().

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%session%') AS tables_matching_term,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'session') AS exact_column_named_term,
  (SELECT arrayStringConcat(arraySort(groupUniqArray(name)), ', ') FROM system.columns WHERE database = 'atlys' AND name ILIKE '%session%') AS columns_containing_term
```

Result: `[{"tables_matching_term": 0, "exact_column_named_term": 0, "columns_containing_term": "app_session_id"}]`

#### [MEDIUM] Documented ORDER BY leads with `id`, a near-unique key that prunes nothing

- **Kind:** `stale_entry` (detected by rule)
- **The context claims:** [table_doc.instrumentation_note@v1] 'Instrumentation note' documents ORDER BY (id, timestamp, user_id) and simultaneously admits: "...first** (`ORDER BY (id, timestamp, user_id)`) — a legacy of the event-table template. Queries filter by time/segment..."
- **The data says:** On `destination_card_clicked`, the declared sorting key is 'id, timestamp, user_id' and the lead key `id` has selectivity 1.0 over 1000000 rows (1000000 distinct values) -- 1.0 distinct values per row -- effectively a unique key. Every granule therefore holds a distinct value, so the primary index prunes nothing for the time/segment filters the entry says queries actually use. The entry documents a design it already calls obsolete. (This check reports on measured cardinality, not on the lead column's position or name: a lead key under 0.5 selectivity and under 10000 distinct values is a genuine discriminator and is NOT reported.)
- **Verified against the database:** **yes**
- **Entries affected:** `table_doc.instrumentation_note`
- **Proposed resolution:** New tables must NOT copy this. Lead ORDER BY with a low-cardinality column the queries filter on, then `timestamp`, then the entity key -- and record the contrast in DDLProposal.rationale['order_by'].

Verification SQL:

```sql
SELECT
  'destination_card_clicked' AS table_checked,
  (SELECT sorting_key FROM system.tables WHERE database = 'atlys' AND name = 'destination_card_clicked') AS declared_sorting_key,
  count() AS rows,
  uniqExact(id) AS distinct_values_of_lead_key,
  round(uniqExact(id) / count(), 4) AS lead_key_selectivity
FROM atlys.destination_card_clicked
```

Result: `[{"table_checked": "destination_card_clicked", "declared_sorting_key": "id, timestamp, user_id", "rows": 1000000, "distinct_values_of_lead_key": 1000000, "lead_key_selectivity": 1.0}]`

#### [MEDIUM] 'On-time delivery rate' is documented as a metric but cannot be computed here

- **Kind:** `uncomputable_metric` (detected by rule)
- **The context claims:** [metric.on_time_delivery_rate@v2] 'On-time delivery rate' = applications issued on or before `visa_issuance_eta_days` ÷ applications issued. The entry itself admits: "... or before `visa_issuance_eta_days` ÷ applications issued. (Reported by the fulfilment team from post-purchase systems; not computable from the funnel tables here.)..."
- **The data says:** Confirmed against the live schema: required column(s) ['visa_issuance_eta_days'] are absent and no table matches ['issued', 'visa_issuance_eta_day']. Executed result: [{"required_column_visa_issuance_eta_days_present": 0, "source_tables_like_issued": 0, "source_tables_like_visa_issuance_eta_day": 0}]
- **Verified against the database:** **yes**
- **Entries affected:** `metric.on_time_delivery_rate`
- **Proposed resolution:** Mark the metric disputed and exclude it from the analytics metric catalog (ContextStore.metric_catalog()) so no agent reports a number for it. Re-admit it only when a post-purchase source table lands in this database.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS required_column_visa_issuance_eta_days_present,
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%issued%') AS source_tables_like_issued,
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%visa_issuance_eta_day%') AS source_tables_like_visa_issuance_eta_day
```

Result: `[{"required_column_visa_issuance_eta_days_present": 0, "source_tables_like_issued": 0, "source_tables_like_visa_issuance_eta_day": 0}]`

#### [MEDIUM] 'sessions' is used in a metric definition but never defined

- **Kind:** `undefined_term` (detected by rule)
- **The context claims:** [metric.conversion_rate@v2] 'Conversion rate' is defined in terms of 'sessions', but no entity/glossary entry defines 'sessions'.
- **The data says:** No table is named for it (0 matches) and no column is named 'session' (0 matches). The closest thing in the schema is: app_session_id -- a column, not an event stream, so there is no boundary event that would let us count 'sessions'.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion_rate`
- **Proposed resolution:** Either add an entity entry defining 'sessions' operationally (e.g. as a gap between events on app_session_id), or restate the metric in terms that exist in the schema.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%session%') AS tables_matching_term,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'session') AS exact_column_named_term,
  (SELECT arrayStringConcat(arraySort(groupUniqArray(name)), ', ') FROM system.columns WHERE database = 'atlys' AND name ILIKE '%session%') AS columns_containing_term
```

Result: `[{"tables_matching_term": 0, "exact_column_named_term": 0, "columns_containing_term": "app_session_id"}]`

### Gaps (context the layer does not yet cover)

- join_assumption_violated: `f_deep_linear_events` cannot be joined to the existing tables on `user_id`
- join_assumption_violated: `f_double_fanout_events` cannot be joined to the existing tables on `user_id`
- join_assumption_violated: `f_mutation_heavy_events` cannot be joined to the existing tables on `user_id`
- join_assumption_violated: `f_sparse_envelope_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined
