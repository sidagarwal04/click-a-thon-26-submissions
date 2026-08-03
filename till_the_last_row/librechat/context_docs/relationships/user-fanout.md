---
type: relationship
title: User fanout
description: User_id joins all event tables.
timestamp: 2026-08-01
tags: [relationship, join]
---

# Join

`destination_card_clicked.user_id` → all tables (`user_id`)

All eight event tables join on `user_id`.

# Order

By `timestamp` ascending within a `user_id`.

# Source

`base_context.md` §6.
