"""
Instrumentation Agent
Turns feature specs into production-ready ClickHouse schemas.
Uses ContextAgent for base context, meta_context_registry for existing table metadata,
and OpenRouter/Anthropic LLM for intelligent schema generation. Integrates with
ContextAgent to auto-document new tables in the business-context document when new
schemas are created.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import json
import re
import clickhouse_connect

from agents.tracing.agent import get_tracer


@dataclass
class ColumnSpec:
    """Column specification for a ClickHouse table."""
    name: str
    type: str
    description: str = ""
    nullable: bool = False
    low_cardinality: bool = False
    codec: str = ""
    
    def valid_codec(self) -> bool:
        """LLM-generated `codec` values are sometimes garbage -- e.g. it puts a
        column TYPE ("String") in the codec field instead of leaving it blank.
        to_ddl() would then emit CODEC(String), which ClickHouse rejects outright
        (SYNTAX_ERROR), failing the whole CREATE TABLE. Whitelist real ClickHouse
        codec names (composable, e.g. "Delta, ZSTD(3)") before emitting CODEC(...)."""
        if not self.codec:
            return False
        name = r"(NONE|LZ4|LZ4HC(\(\d+\))?|ZSTD(\(\d+\))?|ZSTD_QAT(\(\d+\))?|DEFLATE_QPL|" \
               r"Delta(\(\d+\))?|DoubleDelta|Gorilla|FPC(\(\d+\))?|T64|GCD|" \
               r"AES_128_GCM_SIV|AES_256_GCM_SIV)"
        pattern = rf"^\s*{name}(\s*,\s*{name})*\s*$"
        return bool(re.match(pattern, self.codec, re.IGNORECASE))

    def to_ch_type(self) -> str:
        """Convert to ClickHouse type string."""
        ch_type = self.type.strip()

        # LLM sometimes emits e.g. "Decimal64(10, 2)" -- DecimalN (N in
        # 32/64/128/256) takes exactly ONE argument (scale; precision is
        # implied by the bit width), so two arguments is a ClickHouse syntax
        # error (NUMBER_OF_ARGUMENTS_DOESNT_MATCH). The generic Decimal(precision,
        # scale) form takes exactly two and resolves to the right width itself,
        # so normalize to that instead of guessing which argument to drop.
        ch_type = re.sub(r"^Decimal(?:32|64|128|256)(\(\s*\d+\s*,\s*\d+\s*\))$", r"Decimal\1", ch_type, flags=re.IGNORECASE)

        # Normalize accidental wrapper nesting from upstream generation --
        # strip Nullable(...)/LowCardinality(...) in whatever order/depth they
        # appear down to the bare base type, then re-apply exactly the
        # wrappers self.nullable/low_cardinality ask for below. A prior
        # version stripped each wrapper kind in one single pass in a fixed
        # order, so "LowCardinality(Nullable(String))" only had its outer
        # LowCardinality layer stripped (the Nullable-stripping pass had
        # already finished by the time the inner Nullable was exposed),
        # leaving "Nullable(String)" -- which nullable=True then re-wrapped as
        # Nullable(Nullable(String)), rejected outright by ClickHouse
        # (ILLEGAL_TYPE_OF_ARGUMENT: "Nested type ... cannot be inside Nullable").
        while True:
            if ch_type.startswith("Nullable(") and ch_type.endswith(")"):
                ch_type = ch_type[len("Nullable("):-1].strip()
            elif ch_type.startswith("LowCardinality(") and ch_type.endswith(")"):
                ch_type = ch_type[len("LowCardinality("):-1].strip()
            else:
                break

        # ClickHouse is strict about LowCardinality + Nullable nesting.
        # For this pipeline, keep nullable strings as plain Nullable(String)
        # and reserve LowCardinality for non-nullable scalar strings.
        if self.low_cardinality and ch_type.lower() == "string" and not self.nullable:
            ch_type = f"LowCardinality({ch_type})"
        if self.nullable:
            ch_type = f"Nullable({ch_type})"
        return ch_type
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableSchema:
    """Represents a ClickHouse table schema."""
    name: str
    columns: List[ColumnSpec]
    engine: str = "MergeTree"
    partition_by: str = ""
    order_by: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    kind: str = ""  # funnel, supporting, dimension, etc.
    related_tables: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_ddl(self, database: str) -> str:
        """Generate CREATE TABLE DDL."""
        cols = []
        for col in self.columns:
            col_def = f"    {col.name} {col.to_ch_type()}"
            if col.description:
                # LLM-written descriptions routinely contain apostrophes ("Referred
                # user's device type"); unescaped, that closes the SQL string
                # literal early and breaks the whole CREATE TABLE with a syntax
                # error at whatever token follows -- same escaping ContextAgent
                # already does for its ALTER TABLE ... COMMENT calls.
                desc_escaped = col.description.replace("'", "''")
                col_def += f" COMMENT '{desc_escaped}'"
            if col.codec:
                if col.valid_codec():
                    col_def += f" CODEC({col.codec})"
                else:
                    print(f"  Warning: dropping invalid codec {col.codec!r} on {self.name}.{col.name}")
            cols.append(col_def)
        
        nl = "\n"
        comma_nl = ",\n"
        ddl = f"CREATE TABLE IF NOT EXISTS {database}.{self.name}\n(\n{comma_nl.join(cols)}\n)\n"
        ddl += f"ENGINE = {self.engine}"
        if self.partition_by:
            ddl += f"\nPARTITION BY {self.partition_by}"

        settings = dict(self.settings)
        if self.order_by:
            order_expr = self.order_by
            if not order_expr.startswith("("):
                order_expr = f"({order_expr})"
            ddl += f"\nORDER BY {order_expr}"
            # ClickHouse rejects Nullable columns in the sort key unless this is
            # set. We deliberately keep envelope columns like application_id
            # Nullable (real edge cases can exist even when a spec's own sample
            # never shows one) and still key on them when they're the best
            # available identifier -- so set the flag rather than forcing the
            # column non-null.
            nullable_cols = {c.name for c in self.columns if c.nullable}
            if any(col in order_expr for col in nullable_cols):
                settings.setdefault("allow_nullable_key", 1)
        if settings:
            settings_str = ", ".join(f"{k}={v}" for k, v in settings.items())
            ddl += f"\nSETTINGS {settings_str}"
        ddl += ";"
        if self.description:
            ddl = f"-- {self.description}\n{ddl}"
        return ddl


@dataclass
class SpecAnalysis:
    """Result of analyzing a feature spec."""
    feature_name: str
    description: str
    entities: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    properties: Dict[str, Any]
    relationships: List[Dict[str, Any]]
    suggested_tables: List[Dict[str, Any]]
    raw_spec_md: str = ""
    raw_events_sample: List[Dict[str, Any]] = field(default_factory=list)


class InstrumentationAgent:
    """
    Agent that converts feature specs to ClickHouse schemas.
    
    Pipeline:
    1. Load context (base_context.md + meta_context_registry)
    2. Parse spec.md + events.ndjson
    3. Analyze with LLM to extract entities, events, relationships
    4. Generate ClickHouse schema with proper partitioning, ordering, codecs
    5. Validate against existing tables and best practices
    6. Emit DDL + register in meta_context_registry
    7. Invoke ContextAgent to trigger update_context for new tables
    """
    
    def __init__(
        self,
        clickhouse_client=None,
        context_agent=None,
        openrouter_config=None,
        database: str = "atlys",
        registry_table: str = "meta_context_registry",
    ):
        self.client = clickhouse_client
        self.context_agent = context_agent
        self.openrouter_config = openrouter_config
        self.database = database
        self.registry_table = registry_table
        
        # Generated schemas
        self.schemas: Dict[str, TableSchema] = {}
        # name -> DDL, for the daily segment-rollup MVs execute_and_update_context() creates
        self.materialized_views: Dict[str, str] = {}
        # Most recent parse_spec() result, kept for callers that want feature_name/raw_spec_md after process_spec()
        self.last_analysis: Optional[SpecAnalysis] = None

        # Cached context
        self._existing_tables: Dict[str, Any] = {}
        self._context_cache: Dict[str, Any] = {}
        
        # LLM client
        self._llm_client = None
        if openrouter_config and openrouter_config.enabled:
            self._llm_client = openrouter_config.get_client()
    
    # ============================================================
    # Context Loading
    # ============================================================
    
    def load_context(self) -> Dict[str, Any]:
        """Load all context: ContextAgent's business-context document + meta_context_registry."""
        # 1. The latest business-context document from ContextAgent
        if self.context_agent and hasattr(self.context_agent, "get_latest_context"):
            self._context_cache = self.context_agent.get_latest_context()

        # 2. Existing tables from registry
        if self.client:
            self._load_registry()

        return {
            "base_context": self._context_cache,
            "existing_tables": self._existing_tables,
        }
    
    def _load_registry(self):
        """Load existing table metadata from meta_context_registry -- name,
        kind, description, and version only.

        Everything else this table stores per row (`columns` -- a full
        Array(Tuple(name, type, description)) per table -- plus source_spec,
        ordering_key, partition_key, ttl_expression, related_entities, tags,
        is_current) is dead weight here: get_context_summary() only ever reads
        kind/description, and validate_schema()'s collision check only ever
        reads entity_name/version. A prior version pulled every column,
        including the heaviest one (`columns`), for every registered table on
        every process_spec() call regardless of whether anything used it --
        the more tables get registered, the more wasted work and prompt bloat
        that adds up to, for zero benefit.
        """
        query = f"""
        SELECT entity_name, kind, description, version
        FROM {self.database}.{self.registry_table}
        WHERE is_current = 1
        """
        result = self.client.query(query)
        for row in result.result_rows:
            entity_name = row[0]
            self._existing_tables[entity_name] = {
                "entity_name": row[0],
                "kind": row[1],  # funnel, supporting
                "description": row[2],
                "version": row[3],
            }
    
    def get_existing_table(self, name: str) -> Optional[Dict[str, Any]]:
        """Get existing table metadata by name."""
        return self._existing_tables.get(name)
    
    def get_all_existing_tables(self) -> Dict[str, Any]:
        """Get all existing table metadata."""
        return self._existing_tables
    
    def get_context_summary(self) -> str:
        """Get a text summary of all context for LLM prompts.

        ContextAgent.get_latest_context() now returns one whole business-context
        Markdown document ({doc_id, content, version, changelog_summary,
        updated_at}) rather than decomposed rows -- see agents/context/agent.py.
        The document's own content (business overview, metrics, known issues,
        join map, auto-instrumented tables, open flags) is injected verbatim.
        """
        parts = []

        content = (self._context_cache or {}).get("content", "")
        if content:
            version = self._context_cache.get("version", "?")
            parts.append(f"=== BUSINESS CONTEXT (living document, version {version}) ===")
            parts.append(content)

        # Existing tables -- name + one-line description only, straight from
        # meta_context_registry (never raw table data). A prior version dumped
        # every column of every registered table into this prompt on every
        # call -- 37 tables and growing, tens of thousands of characters --
        # which measurably slowed schema-generation LLM calls and was a
        # repeat contributor to truncated/invalid JSON output. Column-level
        # detail for anything already documented also lives (more concisely)
        # in the business-context document's own "Auto-instrumented tables"
        # section above; this is just an index so the LLM knows what already
        # exists and doesn't reinvent a table under a new name.
        if self._existing_tables:
            parts.append(f"\n=== EXISTING TABLES ({len(self._existing_tables)}, from meta_context_registry) ===")
            for name, t in self._existing_tables.items():
                parts.append(f"  - {name} ({t['kind']}): {t['description']}")

        return "\n".join(parts)
    
    # ============================================================
    # Spec Parsing
    # ============================================================
    
    def parse_spec(self, spec_dir: Path) -> SpecAnalysis:
        """Parse spec.md and events.ndjson from a spec directory."""
        with get_tracer().trace_span("instrumentation.parse_spec", input_data={"spec_dir": str(spec_dir)}):
            spec_file = spec_dir / "spec.md"
            events_file = spec_dir / "events.ndjson"
            
            # Read spec.md using UTF-8 on Windows-safe mode to avoid cp1252 decode failures.
            spec_md = ""
            if spec_file.exists():
                spec_md = spec_file.read_text(encoding="utf-8", errors="replace")
            
            # Sample events.ndjson stratified by event type (a flat "first N lines"
            # cap can miss event types entirely on specs where events aren't
            # evenly interleaved -- e.g. 02_group_family's first 10 lines are only
            # group_started/traveller_added, missing traveller_removed and
            # group_submitted -- which would then get no schema/columns at all).
            events_sample = []
            if events_file.exists():
                per_type_cap = 5
                by_type: Dict[str, List[Dict]] = {}
                with open(events_file, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        bucket = by_type.setdefault(event.get("event", ""), [])
                        if len(bucket) < per_type_cap:
                            bucket.append(event)
                for bucket in by_type.values():
                    events_sample.extend(bucket)
            
            # Extract key info from spec.md using LLM
            analysis = self._analyze_with_llm(spec_md, events_sample)
            
            # Add raw content
            analysis.raw_spec_md = spec_md
            analysis.raw_events_sample = events_sample
            
            return analysis

    def _analyze_with_llm(self, spec_md: str, events_sample: List[Dict]) -> SpecAnalysis:
        """Use LLM to analyze spec and extract structured info."""
        if not self._llm_client:
            return self._basic_parse(spec_md, events_sample)
        
        prompt = self._build_analysis_prompt(spec_md, events_sample)
        
        try:
            response = self._llm_client.chat.completions.create(
                model=self.openrouter_config.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=8000,
                response_format={"type": "json_object"},
            )
            
            content = (response.choices[0].message.content or "").strip()

            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                start = content.find("{")
                end = content.rfind("}")
                if start == -1 or end == -1 or end <= start:
                    raise
                parsed = json.loads(content[start:end + 1])
            
            return SpecAnalysis(
                feature_name=parsed.get("feature_name", "unknown"),
                description=parsed.get("description", ""),
                entities=parsed.get("entities", []),
                events=parsed.get("events", []),
                properties=parsed.get("properties", {}),
                relationships=parsed.get("relationships", []),
                suggested_tables=parsed.get("suggested_tables", []),
            )
        except Exception as e:
            print(f"LLM analysis failed: {e}, falling back to basic parsing")
            return self._basic_parse(spec_md, events_sample)
    
    def _get_system_prompt(self) -> str:
        # Deliberately does NOT ask for columns[]/partition_by/order_by/related_tables[]
        # on suggested_tables: nothing downstream reads them -- generate_schema()'s own
        # LLM call designs the real schema from scratch afterward, and the basic-fallback
        # path (_basic_generate/_build_basic_columns/_pick_order_by) computes its own
        # columns and ordering rather than trusting this step's. Asking for full table
        # designs here was pure wasted output -- on a spec with many suggested tables it
        # measurably inflated the response (multi-hundred-line JSON) for zero downstream
        # benefit, which is also just more surface area for a smaller model to make a
        # syntax slip in and trip json.loads().
        return """You are an expert product analyst for Atlys, a digital visa platform.
Analyze feature specifications and extract structured information for schema generation.
This step only extracts and summarizes -- proper ClickHouse types, partitioning, and
ordering keys are all decided in a separate step, so do not design full table schemas here.

Return JSON with:
- feature_name: short kebab-case name
- description: one-sentence summary
- entities: list of {name, description, properties[], identifiers[]}
- events: list of {name, description, trigger, entity_refs[], properties[]}
- properties: dict of property_name -> {type, description, examples[]}
- relationships: list of {from, to, type, description}
- suggested_tables: list of {name, kind (funnel/supporting/dimension), description} -- name/kind/description ONLY"""

    def _build_analysis_prompt(self, spec_md: str, events_sample: List[Dict]) -> str:
        context = self.get_context_summary()
        events_json = json.dumps(events_sample, indent=2, default=str) if events_sample else "[]"
        
        return f"""Analyze this feature specification and extract schema requirements.

{context}

=== FEATURE SPEC ===
{spec_md}

=== EVENTS SAMPLE (stratified, up to 5 per event type) ===
{events_json}

Extract all entities, events, properties, and relationships. Suggest new table names (with kind
and a one-line description) that follow Atlys patterns -- don't design their columns/schema yet."""

    def _basic_parse(self, spec_md: str, events_sample: List[Dict]) -> SpecAnalysis:
        """Basic regex-based parsing as fallback."""
        feature_name = "unknown"
        match = re.search(r"^#\s+(.+)$", spec_md, re.MULTILINE)
        if match:
            feature_name = match.group(1).lower().replace(" ", "-").replace("_", "-")
        
        # events.ndjson is authoritative when present.
        event_names = [e["event"] for e in events_sample if "event" in e]

        # Regex fallback from spec.md, for events the (possibly partial) raw
        # sample doesn't cover. Anchored to the leading backtick token of a
        # markdown bullet ("- `event_name` — ..."), matching this repo's spec.md
        # convention -- a prior, unanchored `` `(\w+_+\w+)` `` regex matched ANY
        # backtick-wrapped identifier anywhere in the doc, including property
        # names mentioned parenthetically (`group_id`, `traveller_index`, etc.),
        # which generated bogus near-empty tables for those properties.
        for m in re.findall(r"^-\s*`(\w+)`", spec_md, re.MULTILINE):
            if m not in event_names:
                event_names.append(m)
        for m in re.findall(r'event["\s:]+(\w+_+\w+)', spec_md, re.IGNORECASE):
            if m not in event_names:
                event_names.append(m)

        event_names = list(dict.fromkeys(event_names))
        
        entities = []
        event_properties = {}
        for e in events_sample:
            event_type = e.get("event", "unknown")
            for key, value in e.items():
                if key in ["user_id", "application_id", "timestamp", "id", "event"]:
                    continue
                prop_type = "String"
                if isinstance(value, bool):
                    prop_type = "UInt8"
                elif isinstance(value, int):
                    prop_type = "Int64"
                elif isinstance(value, float):
                    prop_type = "Float64"
                if event_type not in event_properties:
                    event_properties[event_type] = {}
                event_properties[event_type][key] = prop_type
        
        for event_type, props in event_properties.items():
            for prop_name, prop_type in props.items():
                entities.append({
                    "name": f"{event_type}.{prop_name}",
                    "description": f"Property {prop_name} of {event_type}",
                    "properties": [{"name": prop_name, "type": prop_type}],
                    "identifiers": []
                })
        
        suggested_tables = []
        for ename in event_names:
            table_name = ename.lower().replace("-", "_")
            kind = "supporting"
            funnel_keywords = ["destination_card_clicked", "application_started", "document_uploaded", "purchase_completed"]
            if any(fk in table_name for fk in funnel_keywords):
                kind = "funnel"
            
            suggested_tables.append({
                "name": table_name,
                "kind": kind,
                "description": f"Event table for {ename}",
            })
        
        return SpecAnalysis(
            feature_name=feature_name,
            description=spec_md[:500] if spec_md else "Parsed from spec",
            entities=entities,
            events=[{"name": e, "description": f"Event: {e}"} for e in event_names],
            properties={},
            relationships=[],
            suggested_tables=suggested_tables,
        )
    
    # ============================================================
    # Schema Generation
    # ============================================================
    
    def generate_schema(self, analysis: SpecAnalysis) -> List[TableSchema]:
        """Generate ClickHouse schemas from spec analysis."""
        with get_tracer().trace_span("instrumentation.generate_schema", input_data={"feature": analysis.feature_name}):
            if not self._llm_client:
                return self._basic_generate(analysis)
            
            prompt = self._build_generation_prompt(analysis)
            
            try:
                response = self._llm_client.chat.completions.create(
                    model=self.openrouter_config.model,
                    messages=[
                        {"role": "system", "content": self._get_generation_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=10000,
                    response_format={"type": "json_object"},
                )
                
                content = response.choices[0].message.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                parsed = json.loads(content)
                return self._parse_generated_schemas(parsed)
            except Exception as e:
                print(f"LLM generation failed: {e}, falling back to basic generation")
                return self._basic_generate(analysis)
    
    def _get_generation_system_prompt(self) -> str:
        return """You are an expert ClickHouse schema designer for Atlys.
Generate production-ready table schemas from analyzed feature specifications.

CRITICAL: Return ONLY valid JSON. Do not include markdown blocks, explanations, or any other text.

Return JSON with:
- tables: list of table schemas, each with:
  - name: table name (snake_case)
  - kind: "funnel" or "supporting" or "dimension"
  - description: one-line purpose
  - columns: list of {name, type, description, nullable, low_cardinality, codec}
  - partition_by: partition expression (e.g., "toYYYYMM(timestamp)")
  - order_by: ordering key (e.g., "user_id, timestamp" or "application_id, timestamp")
  - engine: "MergeTree" (default)
  - settings: dict of engine settings
  - related_tables: list of related table names
  - tags: list of tags

Atlys conventions:
- All event tables have envelope: id UUID, timestamp DateTime, user_id String, application_id Nullable(String)
- Partition by toYYYYMM(timestamp)
- Order by the column queries will actually filter/join on, followed by timestamp --
  NEVER lead with `id` (a random UUID). The existing 8 production tables all use
  `ORDER BY (id, timestamp, user_id)`, a known anti-pattern carried over from a
  legacy template: queries never filter by `id`, so it buys no data skipping and
  just adds sort cost. Do not repeat it. Prefer `(application_id, timestamp)` when
  the event always carries an application_id (i.e. it happens after
  application_started), otherwise `(user_id, timestamp)`. Some events don't
  reliably carry a user_id either -- e.g. a recipient-side event fired before
  the recipient has signed up. Check the raw samples: if a field isn't present
  on every sample, mark that column Nullable and don't force it into the sort
  key just because it's normally there; key on whatever per-entity id the
  events actually carry instead (e.g. share_id, group_id), or timestamp alone.
- Use LowCardinality for enum-like strings (device_type, visa_type, etc.)
- Use Nullable for any field not present on every raw sample -- don't assume
  the standard envelope (user_id, device_type, etc.) applies uniformly just
  because it does on the 8 existing tables; check this spec's actual samples
- Funnel tables: destination_card_clicked -> application_started -> document_uploaded -> purchase_completed
- Supporting tables: search, scroll, auth, pay_now clicks
- Reuse existing column names and types where possible"""

    def _build_generation_prompt(self, analysis: SpecAnalysis) -> str:
        context = self.get_context_summary()
        return f"""Generate ClickHouse table schemas for this feature.

{context}

=== SPEC ANALYSIS ===
Feature: {analysis.feature_name}
Description: {analysis.description}

Entities:
{json.dumps(analysis.entities, indent=2)}

Events:
{json.dumps(analysis.events, indent=2)}

Properties:
{json.dumps(analysis.properties, indent=2)}

Relationships:
{json.dumps(analysis.relationships, indent=2)}

Raw Events Sample (one representative per event type):
{json.dumps(list({e.get("event", i): e for i, e in enumerate(analysis.raw_events_sample)}.values()), indent=2, default=str)}

Generate schemas for any NEW tables needed. Also suggest modifications to existing tables if the spec requires it.
Focus on: proper ClickHouse types, partitioning, ordering, codecs, and integration with existing funnel."""

    def _parse_generated_schemas(self, parsed: Dict) -> List[TableSchema]:
        schemas = []
        for t in parsed.get("tables", []):
            columns = []
            for col in t.get("columns", []):
                columns.append(ColumnSpec(
                    name=col["name"],
                    type=col["type"],
                    description=col.get("description", ""),
                    nullable=col.get("nullable", False),
                    low_cardinality=col.get("low_cardinality", False),
                    codec=col.get("codec", ""),
                ))
            
            schema = TableSchema(
                name=t["name"],
                columns=columns,
                engine=t.get("engine", "MergeTree"),
                partition_by=t.get("partition_by", ""),
                order_by=t.get("order_by", ""),
                settings=t.get("settings", {}),
                description=t.get("description", ""),
                kind=t.get("kind", ""),
                related_tables=t.get("related_tables", []),
                tags=t.get("tags", []),
            )
            schemas.append(schema)
            self.schemas[schema.name] = schema
        
        return schemas
    
    def _relevant_samples(self, table_name: str, analysis: SpecAnalysis) -> List[Dict]:
        """Raw event samples belonging to this table's event, keyed by event name."""
        return [
            e for e in analysis.raw_events_sample
            if str(e.get("event", "")).lower().replace(" ", "_").replace("-", "_") == table_name
        ]

    def _pick_order_by(self, table_name: str, analysis: SpecAnalysis) -> str:
        """Pick an ordering key from what the event's raw samples actually carry.

        Never leads with `id` (a random UUID) -- the 8 existing production tables
        all use `ORDER BY (id, timestamp, user_id)`, which EXECUTION_PLAN.md itself
        flags as a legacy anti-pattern since no query filters by `id`. Key on
        application_id when the event always carries one (i.e. it fires after
        application_started), then user_id when that's reliably present, and
        only fall back to timestamp-only when neither is -- a mostly-NULL
        leading sort column (e.g. user_id on recipient-side events that fire
        before the recipient exists, see _build_basic_columns) buys no data
        skipping either.
        """
        samples = self._relevant_samples(table_name, analysis)
        if samples and all(e.get("application_id") for e in samples):
            return "(application_id, timestamp)"
        if samples and all(e.get("user_id") for e in samples):
            return "(user_id, timestamp)"
        return "(timestamp)" if samples else "(user_id, timestamp)"

    def _basic_generate(self, analysis: SpecAnalysis) -> List[TableSchema]:
        schemas = []
        if not analysis.suggested_tables and analysis.events:
            for event in analysis.events:
                event_name = event.get("name", "").lower().replace(" ", "_")
                if event_name:
                    analysis.suggested_tables.append({
                        "name": event_name,
                        "kind": "supporting",
                        "description": event.get("description", ""),
                    })

        for st in analysis.suggested_tables:
            columns = self._build_basic_columns(st, analysis)
            schema = TableSchema(
                name=st["name"],
                columns=columns,
                partition_by="toYYYYMM(timestamp)",
                order_by=self._pick_order_by(st["name"], analysis),
                description=st.get("description", ""),
                kind=st.get("kind", "supporting"),
                related_tables=st.get("related_tables", []),
                tags=st.get("tags", []),
            )
            schemas.append(schema)
            self.schemas[schema.name] = schema
        
        return schemas
    
    # Optional envelope fields carried by the legacy 8 tables. Included only when
    # this spec's own raw events actually carry them -- previously every
    # fallback-generated table got all 29 of these unconditionally (e.g. gclid,
    # citizenship, co_travelers on events that never emit them), which bloats the
    # schema and buries the columns judges actually care about.
    _OPTIONAL_ENVELOPE_CATALOG = [
        ColumnSpec(name="app_session_id", type="String", description="App session ID", nullable=True),
        ColumnSpec(name="device", type="String", description="Device model", nullable=True, low_cardinality=True),
        ColumnSpec(name="device_type", type="String", description="Device type", nullable=True, low_cardinality=True),
        ColumnSpec(name="os", type="String", description="Operating system", nullable=True, low_cardinality=True),
        ColumnSpec(name="app_version", type="String", description="App version", nullable=True),
        ColumnSpec(name="client_lib", type="String", description="Client library", nullable=True),
        ColumnSpec(name="geoip_country_code", type="String", description="Country code", nullable=True, low_cardinality=True),
        ColumnSpec(name="geoip_subdivision_1_code", type="String", description="Subdivision code", nullable=True),
        ColumnSpec(name="city", type="String", description="City", nullable=True),
        ColumnSpec(name="client_ip", type="String", description="Client IP", nullable=True),
        ColumnSpec(name="latitude", type="Float64", description="Latitude", nullable=True),
        ColumnSpec(name="longitude", type="Float64", description="Longitude", nullable=True),
        ColumnSpec(name="locale", type="String", description="Locale", nullable=True),
        ColumnSpec(name="language", type="String", description="Language", nullable=True),
        ColumnSpec(name="funnel_type", type="String", description="Funnel variant", nullable=True, low_cardinality=True),
        ColumnSpec(name="co_travelers", type="UInt8", description="Co-travelers count", nullable=True),
        ColumnSpec(name="is_guest", type="UInt8", description="Is guest user", nullable=True),
        ColumnSpec(name="is_referral", type="UInt8", description="Is referral", nullable=True),
        ColumnSpec(name="is_enterprise", type="UInt8", description="Is enterprise", nullable=True),
        ColumnSpec(name="gclid", type="String", description="Google click ID", nullable=True),
        ColumnSpec(name="fbclid", type="String", description="Facebook click ID", nullable=True),
        ColumnSpec(name="gad_source", type="String", description="Google Ads source", nullable=True),
        ColumnSpec(name="citizenship", type="String", description="User citizenship", nullable=True, low_cardinality=True),
        ColumnSpec(name="destination", type="String", description="Destination country", nullable=True, low_cardinality=True),
        ColumnSpec(name="is_back_filled", type="UInt8", description="Backfilled event", nullable=True),
        ColumnSpec(name="duplicate_id", type="String", description="Deduplication ID", nullable=True),
    ]

    def _build_basic_columns(self, table_spec: Dict, analysis: SpecAnalysis) -> List[ColumnSpec]:
        samples = self._relevant_samples(table_spec["name"], analysis)

        # user_id is required (non-Nullable) EXCEPT for events from users who
        # don't have one yet -- e.g. 03_status_sharing's recipient-side events
        # (link_opened, recipient_cta_clicked) are explicitly "keyed by
        # share_id" per spec.md, fired before the recipient has signed up. The
        # base_context.md invariant "user_id present on every event" doesn't
        # universally hold; the base context itself warns it can lag the data.
        user_id_nullable = bool(samples) and not all(e.get("user_id") for e in samples)

        # Required envelope -- validate_schema() and the join map depend on these.
        columns = [
            ColumnSpec(name="id", type="UUID", description="Event ID"),
            ColumnSpec(name="timestamp", type="DateTime", description="Event timestamp"),
            ColumnSpec(name="user_id", type="String", description="User identifier", nullable=user_id_nullable),
            ColumnSpec(name="application_id", type="String", description="Application ID", nullable=True),
        ]

        observed_keys = {k for e in samples for k in e.keys()}
        for candidate in self._OPTIONAL_ENVELOPE_CATALOG:
            if candidate.name in observed_keys:
                columns.append(candidate)

        for entity in analysis.entities:
            entity_name = entity.get("name", "")
            if "." in entity_name:
                entity_event = entity_name.split(".")[0].lower().replace("-", "_")
                if entity_event != table_spec["name"]:
                    continue
                    
            for prop in entity.get("properties", []):
                col_name = prop.get("name", "").lower().replace(" ", "_")
                col_type = prop.get("type", "String")
                type_map = {
                    "string": "String",
                    "int": "Int64",
                    "integer": "Int64",
                    "float": "Float64",
                    "boolean": "UInt8",
                    "bool": "UInt8",
                    "uuid": "UUID",
                    "datetime": "DateTime",
                }
                ch_type = type_map.get(col_type.lower(), col_type)
                
                if not any(c.name == col_name for c in columns):
                    columns.append(ColumnSpec(
                        name=col_name,
                        type=ch_type,
                        description=f"From {entity.get('name', 'spec')}",
                        nullable=True,
                        low_cardinality=False if col_name in {"application_id", "user_id", "id"} else (
                            ch_type == "String" and "type" in col_name.lower()
                        ),
                    ))
        
        return columns
    
    # ============================================================
    # Validation
    # ============================================================
    
    def validate_schema(self, schema: TableSchema) -> List[str]:
        """Validate schema against best practices and existing tables."""
        issues = []
        
        envelope_cols = {"id", "timestamp", "user_id", "application_id"}
        schema_cols = {c.name for c in schema.columns}
        missing = envelope_cols - schema_cols
        if missing:
            issues.append(f"Missing envelope columns: {missing}")
        
        if not schema.partition_by:
            issues.append("Missing partition_by (recommend: toYYYYMM(timestamp))")
        elif "timestamp" not in schema.partition_by:
            issues.append("partition_by should reference timestamp")
        
        if not schema.order_by:
            issues.append("Missing order_by (recommend: user_id or application_id, then timestamp)")
        elif "timestamp" not in schema.order_by:
            issues.append("order_by should include timestamp")
        elif re.match(r"^\(?\s*id\s*,", schema.order_by):
            issues.append("order_by leads with `id` (a random UUID) -- no query filters by it; key on user_id/application_id instead")
        elif (
            "user_id" not in schema.order_by
            and "application_id" not in schema.order_by
            and not any(c.name.endswith("_id") and c.name in schema.order_by for c in schema.columns)
        ):
            # Not necessarily wrong -- some events (e.g. recipient-side events
            # fired before the recipient has a user_id) legitimately have no
            # better key than timestamp alone -- but flag it so a human reviews
            # whether a spec-specific id (share_id, group_id, ...) was missed.
            issues.append("order_by has no id-like column (timestamp only) -- confirm no better key (e.g. a spec-specific *_id) exists")
        
        col_names = [c.name for c in schema.columns]
        dupes = set([x for x in col_names if col_names.count(x) > 1])
        if dupes:
            issues.append(f"Duplicate column names: {dupes}")
        
        for existing_name, existing in self._existing_tables.items():
            if existing_name == schema.name:
                issues.append(f"Table {schema.name} already exists in registry (version {existing.get('version', '?')})")
        
        for col in schema.columns:
            if col.low_cardinality and col.type not in ("String", "LowCardinality(String)"):
                issues.append(f"LowCardinality only works with String types: {col.name}")
        
        return issues
    
    def validate_all(self) -> Dict[str, List[str]]:
        """Validate all generated schemas."""
        return {name: self.validate_schema(schema) for name, schema in self.schemas.items()}
    
    # ============================================================
    # Registry & Context Agent Operations
    # ============================================================
    
    def register_table(self, schema: TableSchema, version: int = 1) -> bool:
        """Register a new table schema in meta_context_registry.

        meta_context_registry.columns is Array(Tuple(name String, type String,
        description String)) -- nullable/low_cardinality info isn't lost, it's
        baked into to_ch_type()'s resolved type string (e.g. Nullable(String)).
        Uses client.insert() (structured, parameterized) rather than building a
        raw SQL string: the previous version hand-built an INSERT with a
        double-quoted JSON blob spliced in unquoted, which the Array(Tuple(...))
        column could never parse -- every registration silently failed.
        """
        if not self.client:
            print("No ClickHouse client, skipping registry")
            return False

        columns_tuples = [(c.name, c.to_ch_type(), c.description) for c in schema.columns]

        row = [
            schema.name, "table", schema.kind, schema.description,
            columns_tuples, "generated",
            schema.order_by, schema.partition_by, "",
            schema.related_tables, schema.tags,
            version, 1,
        ]
        column_names = [
            "entity_name", "entity_type", "kind", "description",
            "columns", "source_spec",
            "ordering_key", "partition_key", "ttl_expression",
            "related_entities", "tags",
            "version", "is_current",
        ]

        name_escaped = schema.name.replace("'", "''")
        verify_query = (
            f"SELECT count() FROM {self.database}.{self.registry_table} "
            f"WHERE entity_name = '{name_escaped}' AND version = {version}"
        )

        for attempt in (1, 2):
            try:
                # async_insert=0: this ClickHouse Cloud service defaults to
                # async_insert=1, which buffers small inserts server-side before
                # a background flush; forcing this off is necessary but wasn't
                # sufficient on its own -- see the read-back check below.
                self.client.insert(
                    f"{self.database}.{self.registry_table}",
                    [row],
                    column_names=column_names,
                    settings={"async_insert": 0},
                )
            except Exception as e:
                print(f"Failed to register {schema.name}: {e}")
                return False

            # Read-back verification: writes to this table have been observed
            # live to report success (written_rows=1, no exception in
            # system.query_log, even under select_sequential_consistency=1) yet
            # be unqueryable moments later -- reproducibly, specifically when
            # this call runs as part of the full pipeline rather than in
            # isolation. Root cause not fully pinned down (ruled out: the
            # ReplacingMergeTree is_deleted footgun, async_insert buffering,
            # replica read lag). Rather than silently report success on a write
            # that may not stick, verify and retry once before surfacing it.
            try:
                visible = self.client.query(verify_query).result_rows[0][0] > 0
            except Exception:
                visible = False

            if visible:
                print(f"Registered {schema.name} in meta_context_registry")
                return True

            if attempt == 1:
                print(f"Warning: {schema.name} not visible in meta_context_registry immediately after insert, retrying once...")

        print(f"Warning: {schema.name} registration did not verify after retry -- table was created in ClickHouse but may be MISSING from meta_context_registry. Check manually.")
        return False
    
    def register_all(self) -> Dict[str, bool]:
        """Register all generated schemas."""
        return {name: self.register_table(schema) for name, schema in self.schemas.items()}

    # ============================================================
    # Materialized Views
    # ============================================================

    _CONVERSION_NAME_HINTS = (
        "purchased", "confirmed", "completed", "submitted", "converted", "reconverted",
    )

    def _pick_primary_table(self, candidates: Optional[List[TableSchema]] = None) -> Optional[TableSchema]:
        """Heuristic for which of this spec's tables is worth a rollup MV: the
        terminal funnel step if one was tagged `kind="funnel"`, else the table
        whose name reads like a conversion/completion event, else the last
        table generated (usually the end of the spec's event sequence).
        `candidates` should be restricted to tables that actually got created --
        picking one whose CREATE TABLE failed would just fail the MV too."""
        schemas = candidates if candidates is not None else list(self.schemas.values())
        if not schemas:
            return None
        funnel = [s for s in schemas if s.kind == "funnel"]
        if funnel:
            return funnel[-1]
        for s in schemas:
            if any(hint in s.name for hint in self._CONVERSION_NAME_HINTS):
                return s
        return schemas[-1]

    def generate_materialized_view(self, schema: TableSchema) -> Optional[str]:
        """Daily device/geo rollup (event count + unique users) for one table.

        Uses AggregatingMergeTree + uniqState/uniqMerge rather than a plain
        SummingMergeTree count(DISTINCT ...): approximate-distinct states combine
        correctly across merges, a raw per-row distinct count doesn't. This is
        the table AnalyticsAgent's segment-cut queries should read from instead
        of scanning raw events every time.
        """
        nullable_by_name = {c.name: c.nullable for c in schema.columns}
        segment_cols = [c for c in ("device_type", "geoip_country_code") if c in nullable_by_name]
        if not segment_cols:
            return None

        segment_select = ", ".join(segment_cols)
        mv_name = f"{schema.name}_daily_segment_mv"
        # Same allow_nullable_key requirement as to_ddl(): device_type/
        # geoip_country_code are Nullable(String) on the source table, and this
        # DDL is hand-built rather than going through TableSchema.to_ddl() (which
        # already detects and sets this), so it needs its own check.
        settings_clause = ""
        if any(nullable_by_name.get(c) for c in segment_cols):
            settings_clause = "\nSETTINGS allow_nullable_key = 1\n"
        return (
            f"-- Daily {', '.join(segment_cols)} rollup for {schema.name}: event count + "
            f"unique users, pre-aggregated so AnalyticsAgent's segment cuts don't rescan raw events.\n"
            f"CREATE MATERIALIZED VIEW IF NOT EXISTS {self.database}.{mv_name}\n"
            f"ENGINE = AggregatingMergeTree\n"
            f"ORDER BY (day, {segment_select})\n"
            f"{settings_clause}"
            f"POPULATE AS\n"
            f"SELECT\n"
            f"    toDate(timestamp) AS day,\n"
            f"    {segment_select},\n"
            f"    count() AS events,\n"
            f"    uniqState(user_id) AS unique_users_state\n"
            f"FROM {self.database}.{schema.name}\n"
            f"GROUP BY day, {segment_select};"
        )

    def execute_and_update_context(self, source_spec: str = "") -> Dict[str, Any]:
        """
        Executes DDL statements to create generated tables in ClickHouse,
        registers them in meta_context_registry, then invokes
        ContextAgent.update_context() ONCE for every table this spec actually
        created (not once per table) to document them all in a single new
        business-context document version. A prior version called
        update_context() inside this loop -- one LLM call and one version bump
        per table, each of which could ALSO trigger its own run_audit() and a
        second version bump -- so a single 5-table spec could produce up to 10
        new document versions in one pipeline run, all landing back-to-back
        with nothing meaningful between them. Batching to one call means at
        most 2 version bumps per spec (the update, then the trailing audit)
        regardless of table count.
        """
        results = {}
        created_schemas: List[TableSchema] = []
        for schema_name, schema in self.schemas.items():
            ddl = schema.to_ddl(self.database)

            # Execute CREATE TABLE on ClickHouse. If this fails, the table does
            # not exist -- registering it in meta_context_registry or documenting
            # it in the business-context document would either lie about its
            # existence or crash outright (UNKNOWN_TABLE) and take down every
            # other schema in this spec along with it. Skip to the next table.
            ddl_ok = True
            if self.client:
                try:
                    self.client.command(ddl)
                    print(f"Executed DDL for table {schema_name}")
                except Exception as e:
                    print(f"Failed to execute DDL for table {schema_name}: {e}")
                    ddl_ok = False

            if not ddl_ok:
                results[schema_name] = {"registered": False, "context_version": None, "ddl_failed": True}
                continue

            created_schemas.append(schema)

            # Register in meta_context_registry
            registered = self.register_table(schema)
            results[schema_name] = {"registered": registered, "ddl": ddl}

        # One ContextAgent update for every table this spec created, in a
        # single call/version -- not one per table.
        if created_schemas and self.context_agent and hasattr(self.context_agent, "update_context"):
            table_names = [s.name for s in created_schemas]
            print(f"Invoking ContextAgent.update_context for {len(created_schemas)} table(s): {', '.join(table_names)}...")
            next_version = self.context_agent.update_context(
                new_tables=[{"name": s.name, "ddl": results[s.name]["ddl"]} for s in created_schemas],
                source_spec=source_spec,
            )
            for name in table_names:
                results[name]["context_version"] = next_version
        else:
            for name in results:
                results[name].setdefault("context_version", None)
        for r in results.values():
            r.pop("ddl", None)

        # One rollup MV per spec, on the table worth pre-aggregating (tables must
        # already exist, so this runs after the create-table loop above). Only
        # consider tables that were actually created.
        primary = self._pick_primary_table(created_schemas)
        if primary is not None:
            mv_ddl = self.generate_materialized_view(primary)
            if mv_ddl:
                mv_name = f"{primary.name}_daily_segment_mv"
                self.materialized_views[mv_name] = mv_ddl
                if self.client:
                    try:
                        self.client.command(mv_ddl)
                        print(f"Executed DDL for materialized view {mv_name}")
                        results[mv_name] = {"registered": None, "context_version": None, "kind": "materialized_view"}
                    except Exception as e:
                        print(f"Failed to execute DDL for materialized view {mv_name}: {e}")

        return results

    # ============================================================
    # Full Pipeline
    # ============================================================
    
    def process_spec(self, spec_dir: Path, execute_ddl: bool = True) -> List[TableSchema]:
        """Full pipeline: spec -> analysis -> schemas -> validation -> register -> update_context."""
        with get_tracer().trace_span("instrumentation.process_spec", input_data={"spec_dir": str(spec_dir)}):
            print(f"Processing spec: {spec_dir}")
            
            # Reset schemas for this spec
            self.schemas = {}
            
            # 1. Load context
            self.load_context()
            print(f"  Found {len(self._existing_tables)} existing tables in the registry")
            
            # 2. Parse spec
            analysis = self.parse_spec(spec_dir)
            self.last_analysis = analysis  # so callers (main.py) can read feature_name/raw_spec_md after the fact
            print(f"  Analyzed: {analysis.feature_name} ({len(analysis.entities)} entities, {len(analysis.events)} events)")
            
            # 3. Generate schemas
            schemas = self.generate_schema(analysis)
            print(f"  Generated {len(schemas)} table schemas")
            
            # 4. Validate
            all_issues = self.validate_all()
            for name, issues in all_issues.items():
                if issues:
                    print(f"  Validation warnings for {name}: {issues}")
                else:
                    print(f"  {name}: OK")
            
            # 5. Execute DDL, Register, and Update Context
            if execute_ddl:
                self.execute_and_update_context(source_spec=analysis.raw_spec_md)
            
            return schemas
    
    def emit_ddl(self, database: str = None, output_path: Path = None) -> str:
        """Emit all table + materialized view DDL statements (for the submission
        artifact / generated_schema.sql). Note process_spec() already executes
        this DDL directly via execute_and_update_context() -- this is for the
        written record, not a second execution pass."""
        db = database or self.database
        ddl_parts = [schema.to_ddl(db) for schema in self.schemas.values()]
        ddl_parts.extend(self.materialized_views.values())
        nl = "\n"
        full_ddl = f"{nl}{nl}".join(ddl_parts)
        if output_path:
            output_path.write_text(full_ddl)
        return full_ddl
    
    def get_schema(self, name: str) -> Optional[TableSchema]:
        """Get a generated schema by name."""
        return self.schemas.get(name)