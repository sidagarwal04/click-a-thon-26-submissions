# Three Eyed Raven

# Counting the Crowd

## Team Members

- https://github.com/threeeyedraven2026

---

## Project

Counting the Crowd is a real-time session analytics platform built for SonyLIV-style streaming workloads. It ingests millions of playback events into ClickHouse and delivers real-time insights through dashboards and AI-powered analytics.

---

## What it does

- Tracks concurrent viewers in real time
- Reconstructs complete playback session timelines
- Provides live operational dashboards
- Enables natural language analytics using LibreChat
- Uses Materialized Views for instant aggregations
- Analyzes playback behavior, buffering, quality changes, and viewer engagement

---

## Hosted Demo

> https://www.youtube.com/watch?v=HkScOPeBGyo

---

## Demo Video

> https://www.youtube.com/watch?v=HkScOPeBGyo

---

## Architecture


Viewer events (Play, Pause, Stop) are captured in real time.
Raw events are stored unchanged in the Bronze layer.
Bronze preserves every event for auditing and replay.
Materialized Views transform raw events automatically.
The Silver layer cleans and enriches viewer activity.
Events are consolidated into minute-level viewing sessions.
Session state is maintained with platform and content metadata.
The Gold layer aggregates business-ready metrics.
Metrics are available at minute, hour, day, and month granularity.
Dashboards and AI assistants query only the Gold layer for instant insights.

---

## How We Built It
 
Simulated millions of OTT streaming events.
Ingested events into ClickHouse in real time.
Stored incoming events in Bronze tables.
Used Materialized Views for automatic data transformation.
Built Silver tables to reconstruct viewer sessions.
Generated minute-level active session records.
Aggregated data into Gold rollups (minute → hour → day → month).
Optimized queries using partitions, primary indexes, and pre-aggregations.
Exposed metrics through ClickStack dashboards.
Integrated LibreChat with ClickHouse MCP for natural language analytics.

### Database

- ClickHouse Cloud
- MergeTree tables
- Partitioning
- ORDER BY optimization
- Compression
- Materialized Views
- Cascading Materialized Views
- Secondary Indexes  
- 

### AI

- LibreChat
- ClickStack
- ClickHouse MCP
- ClickHouse Assistant

### Dataset

Synthetic SonyLIV playback events including:

- Play
- Pause
- Resume
- Seek
- Buffer
- Quality Change
- Session Start
- Session End
- Device Information
- User Information
- Content Metadata

---

## Tech Stack

- ClickHouse Cloud
- ClickStack
- LibreChat


---

## How to Run It
https://github.com/sidagarwal04/click-a-thon-26-submissions/pull/55
Clone all the scripts from the repo and run them against any ClickHouse database. 
Refer to the attached ClickHouse data pipeline architecture diagram to understand how the dashboards work. 
Both dashboards are also included in the repo.