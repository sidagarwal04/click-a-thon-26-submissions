"""Scope registry: every slice of the business that gets its own baseline band.

A SCOPE is a way of cutting the data (region, app, advertiser, region x device,
...). A scope's ENTITIES are the concrete values in it (APAC, app_00123, ...).
Every entity of every scope gets a band; the sweep evaluates them all in one
query per (scope, grain), which is why covering 2,000 apps costs the same as
covering 5 regions.

CONTAINMENT IS DERIVED, NOT DECLARED
------------------------------------
Clustering needs to know that "APAC x IN x iPhone 14" is inside "APAC", so that
one incident is reported instead of one per affected slice. That relationship is
NOT maintained as a hand-written parent list -- those go stale the moment a
scope is added, and a wrong edge silently splits or merges incidents.

Instead it falls out of the key columns: scope A contains scope B when A's key
columns are a subset of B's, and B's values agree with A's on those columns.

    global()                    contains everything (no keys to disagree on)
    region(region)              contains geo_cell(region, country, device_model)
    device_model(device_model)   also contains geo_cell -- containment is a
                                 lattice, not a tree, and treating it as a tree
                                 is what makes a device-wide outage get filed
                                 under one arbitrary region

WHICH SCOPES HAVE SUB-HOUR SOURCES
----------------------------------
Only global, region and ad_format. A 5-minute rollup keyed by app_id would be
~20M rows against a 9M-row fact table -- bigger than the raw data, which defeats
the entire point of a rollup. Sub-hour questions about one app are answered by a
partition-pruned raw drill instead, logged verbatim. `minute5_table = None` is
the honest encoding of that: the sweep records those cells as skipped for want
of a source, rather than quietly monitoring less than it claims.

THE EMPTY KEY
-------------
advertiser_id is '' on unfilled requests -- no ad was served, so there is no
advertiser, vertical or campaign_type to attribute anything to. That is a
fill-rate artifact, not a segment, and banding it would produce an "advertiser"
whose fill rate is always exactly 0. Scopes derived from advertiser therefore
set excludes_empty_key.
"""

from dataclasses import dataclass
from typing import Optional

from engine.config import _csv_setting, settings
from engine.grains import BASES, GrainSpec

SCOPE_VALUE_SEP = "|"

# Which underlying entity each key column is an attribute OF.
#
# This matters for one specific reason: a uniformity check must spread a
# deviation across dimensions that are INDEPENDENT of the one being tested. An
# app's category is not independent of the app -- it is a function of it -- so
# "is this drop uniform across categories?" is partly asking "is this drop
# uniform across itself". One broken app drags its own category down and the
# check reports a spurious concentration.
#
# Grouping columns by their entity root makes independence computable instead of
# hand-listed: two scopes are independent exactly when their root sets are
# disjoint.
COLUMN_ENTITY_ROOT = {
    # attributes of geo_device_id
    "region": "geo_device",
    "country": "geo_device",
    "device_model": "geo_device",
    "os_version": "geo_device",
    "os_family": "geo_device",
    # attributes of app_id
    "app_id": "app",
    "category": "app",
    "publisher_tier": "app",
    # attributes of advertiser_id
    "advertiser_id": "advertiser",
    "vertical": "advertiser",
    "campaign_type": "advertiser",
    # its own root: ad_format is a column on ad_events, not a dimension attribute
    "ad_format": "ad_format",
}


@dataclass(frozen=True)
class ScopeSpec:
    name: str
    label: str
    # Columns in the rollup that identify one entity. Empty tuple = the global
    # series (exactly one entity, whose scope_value is '').
    key_columns: tuple
    # Source table for the 1h / 1d / 1mo bases (all three read the same hourly
    # rollup, folded up with toStartOfDay/toStartOfMonth).
    hourly_table: str
    # Source table for the 5m base, or None when no sub-hour rollup exists.
    minute5_table: Optional[str] = None
    # Expression reproducing each key column directly from raw ad_events, for
    # the drill path that leaves the rollup layer.
    raw_exprs: tuple = ()
    # High cardinality: tiering by revenue contribution controls how often the
    # fine grains are swept. It never controls WHETHER an entity is covered.
    is_entity: bool = False
    # Drop the '' key (see module docstring).
    excludes_empty_key: bool = False
    # Metrics that are structurally MEANINGLESS for this scope, not merely
    # sparse. See the note on advertiser-derived scopes below -- a band on a
    # quantity that can only ever take one value is a false claim of coverage,
    # and it is worse than an admitted gap because it looks like monitoring.
    unsupported_metrics: tuple = ()
    # Purely descriptive: what this scope's breach usually implicates. Used in
    # signature wording, never in a numeric claim.
    implicates: str = ""

    @property
    def is_global(self) -> bool:
        return len(self.key_columns) == 0

    @property
    def entity_roots(self) -> frozenset:
        """The underlying entities this scope slices by. Two scopes are
        independent -- and so usable as each other's uniformity partners --
        exactly when these sets are disjoint. See COLUMN_ENTITY_ROOT."""
        return frozenset(COLUMN_ENTITY_ROOT[c] for c in self.key_columns)

    @property
    def is_composite(self) -> bool:
        return len(self.key_columns) > 1

    def table_for(self, g: GrainSpec) -> Optional[str]:
        """Source table for this scope at this grain, or None when the scope has
        no source at that grain's base."""
        base = BASES[g.base]
        if base.table_suffix == "minute5":
            return self.minute5_table
        return self.hourly_table

    def time_column_for(self, g: GrainSpec) -> str:
        return BASES[g.base].time_column

    def supports(self, g: GrainSpec) -> bool:
        return self.table_for(g) is not None

    def supports_metric(self, metric: str) -> bool:
        return metric not in self.unsupported_metrics

    def metrics_for(self, metrics) -> list:
        return [m for m in metrics if self.supports_metric(m)]

    def encode_value(self, parts) -> str:
        """Joins key-column values into the single scope_value string stored in
        baselines / metric_events. Global scopes encode as ''."""
        return SCOPE_VALUE_SEP.join(str(p) for p in parts)

    def decode_value(self, scope_value: str) -> tuple:
        if self.is_global:
            return ()
        return tuple(scope_value.split(SCOPE_VALUE_SEP))

    def value_sql(self) -> str:
        """SQL producing scope_value from the rollup's key columns, so the
        stored form and the queried form cannot diverge."""
        if self.is_global:
            return "''"
        if len(self.key_columns) == 1:
            return f"toString({self.key_columns[0]})"
        joined = ", ".join(f"toString({c})" for c in self.key_columns)
        return f"concatWithSeparator('{SCOPE_VALUE_SEP}', {joined})"

    def describe_value(self, scope_value: str) -> str:
        """Human label for one entity, e.g. 'APAC x IN x iPhone 14'."""
        if self.is_global:
            return "overall"
        parts = self.decode_value(scope_value)
        return " x ".join(parts)


SCOPE_REGISTRY = {
    s.name: s
    for s in (
        ScopeSpec(
            name="global", label="Overall", key_columns=(),
            hourly_table="hourly_overall", minute5_table="minute5_overall",
            implicates="platform-wide",
        ),
        # --- geo / device ---
        ScopeSpec(
            name="region", label="Region", key_columns=("region",),
            hourly_table="hourly_by_region", minute5_table="minute5_by_region",
            raw_exprs=("dictGet('geo_device_dict', 'region', geo_device_id)",),
            implicates="a geography",
        ),
        ScopeSpec(
            name="country", label="Country", key_columns=("country",),
            hourly_table="hourly_by_country",
            raw_exprs=("dictGet('geo_device_dict', 'country', geo_device_id)",),
            implicates="a geography",
        ),
        ScopeSpec(
            name="device_model", label="Device model", key_columns=("device_model",),
            hourly_table="hourly_by_device_model",
            raw_exprs=("dictGet('geo_device_dict', 'device_model', geo_device_id)",),
            implicates="a device population",
        ),
        ScopeSpec(
            name="os_version", label="OS version", key_columns=("os_version",),
            hourly_table="hourly_by_os_version",
            raw_exprs=("dictGet('geo_device_dict', 'os_version', geo_device_id)",),
            implicates="an OS build",
        ),
        ScopeSpec(
            name="os_family", label="OS family", key_columns=("os_family",),
            hourly_table="hourly_os_family_region",
            raw_exprs=("splitByChar(' ', dictGet('geo_device_dict', 'os_version', geo_device_id))[1]",),
            implicates="a demand integration for one OS",
        ),
        # --- inventory ---
        ScopeSpec(
            name="ad_format", label="Ad format", key_columns=("ad_format",),
            hourly_table="hourly_by_format", minute5_table="minute5_by_format",
            raw_exprs=("ad_format",),
            implicates="a format's demand or player",
        ),
        ScopeSpec(
            name="app", label="App", key_columns=("app_id",),
            hourly_table="hourly_by_app", raw_exprs=("app_id",), is_entity=True,
            implicates="one publisher integration",
        ),
        ScopeSpec(
            name="category", label="App category", key_columns=("category",),
            hourly_table="hourly_by_category",
            raw_exprs=("dictGet('apps_dict', 'category', app_id)",),
            implicates="a content category",
        ),
        ScopeSpec(
            name="publisher_tier", label="Publisher tier", key_columns=("publisher_tier",),
            hourly_table="hourly_by_publisher_tier",
            raw_exprs=("dictGet('apps_dict', 'publisher_tier', app_id)",),
            implicates="a supply tier",
        ),
        # --- demand ---
        # --- demand ---
        # NOTE on ADVERTISER_DERIVED_UNSUPPORTED below: for these three scopes a
        # rollup row exists only when an ad was actually served, because
        # advertiser_id is '' on unfilled requests. So their `requests` column
        # counts FILLED requests -- verified exactly on live data:
        #     hourly_by_advertiser (non-empty): requests = fills = 7,027,910
        #     hourly_by_region (all traffic):   requests = 9,000,000, fills = 7,027,910
        # Two consequences, both handled rather than tolerated:
        #   fill_rate is identically 1.0 -- it has no variance and no meaning here.
        #     Left in, it produced 20,643 bands with centre exactly 1.0 and zero
        #     spread, every one of which would score any movement as a maximal
        #     breach. Excluded.
        #   rpr is revenue/requests, which for these scopes is revenue per FILL,
        #     not per request. The number would be correct arithmetic under a
        #     wrong name, which is precisely the kind of quietly-misleading figure
        #     that costs more than a missing one. Excluded; ecpm covers pricing
        #     for these scopes properly.
        ScopeSpec(
            name="advertiser", label="Advertiser", key_columns=("advertiser_id",),
            hourly_table="hourly_by_advertiser", raw_exprs=("advertiser_id",),
            is_entity=True, excludes_empty_key=True,
            unsupported_metrics=("fill_rate", "rpr"),
            implicates="one buyer's budget or campaign",
        ),
        ScopeSpec(
            name="vertical", label="Advertiser vertical", key_columns=("vertical",),
            hourly_table="hourly_by_vertical",
            raw_exprs=("dictGetOrDefault('advertisers_dict', 'vertical', advertiser_id, '')",),
            excludes_empty_key=True,
            unsupported_metrics=("fill_rate", "rpr"),
            implicates="a whole demand vertical",
        ),
        ScopeSpec(
            name="campaign_type", label="Campaign type", key_columns=("campaign_type",),
            hourly_table="hourly_by_campaign_type",
            raw_exprs=("dictGetOrDefault('advertisers_dict', 'campaign_type', advertiser_id, '')",),
            excludes_empty_key=True,
            unsupported_metrics=("fill_rate", "rpr"),
            implicates="a buying model",
        ),
        # --- composite cells: the scopes that make a segment-only incident
        # detectable rather than merely explainable after something else fired ---
        ScopeSpec(
            name="geo_cell", label="Region x Country x Device",
            key_columns=("region", "country", "device_model"),
            hourly_table="hourly_geo_cell",
            raw_exprs=(
                "dictGet('geo_device_dict', 'region', geo_device_id)",
                "dictGet('geo_device_dict', 'country', geo_device_id)",
                "dictGet('geo_device_dict', 'device_model', geo_device_id)",
            ),
            implicates="targeted demand for one device population in one place",
        ),
        ScopeSpec(
            name="os_family_region", label="OS family x Region",
            key_columns=("os_family", "region"),
            hourly_table="hourly_os_family_region",
            raw_exprs=(
                "splitByChar(' ', dictGet('geo_device_dict', 'os_version', geo_device_id))[1]",
                "dictGet('geo_device_dict', 'region', geo_device_id)",
            ),
            implicates="a demand partner serving one OS in one region",
        ),
        ScopeSpec(
            name="format_region", label="Format x Region",
            key_columns=("ad_format", "region"),
            hourly_table="hourly_format_region",
            raw_exprs=(
                "ad_format",
                "dictGet('geo_device_dict', 'region', geo_device_id)",
            ),
            implicates="a format's demand source in one region",
        ),
    )
}


def scope(name: str) -> ScopeSpec:
    return SCOPE_REGISTRY[name]


def monitored_scopes() -> list:
    names = _csv_setting(settings.monitor_scopes, list(SCOPE_REGISTRY.keys()))
    unknown = [n for n in names if n not in SCOPE_REGISTRY]
    if unknown:
        raise ValueError(f"MONITOR_SCOPES names unknown scope(s): {unknown}")
    return names


# ---------------------------------------------------------------------------
# Containment lattice
# ---------------------------------------------------------------------------
def contains(outer: ScopeSpec, outer_value: str, inner: ScopeSpec, inner_value: str) -> bool:
    """True when `inner`'s entity lies inside `outer`'s.

    Derived purely from key columns and values, so it stays correct when a scope
    is added. `global` contains everything; a scope contains itself only when the
    values are equal.
    """
    if outer.is_global:
        return True
    if not set(outer.key_columns).issubset(set(inner.key_columns)):
        return False
    outer_parts = dict(zip(outer.key_columns, outer.decode_value(outer_value)))
    inner_parts = dict(zip(inner.key_columns, inner.decode_value(inner_value)))
    return all(inner_parts.get(col) == val for col, val in outer_parts.items())


def specificity(s: ScopeSpec) -> int:
    """How narrow a scope is. Used to choose the ROOT scope of an incident: the
    attribution rule is 'concentrated where it is, uniform where it is', so
    among candidate scopes that all explain the same breach, the least specific
    one that still explains it is the right root -- reporting 'Android demand'
    rather than 300 individual apps downstream of it."""
    return len(s.key_columns)


def coarser_alternatives(s: ScopeSpec) -> list:
    """Scopes strictly coarser than `s` (a subset of its key columns), coarsest
    first. These are the candidates an incident's root may be promoted to."""
    out = [
        other for other in SCOPE_REGISTRY.values()
        if other.name != s.name and set(other.key_columns).issubset(set(s.key_columns))
    ]
    return sorted(out, key=specificity)


def finer_alternatives(s: ScopeSpec) -> list:
    """Scopes strictly finer than `s`. These are where a drill-down looks next
    for the epicentre."""
    out = [
        other for other in SCOPE_REGISTRY.values()
        if other.name != s.name and set(s.key_columns).issubset(set(other.key_columns))
    ]
    return sorted(out, key=specificity)


def partner_dimensions(s: ScopeSpec) -> list:
    """Scopes independent of `s` -- the dimensions a uniformity check spreads a
    deviation across.

    This is the operational core of the signature matrix: "requests down in one
    country, uniform across every app and every device" means an external,
    user-side event, while "down in one app, across all countries and devices"
    means that app's own supply broke. Both are the same measurement taken
    against different partners, so the partners must be independent of the scope
    under test.

    Independence is by ENTITY ROOT, not by column name. Excluding only scopes
    that share a literal column would leave `category` as a partner of `app`,
    and a category is a function of its apps -- one broken app pulls its own
    category down, so the spread check would see a concentration it created
    itself and report a false localization. Same for vertical/campaign_type
    against advertiser, and for every geo attribute against another.
    """
    own_roots = s.entity_roots
    out = [
        other for other in SCOPE_REGISTRY.values()
        if not other.is_global and not (other.entity_roots & own_roots)
    ]
    return sorted(out, key=specificity)


def sibling_values_scope(s: ScopeSpec) -> Optional[ScopeSpec]:
    """For a composite scope, the coarsest scope that isolates its most specific
    key -- used for the SIBLING comparison, which is a different question from
    the partner spread.

    Partners ask "did this happen everywhere else too?". Siblings ask "did the
    other values of THIS dimension move as well?" -- which is how the device test
    rules out seasonality: seasonality moves people, and people carry every
    device, so a real seasonal dip moves iOS and Android together. Android alone
    collapsing while iOS stays flat cannot be seasonal, and that is a sibling
    comparison, not a partner one.
    """
    if s.is_global or not s.key_columns:
        return None
    last = s.key_columns[-1]
    for other in sorted(SCOPE_REGISTRY.values(), key=specificity):
        if other.key_columns == (last,):
            return other
    return None


def cadence_tier_grains(tier: str, all_grains: list) -> list:
    """Which grains an entity of this contribution tier is swept at.

    Tiering changes WHEN a slice is checked, never WHETHER: every tier still
    reaches every coarse grain, so no entity is ever uncovered. What tiering
    buys is not skipping work on the tail -- the sweep reads a whole scope in one
    query regardless -- but avoiding sub-hour evaluation for slices whose
    sub-hour volume could not clear a power floor anyway.
    """
    from engine.grains import GRAIN_REGISTRY

    if tier == "A":
        return list(all_grains)
    floor_seconds = 900 if tier == "B" else 3600
    return [g for g in all_grains if GRAIN_REGISTRY[g].seconds >= floor_seconds]
