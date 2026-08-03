# Incoming features

The baseline Atlys tables are already loaded in ClickHouse and are not bootstrapped
by this application. This directory is only for new feature inputs processed by the
shared pipeline.

Each feature must be a single, safely named directory containing exactly the two
required inputs:

```text
incoming_features/
└── 01_express_checkout/
    ├── spec.md
    └── events.ndjson
```

`events.ndjson` is streamed and profiled by Python. Raw event rows are not returned
through the REST API or MCP tools and are not placed in an LLM prompt.
