---
type: entity
title: Destination
description: Target country for visa application, identified by ISO-2 code.
timestamp: 2026-08-01
tags: [entity, destination]
---

# Definition

The target country, ISO-2 code in `destination`. Each destination belongs to a region (GCC, SEA, Schengen, Americas, …) with its own visa types.

# Key fields

| field | meaning |
|---|---|
| destination | ISO-2 country code |
| region | GCC, SEA, Schengen, Americas, etc. |

# Related

- Tables: [destination_card_clicked](/tables/destination_card_clicked.md)
