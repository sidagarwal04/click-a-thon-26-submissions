# Langfuse trace evidence

Traces from graded investigation runs, captured against the Sentinel Langfuse
project (`cmsb6gra113rdad0jko2lye0y`).

1. https://us.cloud.langfuse.com/project/cmsb6gra113rdad0jko2lye0y/traces/b1087c3e55bdf2bc7336ad2f6cc7a694?observation=5cee89bb7ad42887&timestamp=2026-08-02T04:28:55.508Z&traceId=b1087c3e55bdf2bc7336ad2f6cc7a694
2. https://us.cloud.langfuse.com/project/cmsb6gra113rdad0jko2lye0y/traces/2740d86063eea9306607ac45f858e7fb?observation=339b840c3286bc18&timestamp=2026-08-02T04:30:07.558Z&traceId=2740d86063eea9306607ac45f858e7fb

Both links are public share links — no Langfuse account required to view.

`trace-2740d86-public.png` — screenshot of trace #2's investigation graph
(Sentinel Chat Orchestrator → Root-Cause Analyst delegate → ClickHouse
evidence tool calls), confirming the "Public" badge and showing the
resulting diagnosis (segment attribution to `geo_device_id`, with the
underlying eCPM/z-score figures cited from `inmobi.incidents` /
`inmobi.anomalies`).
