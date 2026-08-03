# Team Name
Team Clicktick

## Track
SonyLIV

## Project
ott-o11y

## Team Members
- Vikash Kumar (https://github.com/vikashkumar2020)
- Muni Siva (https://github.com/muni91)

## What it does
We built a real-time streaming concurrency analytics platform on ClickHouse that accurately computes foreground-only concurrent viewers at scale. The solution ingests session and heartbeat datasets into ClickHouse and uses a series of Materialized Views to incrementally build optimized serving tables for concurrency, peak concurrency, average concurrency, and dimension-based filtering (platform, country, content, video type, and time grain). This eliminates expensive scans of raw session history while supporting continuously evolving sessions. On top of the analytics layer, we integrated LibreChat with the ClickHouse MCP server, enabling users to query concurrency metrics and insights using natural language through a conversational interface.

## Hosted Demo
Dashboard - https://scarletcorn757.grafana.net/public-dashboards/ec4dd23ed92948348c9586e491226971
Librechat with clicktick bot - https://guiding-monster-publicly.ngrok-free.app/c/new?endpoint=ollama&model=gpt-oss&projectId=6a6e2bdbed5b4a34774a88cf
username: kvvik2020@gmail.com
password: clicktick

## Pitch Deck
[Clicktick_Pitch_Deck.pptx](https://github.com/ClickHouse/click-a-thon-26-submissions/blob/main/team-clicktick/Clicktick_Pitch_Deck.pptx)

## Demo Video
(https://www.loom.com/share/596a893ccadb4921b10de35832cddcc6)

## Architecture

Our solution is built around **ClickHouse as the primary analytical engine**, using a layered architecture that separates ingestion, aggregation, serving, and conversational analytics.

```text
                 +-----------------------+
                 |   Session Dataset     |
                 +-----------------------+
                            |
                 +-----------------------+
                 | Heartbeat/Event Data  |
                 +-----------------------+
                            |
                            ▼
               +-------------------------+
               |    ClickHouse Raw Tables |
               +-------------------------+
                            |
                            ▼
          +--------------------------------------+
          | Materialized View Pipeline           |
          |--------------------------------------|
          | • Active Interval Generation         |
          | • Foreground-only Filtering          |
          | • Minute Delta Computation (+1/-1)  |
          | • Concurrency Aggregation           |
          | • Peak & Average Aggregation        |
          +--------------------------------------+
                            |
                            ▼
             +-------------------------------+
             | Optimized Serving Tables      |
             | (Pre-aggregated Analytics)    |
             +-------------------------------+
                  |                      |
                  |                      |
                  ▼                      ▼
      Dashboard / SQL Queries     LibreChat + MCP
                                        |
                                        ▼
                           Natural Language Analytics
```

### Components

* **Raw Tables:** Store session and heartbeat/playback events.
* **Materialized Views:** Incrementally process incoming events to generate active intervals and precompute concurrency, peak, and average metrics.
* **Serving Tables:** Optimized for low-latency queries with filters on platform, country, content, video type, and time grain.
* **LibreChat + ClickHouse MCP:** Provides a conversational interface, allowing users to retrieve concurrency insights using natural language while the MCP server translates requests into ClickHouse SQL.


## How we built it
We designed the system around ClickHouse as the primary analytical engine, ensuring that both ingestion and concurrency computation happen entirely within ClickHouse.

### Data Ingestion
Loaded the synthetic session dataset and heartbeat/playback events dataset into ClickHouse.
The ingestion pipeline supports continuous inserts so that new sessions and heartbeats are reflected without rebuilding historical data.

### Data Modeling
Created optimized MergeTree tables for raw session and heartbeat data.
Defined active playback intervals by combining session boundaries with heartbeat and playback-state events, excluding paused, backgrounded, and inactive periods.

### Materialized View Pipeline
Built a chain of Materialized Views (MVs) that incrementally transform raw events into serving tables.
The MVs:
- derive active viewing intervals,
- generate interval deltas (+1/-1),
- aggregate minute-level concurrency,
- maintain precomputed peak and average concurrency,
- preserve common business dimensions such as platform, country, content, and video type for fast filtering.

### Serving Layer
Dashboards and applications query the aggregated serving tables instead of scanning raw session history.
This provides low-latency responses for:
- current concurrency,
- minute-wise concurrency,
- peak concurrency,
- average concurrency,
- filtered analytics across multiple dimensions.

### Handling Live Sessions
As new heartbeats arrive, the Materialized Views update the aggregated tables automatically.
Open sessions continue extending their active intervals incrementally, eliminating the need for expensive recomputation.

### Conversational Analytics
Integrated LibreChat with the ClickHouse MCP Server.

The MCP server translates these requests into ClickHouse queries and returns the results through the chat interface.

## How to run it
- grafana is hosted over cloud, so no setup is required.
- Configure ClickHouse by updating with your ClickHouse Cloud credentials.
- Load the datasets (sessions and heartbeats) into the raw ClickHouse tables.
- Create the Materialized Views to build the serving layer for active intervals, concurrency,   peak concurrency, and average concurrency.
- Start LibreChat and the ClickHouse MCP server using Docker Compose.
- Access LibreChat and query the data using natural language, or run SQL queries directly on the serving tables for real-time concurrency analytics.