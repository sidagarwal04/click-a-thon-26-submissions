---
type: entity
title: Event
description: One row in one of the eight raw event tables.
timestamp: 2026-08-01
tags: [entity, event]
---

# Definition

One row in one of the eight raw event tables. Every event shares the common envelope (device, os, geo, app version, session, timestamps) plus event-specific columns.

# Common envelope fields

- device_type
- os
- geoip_country_code
- app_version
- session_id
- timestamp
- user_id
- application_id (may be empty for pre-application events)

# Grain

Events are the grain of all analysis.

# Related

- Tables: all eight event tables
