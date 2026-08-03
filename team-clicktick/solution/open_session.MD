**How we keep “open” sessions up‑to‑date**

| Step | What happens when a new heartbeat arrives | Where the change ends up in the data model |
|------|-------------------------------------------|------------------------------------------|
| 1️⃣ **Heartbeat received** | The ingestion worker notes `last_seen_ts` = timestamp of this beat. | A lightweight *open‑session* record (`interval_start`, `last_seen_ts`) is refreshed in a small, always‑running table (`open_session_intervals`). |
| 2️⃣ **Check the timeout** | Compute `<last_seen_ts> + heartbeat_timeout`. If the current wall‑clock time is still inside that window, the session is *still active*; nothing else changes. | The row stays alive in `open_session_intervals` with an updated `last_seen_ts`. |
| 3️⃣ **Heartbeat stops** (or timeout expires) | As soon as the timeout passes, the system treats the last heartbeat as the final activity point and creates a *closed interval* (`interval_start → last_seen_ts + heartbeat_timeout`). | A new row is appended to `session_active_intervals_clean`. The original open record may be deleted or flagged `is_open = 0` depending on how you design the lifecycle. |
| 4️⃣ **Live view of active ranges** | Clients that need a real‑time list of in‑flight viewers query the *open* table or use `session_active_intervals_clean` merged with the open rows (see “live session list” technique). | The union can be performed on‑the‐fly or by materializing a “peeking” view `active_sessions_current`. |
| 5️⃣ **Periodical purge** | After a configurable retention period (e.g., 30 days) we archive or delete the old intervals from `session_active_intervals_clean` to keep storage lean. | Purge job runs nightly; it does not touch open rows because they still need to be kept until they close. |

---

### Why this architecture works for growing ranges

- **No “resizing” of existing rows** – We never modify a row that’s already in `session_active_intervals_clean`.  Once a session is closed, its final boundaries are permanent; subsequent heartbeats no longer touch it.
- **Open sessions evolve via a tiny update each heartbeat** – The open‑interval table holds only the latest `last_seen_ts`; updating a single column is inexpensive even at millions of concurrent users.
- **Timeout logic lives in the ingestion layer** – By making the timeout a configuration (`concurrency_config.heartbeat_timeout_s`), we can change behaviour without altering any SQL schema or queries.  
- **No heavy window functions during runtime** – The system doesn’t have to scan billions of intervals to figure out who’s still live; it reads one small row per session.