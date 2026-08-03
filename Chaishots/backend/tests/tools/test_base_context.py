from app.schemas.agents import ContextAgentOutput, MetricDefinition
from app.tools.base_context import load_base_context, parse_base_context
from app.tools.context_store import merge_context

_MARKDOWN = """# Base Context

> Treat it as the starting point, not gospel.

## 2. Entity definitions

**User** — a traveller. Identified by `user_id`, present on every event.

**Application** — one visa application, identified by `application_id`.

## 3. The eight raw event tables

| Table | Kind | Emitted when | Key event-specific columns |
|-------|------|--------------|----------------------------|
| `application_started` | funnel | user starts an application | `purpose`, `destination` |
| `purchase_completed` | funnel | payment succeeds | `value`, `currency` |
| `search_typed` | supporting | user types a search | `search_term` |

## 4. Metric definitions

**Conversion rate** = completed purchases ÷ **sessions**. This is the headline number.

**Step-through rate** = users at stage N+1 ÷ users at stage N.

> Note on funnel conversion: we treat **conversion as `purchase_completed` users ÷
> users who started an application**. This is the denominator used in dashboards.

## 5. Known-issues log

1. **K1 — iOS WebKit OTP autofill regression.** On recent iOS builds the payment OTP
   field fails to autofill.
2. **K2 — Passport scan model update.** The on-device model was updated in April.

## 6. Entity relationships (join map)

- `application_started.application_id` → `purchase_completed`,
  `search_typed` (on `application_id`)

## 7. How to analyse the funnel

- Push aggregation into ClickHouse; interpret the aggregates.
"""


def test_parses_entities_metrics_issues_and_joins() -> None:
    document = parse_base_context(_MARKDOWN)

    assert document.version == 1
    assert document.source == "base_context.md"

    entity_names = {str(entity["name"]) for entity in document.entities}
    assert {"User", "Application"} <= entity_names
    # Table inventory rows become entities too, so the join map can resolve.
    assert {"application_started", "purchase_completed"} <= entity_names

    metric_names = {str(metric["name"]) for metric in document.metrics}
    assert {"Conversion rate", "Step-through rate"} <= metric_names

    assert [issue["key"] for issue in document.known_issues] == ["K1", "K2"]
    assert "iOS WebKit OTP autofill" in str(document.known_issues[0]["title"])


def test_join_map_expands_to_every_named_target() -> None:
    document = parse_base_context(_MARKDOWN)
    pairs = {
        (str(r["source_table"]), str(r["target_table"]), str(r["target_column"]))
        for r in document.relationships
    }
    assert (
        "application_started",
        "purchase_completed",
        "application_id",
    ) in pairs
    assert ("application_started", "search_typed", "application_id") in pairs


def test_document_self_contradiction_is_recorded_as_a_conflict() -> None:
    """The base layer defines conversion two ways; that must survive as a conflict."""

    document = parse_base_context(_MARKDOWN)
    assert document.conflicts
    joined = " ".join(str(conflict) for conflict in document.conflicts)
    assert "UNVERIFIED" in joined
    assert "purchase_completed" in joined
    # The file's opening blockquote describes the document, not the data.
    assert "starting point, not gospel" not in joined


def test_known_issues_survive_a_context_merge() -> None:
    base = parse_base_context(_MARKDOWN)
    merged = merge_context(
        base,
        ContextAgentOutput(
            metrics_added=[
                MetricDefinition(
                    name="express adoption",
                    description="d",
                    numerator="n",
                    denominator="d",
                )
            ]
        ),
        version=2,
        run_id="11111111-1111-1111-1111-111111111111",
    )
    assert [issue["key"] for issue in merged.known_issues] == ["K1", "K2"]
    assert len(merged.metrics) == len(base.metrics) + 1
    assert merged.conflicts == base.conflicts


def test_vendored_base_context_parses() -> None:
    """The real shipped document must parse, not just the fixture."""

    document = load_base_context()
    assert document is not None
    assert len(document.known_issues) == 7
    assert len(document.entities) >= 13
    assert len(document.relationships) >= 10
