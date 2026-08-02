"""Clustering: collapse correlated band breaches into incidents with ONE root
cause each.

WHY THIS IS NOT OPTIONAL
------------------------
Measured on this dataset: a single full sweep of the window containing the planted
demand outage produced 371 confirmed breaches. They are not 371 problems. They are
two, seen from every angle the system watches -- the same fill shortfall showing up
as Android, as Android 15, as Galaxy A54, as EU, as Android x EU, as tier_2, as
ecommerce, as global, and as each downstream metric (rpr, revenue) that fill feeds.

Unclustered, that is an alert stream nobody reads, which makes the detection
worthless no matter how accurate it is. The whole value of detecting at every scope
is realised only if the results are then reduced back to the cause.

THE ATTRIBUTION RULE
--------------------
    assign the incident to the dimension where the deviation is CONCENTRATED,
    at the level where it is UNIFORM.

Read carefully, that is two constraints pulling in opposite directions, and the
tension is the point:

  * too fine a root (Galaxy A54 x EU x tier_2) is concentrated but not uniform --
    it names one cell of a wider failure and hides the rest;
  * too coarse a root (global) is uniform but not concentrated -- it is technically
    true, useless, and dilutes the signal with everything that is fine.

The correct root for the Android outage is `os_family = Android`: the coarsest
scope at which the deviation is still specific to something, with iOS demonstrably
flat beside it.

HOW THE ROOT IS CHOSEN, WITHOUT EXTRA QUERIES
---------------------------------------------
Because the sweep already evaluated every scope, the spread of the deviation is
readable from the sweep's own results (engine/uniformity.py). So root selection
is a ranking over members using numbers already computed and already logged:

    score = specificity_penalty x sibling_isolation x impact_share

  sibling_isolation -- of the sibling values of this scope, how few breached.
    Android among {Android, iOS} = 1 of 2. tier_2 among 3 tiers when all 3
    breached = 3 of 3, which disqualifies it as a root: if every tier moved, the
    cause is not "tier_2".
  impact_share -- how much of the cluster's dollars this member holds.
  specificity_penalty -- prefers coarser scopes on ties, implementing "at the
    level where it is uniform".

CLUSTER MEMBERSHIP
------------------
Two breaches belong together when their time windows overlap AND their scopes are
related by containment (engine/scopes.contains, itself derived from key columns
rather than a hand-written parent list). Direction must also agree: a fill drop and
a CTR spike in the same hour are two findings, not one, and merging them would
produce a mechanism that explains neither.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional  # noqa: F401  (used in Incident field annotations)

from engine.config import settings, utc_now
from engine.datasets import current_database
from engine.impact import decompose_impact
from engine.scopes import contains, scope, specificity
from engine.signature import match_signature, seasonality_disproof
from engine.uniformity import partner_profile, sibling_spread, spread_profile

logger = logging.getLogger(__name__)


@dataclass
class Incident:
    incident_id: str
    opened_at: datetime
    last_seen_at: datetime
    root_scope_type: str
    root_scope_value: str
    root_metric: str
    grain: str
    direction: str
    signature: str = "S0"
    signature_confidence: float = 0.0
    mechanism: str = ""
    owner: str = "unassigned"
    impact_usd: float = 0.0
    # Exposure normalised to a daily run rate.
    #
    # This, not impact_usd, is the figure to use wherever exposure is COMPARED, because raw
    # dollars are not comparable across grains: a 15-day window has accumulated fifteen days
    # of shortfall while a 1-day window has accumulated one. Ranking on the raw figure put a
    # $31 loss spread over fifteen days ($2/day) above a $25/day demand outage with 756
    # corroborating breaches -- burying the most important finding under an arithmetic
    # artefact.
    #
    # It is no longer what the QUEUE is ordered by: the console lists incidents newest first
    # and leads with the metric movement. This still gates (below settings.impact_usd_gate an
    # incident is recorded but not raised) and is still displayed per row.
    #
    # "$X per day" is also the number an operator actually needs: it answers "what is this
    # costing me while I decide whether to act".
    impact_usd_per_day: float = 0.0
    # How many distinct root-scope windows the exposure was summed over. 1 means the
    # incident is a single window; >1 means it genuinely persisted, and impact_usd covers
    # the whole span rather than one slice of it.
    windows_spanned: int = 1
    # The ROOT breach's own window. Distinct from opened_at, which is the minimum across
    # every member and therefore reflects the coarsest grain in the cluster -- a 3-week
    # member drags opened_at back three weeks, which is the wrong anchor for a 1d lookback.
    root_window_start: Optional[datetime] = None
    root_window_end: Optional[datetime] = None
    member_event_count: int = 0
    breached_metrics: list = field(default_factory=list)
    fingerprint: str = ""
    closed_at: Optional[datetime] = None
    narration: Optional[str] = None
    narration_available: bool = False
    investigation_id: Optional[str] = None
    langfuse_trace_url: Optional[str] = None
    evidence: Optional[dict] = None
    label: str = ""
    members: list = field(default_factory=list)      # BandVerdicts
    ruled_out: list = field(default_factory=list)    # plain-language checks with numbers
    seasonality: dict = field(default_factory=dict)
    impact_breakdown: dict = field(default_factory=dict)
    history: dict = field(default_factory=dict)
    # The published-formula evidence index (engine/confidence.py). Carries its own
    # formula text, per-component breakdown and caveat, so the number is never
    # displayed without the means to check it.
    evidence_score_detail: dict = field(default_factory=dict)
    gated_by_impact: bool = False
    # Other clusters folded into this one as symptoms, each with the evidence that
    # justified the merge. Kept visible rather than discarded: a reader must be
    # able to see that tier_2 and ecommerce also breached and why they are not
    # being reported separately, otherwise absorption looks like data loss.
    absorbed: list = field(default_factory=list)

    @property
    def root_label(self) -> str:
        return f"{self.root_scope_type}={self.root_scope_value or 'overall'}"

    def summary(self) -> str:
        span = (f"over {self.windows_spanned} x {self.grain}"
                if self.windows_spanned > 1 else f"over the {self.grain} window")
        return (f"[{self.signature}] {self.root_metric} {self.direction} band on {self.root_label} "
                f"at {self.grain}: ${abs(self.impact_usd_per_day):,.2f}/day "
                f"(${abs(self.impact_usd):,.2f} {span}), "
                f"{self.member_event_count} breach(es)")


def _windows_overlap(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


# device_model -> os_family, cached PER DATABASE.
#
# Keyed as a PRECAUTION, and the distinction is worth stating rather than implying a
# bug that was not observed: measured across the two datasets loaded here, this map
# is identical (the same 8 models, the same families), because device_model ->
# os_family is a property of the device rather than of the drop. So an unkeyed cache
# happens to be harmless TODAY.
#
# It is keyed anyway because the reason it is safe is a coincidence, not a
# guarantee. `geo_device` is where this comes from and the two datasets disagree
# about 4,983 of its 5,000 rows -- they reuse the same ids for different devices --
# so a drop that introduces a model name the other lacks, or reuses one across
# families, would break it. And it would break quietly: this map only feeds DERIVED
# atoms, so the failure is a mis-cluster (one incident split, or two merged), which
# looks plausible either way rather than raising.
_DEVICE_OS_CACHE: dict = {}


def device_os_map(client=None, trace=None) -> dict:
    """device_model -> os_family, read from the `geo_device` dimension table.

    Queried rather than hardcoded because it is a fact about the data, not a convention:
    verified on this dataset that every one of the eight device models maps to exactly one
    family (iPhone 13/14/15 -> iOS; Galaxy, Pixel, Redmi -> Android), so the derivation is
    unambiguous. Cached per database for the process; falls back to an empty map, which
    simply disables the derived atom rather than guessing.
    """
    from engine.ch_client import Trace, get_client

    client = client or get_client()
    # Keyed off the client's own database for the same reason as sweep.data_floor():
    # an explicitly passed client states which dataset the answer belongs to.
    database = getattr(client, "database", None) or current_database()
    cached = _DEVICE_OS_CACHE.get(database)
    if cached is not None:
        return cached
    try:
        rows = client.query(
            "SELECT device_model, splitByChar(' ', any(os_version))[1] AS os_family "
            "FROM geo_device GROUP BY device_model",
            step="cluster:device_os_map", trace=trace if trace is not None else Trace(),
        )
        _DEVICE_OS_CACHE[database] = {r["device_model"]: r["os_family"] for r in rows}
    except Exception:
        _DEVICE_OS_CACHE[database] = {}
    return _DEVICE_OS_CACHE[database]


def atoms(scope_type: str, scope_value: str, device_os: Optional[dict] = None) -> set:
    """The set of (dimension, value) facts a breach is about.

    Pure key-column containment is not enough to relate real breaches, and both
    failure modes showed up immediately in testing:

    1. `global` has no key columns, so it CONTAINS every other scope. Linking on
       containment therefore merged all 284 breaches into one cluster whose root
       was `global` -- the least useful answer available. Global has no atoms here,
       so it cannot link anything; it is attached afterwards, to the cluster that
       actually explains it.

    2. os_version='Android 15' is obviously inside os_family='Android', but
       {os_version} is not a subset of {os_family}, so containment said no. The
       relationship lives in the VALUES, not the columns. Expanding derived atoms
       fixes it: 'Android 15' contributes both its own atom and ('os_family',
       'Android').

    Composite scopes expand to one atom per component, which is what lets
    region=EU and device_model='Galaxy A54' end up in the same cluster --
    transitively, through the geo_cell breaches that mention both.
    """
    s = scope(scope_type)
    if s.is_global:
        return set()
    parts = s.decode_value(scope_value)
    out = set()
    for col, val in zip(s.key_columns, parts):
        out.add((col, val))
        # os_version values are 'iOS 17.2' / 'Android 14', so the family is the
        # first token -- the same derivation the os_family rollup uses.
        if col == "os_version" and " " in val:
            out.add(("os_family", val.split(" ")[0]))
        # A device model implies its OS family. This derivation is what lets
        # _conflicting() tell an iPhone breach apart from an Android one -- without it a
        # geo cell carries no OS atom at all and can be merged into an incident about the
        # other platform. See _split_on_os_conflict.
        if col == "device_model" and device_os:
            family = device_os.get(val)
            if family:
                out.add(("os_family", family))
    return out


def _os_family_of(v, device_os: Optional[dict] = None) -> Optional[str]:
    """The OS family a breach is about, if it identifies one."""
    for dim, val in atoms(v.scope_type, v.scope_value, device_os):
        if dim == "os_family":
            return val
    return None


def _split_on_os_conflict(groups: list, device_os: Optional[dict] = None) -> list:
    """Splits any cluster that mixes OS families into one cluster per family.

    THIS FIXES AN OBSERVED FALSE MERGE, not a hypothetical one. Clustering links breaches
    that share a (dimension, value) atom, and union-find makes that transitive. Two
    genuinely separate concurrent incidents were therefore merged:

        geo_cell APAC|JP|iPhone 14  --shares region=APAC-->  os_family_region Android|APAC
        os_family_region Android|APAC  --shares os_family=Android-->  os_version Android 15

    so a -35.9 sigma iOS/iPhone-14 fill collapse in Japan was absorbed into an incident
    rooted on `os_version=Android 15` and described as an Android demand outage. The
    iPhone incident then had no row of its own and never reached the queue. A merge that
    hides one incident inside another is far worse than fragmentation, because
    fragmentation is visible.

    Narrow on purpose: it splits on OS FAMILY only, not on any dimension that disagrees.
    Splitting on every conflicting dimension would shatter legitimately broad incidents --
    a platform-wide outage spans every region by definition. OS family earns the exception
    because it is a hard partition of the traffic (a device runs one of them), and because a
    merge across it produces a factually wrong mechanism and routes the wrong team.

    Breaches carrying no OS atom (a region, an app, a format) attach to the surviving
    sub-cluster with the largest absolute impact rather than being dropped.
    """
    out = []
    for members in groups:
        by_family: dict = {}
        neutral = []
        for v in members:
            fam = _os_family_of(v, device_os)
            if fam is None:
                neutral.append(v)
            else:
                by_family.setdefault(fam, []).append(v)

        if len(by_family) <= 1:
            out.append(members)
            continue

        # Attach the OS-agnostic breaches to the biggest sub-cluster; they are context for
        # whichever incident carries the money, and duplicating them across both would
        # double-count.
        biggest = max(by_family, key=lambda f: sum(abs(getattr(m, "impact_usd", 0.0)) for m in by_family[f]))
        for fam, group in by_family.items():
            out.append(group + (neutral if fam == biggest else []))
    return out


def _atom_memo(device_os: Optional[dict] = None):
    """An atom-set lookup cached by (scope_type, scope_value).

    Pure speed, no effect on any result. It matters because `_related` runs once per PAIR of
    breaches: on a heavy day that meant recomputing the same few hundred atom sets tens of
    millions of times, each one a scope lookup, a value decode and a string split.
    """
    cache: dict = {}

    def get(scope_type: str, scope_value: str) -> set:
        key = (scope_type, scope_value)
        got = cache.get(key)
        if got is None:
            got = cache[key] = atoms(scope_type, scope_value, device_os)
        return got

    return get


def _related(a, b, atom_of=None) -> bool:
    """Two breaches are about the same thing when their atom sets intersect.

    Union-find then makes this transitive, which is what stitches an incident
    together across dimensions that share no atom directly.

    `atom_of` is an optional cached accessor from _atom_memo; omitting it computes atoms
    directly, which is the same answer, just slower.
    """
    if atom_of is None:
        aa = atoms(a.scope_type, a.scope_value)
        ab = atoms(b.scope_type, b.scope_value)
    else:
        aa = atom_of(a.scope_type, a.scope_value)
        ab = atom_of(b.scope_type, b.scope_value)
    if not aa or not ab:
        return False
    if aa & ab:
        return True
    # Fall back to declared containment for scopes whose relationship is
    # structural rather than value-based.
    sa, sb = scope(a.scope_type), scope(b.scope_type)
    if sa.is_global or sb.is_global:
        return False
    return (contains(sa, a.scope_value, sb, b.scope_value)
            or contains(sb, b.scope_value, sa, a.scope_value))


def cluster_verdicts(verdicts: list, coverage: list) -> list:
    """Groups confirmed breaches into incidents. Returns them ranked by dollars.

    Bounded by settings.max_verdicts_clustered. The pairwise stage below is O(n^2), so an
    abnormally noisy day would otherwise hang the monitor rather than degrade -- see the
    config comment for the measured case. If the cap binds, the largest breaches by
    |impact_usd| are kept and the drop is logged, because a truncated run that looks
    complete is worse than one that says what it left out.
    """
    if not verdicts:
        return []

    cap = max(1, int(getattr(settings, "max_verdicts_clustered", 8000)))
    dropped = 0
    if len(verdicts) > cap:
        dropped = len(verdicts) - cap
        verdicts = sorted(
            verdicts, key=lambda v: -abs(float(getattr(v, "impact_usd", 0.0) or 0.0))
        )[:cap]
        logger.warning(
            "Clustering input capped at %d of %d confirmed breaches (dropped %d smallest by "
            "|impact_usd|). The pairwise stage is O(n^2); above this it does not complete. "
            "This many breaches in one window usually means the bands are too tight for the "
            "data -- check band_k_amber before trusting the incident list.",
            cap, cap + dropped, dropped,
        )

    # Loaded once per clustering run, not per comparison: the OS family a device model
    # implies is what keeps two concurrent incidents on different platforms apart.
    device_os = device_os_map()

    # Union-find over breaches: same direction, overlapping windows, related scopes.
    parent = list(range(len(verdicts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    atom_of = _atom_memo(device_os)

    # The pairwise test below is O(n^2), so the cheapest correctness-preserving win is to
    # shrink n before entering it. Two reductions, both exact rather than approximate:
    #
    # 1. Breaches sharing (scope key, direction, window) are ALWAYS mutually related -- their
    #    atom sets are literally identical and non-empty, so every pair among them links. Ten
    #    metrics breaching on one scope at one grain is ten breaches the pairwise loop would
    #    compare 45 times to rediscover a link that is true by construction. Link them
    #    directly and send ONE representative into the loop; union-find makes the rest follow.
    # 2. Global breaches carry no atoms at all (see atoms()), so _related is False for every
    #    pair involving one. They are attached to an explaining cluster further down instead,
    #    which means putting them through the loop is pure cost.
    #
    # Measured on the heaviest day in this dataset (2026-06-22, 9,464 confirmed breaches):
    # 98.6s before, and the resulting incident set is unchanged.
    representatives = {}
    for idx, v in enumerate(verdicts):
        if scope(v.scope_type).is_global:
            continue
        key = (v.scope_type, v.scope_value, v.direction, v.window_start, v.window_end)
        first = representatives.get(key)
        if first is None:
            representatives[key] = idx
        else:
            union(first, idx)

    reps = sorted(representatives.values())
    for a in range(len(reps)):
        i = reps[a]
        vi = verdicts[i]
        vi_dir, vi_win = vi.direction, (vi.window_start, vi.window_end)
        for b in range(a + 1, len(reps)):
            j = reps[b]
            vj = verdicts[j]
            if vi_dir != vj.direction:
                continue
            if not _windows_overlap(vi_win, (vj.window_start, vj.window_end)):
                continue
            if not _related(vi, vj, atom_of):
                continue
            union(i, j)

    groups = {}
    globals_ = []
    for idx, v in enumerate(verdicts):
        if scope(v.scope_type).is_global:
            globals_.append(v)
            continue
        groups.setdefault(find(idx), []).append(v)

    # Global breaches are real and must be reported, but they are almost never a
    # separate problem -- a platform-wide fill dip IS the Android outage, seen from
    # the top. Attach each to the cluster that best explains it: same metric,
    # overlapping window, largest dollar impact. Only if nothing explains it does a
    # global breach stand as its own incident, which is the honest outcome for a
    # movement with no localisable segment.
    unexplained_globals = []
    for gv in globals_:
        candidates = [
            (sum(abs(getattr(m, "impact_usd", 0.0)) for m in members), key)
            for key, members in groups.items()
            if any(m.metric == gv.metric and m.direction == gv.direction
                   and _windows_overlap((m.window_start, m.window_end), (gv.window_start, gv.window_end))
                   for m in members)
        ]
        if candidates:
            groups[max(candidates)[1]].append(gv)
        else:
            unexplained_globals.append(gv)

    member_sets = list(groups.values()) + [[gv] for gv in unexplained_globals]
    # Undo any merge that spans two OS families -- see _split_on_os_conflict.
    member_sets = _split_on_os_conflict(member_sets, device_os)
    incidents = [_build_incident(members, verdicts, coverage) for members in member_sets]
    # Ranked by DAILY RUN RATE (see Incident.impact_usd_per_day), and SIGNED rather than
    # absolute: a gain must never outrank a loss in a queue of things to act on.
    incidents.sort(key=lambda i: -i.impact_usd_per_day)
    incidents = absorb_symptoms(incidents, verdicts, coverage)
    # Ranked by DAILY RUN RATE (see Incident.impact_usd_per_day), and SIGNED rather than
    # absolute: a gain must never outrank a loss in a queue of things to act on.
    incidents.sort(key=lambda i: -i.impact_usd_per_day)
    # Extend exposure over the consecutive earlier windows each incident persisted for, then
    # re-rank: it changes both the total and the rate.
    attach_span_impact(incidents)
    incidents.sort(key=lambda i: -i.impact_usd_per_day)
    attach_history(incidents)
    # Scored AFTER history, because the corroboration component reads it -- and a
    # chronic slice must be able to pull the score down.
    from engine.confidence import attach_scores

    attach_scores(incidents)
    return incidents


def attach_span_impact(incidents: list, limit: Optional[int] = None) -> None:
    """Extends each incident's exposure across the CONSECUTIVE earlier windows it persisted
    for, by reading `metric_events`.

    Why this needs a query rather than the members in hand: a single sweep evaluates exactly
    one window per (scope, grain), so an incident built from one sweep always spans one
    window no matter how long the real outage ran. Summing over members is therefore
    structurally incapable of producing a multi-day figure -- it has to come from the stored
    history of previous sweeps.

    What it sums is deliberately narrow, and the narrowness is what makes it additive: the
    SAME root scope, the SAME metric, the SAME grain, over consecutive windows. No other
    scope and no other grain, because those are the same money seen again.

    Anchor for whether this is right, as actually measured rather than as predicted: the
    problem-statement package puts INC-0623 at roughly $73 over its three days, i.e. ~$24.4/day.
    Sweeping Jun 24 -> 25 -> 26 in sequence yields $48.84 over 2 windows = **$24.42/day** -- the
    rate matches. The TOTAL is one day short on purpose: the Jun 23 window did not breach at
    `os_family` at all, because the outage began mid-day and that day's full-day average was
    diluted (29 events stored for that window, against 284 for each following day). The span
    covers the windows the system actually confirmed, never the windows it expects to exist.

    For contrast, the two wrong answers this replaced: summing all 756 members gave $1,680
    (the same money counted once per scope x grain), and using the root breach alone gave
    $24.54 (correct arithmetic on one window, answering a question nobody asked).

    Stops at the first gap. A slice that breached Monday and Thursday is two incidents, not
    one four-day incident.
    """
    from engine.ch_client import Trace, get_client
    from engine.grains import GRAIN_REGISTRY

    cap = limit if limit is not None else settings.max_investigations_per_sweep * 4
    client = get_client()
    trace = Trace()
    n = 0
    for inc in incidents:
        if inc.gated_by_impact or n >= cap or inc.grain not in GRAIN_REGISTRY:
            continue
        n += 1
        step = GRAIN_REGISTRY[inc.grain].duration
        # Anchored on the ROOT's window, not opened_at. opened_at is the minimum across all
        # members, so a 3-week member pushes it back three weeks and a 1d lookback then
        # searches a period where the 1d grain has no events at all -- which is exactly how
        # this silently found nothing on the first attempt.
        anchor = inc.root_window_start or inc.opened_at
        try:
            # STRICTLY earlier than the root's own window. The current window is taken from
            # the incident in hand rather than read back, because the scanner persists events
            # AFTER clustering -- so at this moment the root's own window is not in the table
            # yet. Seeding the walk from the table instead made the whole function
            # order-dependent: it started one window too early, always measured a span of 1,
            # and therefore silently did nothing except on a re-run over already-stored data.
            rows = client.query(
                "SELECT window_start, impact_usd FROM metric_events FINAL "
                f"WHERE metric = '{inc.root_metric}' AND scope_type = '{inc.root_scope_type}' "
                f"AND scope_value = '{inc.root_scope_value.replace(chr(39), chr(39) * 2)}' "
                f"AND grain = '{inc.grain}' "
                f"AND window_start < '{anchor:%Y-%m-%d %H:%M:%S}' "
                "ORDER BY window_start DESC LIMIT 60",
                step="cluster:span_impact", trace=trace,
            )
        except Exception:
            continue
        if not rows:
            continue

        # Seeded with the window just clustered, then walking backwards while each stored
        # window is exactly one grain-step earlier.
        total = float(inc.impact_usd or 0.0)
        spanned = 1
        earliest = anchor
        expected = anchor - step
        for r in rows:
            ws = r["window_start"]
            if ws != expected:
                break  # a gap: an earlier, separate episode
            total += float(r["impact_usd"] or 0.0)
            spanned += 1
            earliest = ws
            expected = ws - step

        if spanned > 1:
            inc.impact_usd = total
            inc.windows_spanned = spanned
            inc.opened_at = earliest
            grain_days = max(GRAIN_REGISTRY[inc.grain].seconds / 86400.0, 1.0 / 288)
            inc.impact_usd_per_day = total / (grain_days * spanned)


def attach_history(incidents: list, limit: Optional[int] = None) -> None:
    """Looks up prior occurrences for each incident and attaches the history block.

    Only for incidents above the dollar gate by default: a history lookup is two
    queries, and running it for hundreds of sub-dollar findings would cost more than
    the findings are worth. Gated incidents keep an explicit note saying the lookup
    was skipped and why -- an empty history block must never be mistaken for
    "no history found".
    """
    from engine import history as history_mod

    n = 0
    cap = limit if limit is not None else settings.max_investigations_per_sweep * 4
    for inc in incidents:
        if inc.gated_by_impact or n >= cap:
            inc.history = {
                "looked_up": False,
                "reason": (
                    f"history lookup skipped: this incident is below the "
                    f"${settings.impact_usd_gate:,.2f} alerting gate"
                    if inc.gated_by_impact else
                    f"history lookup skipped: only the top {cap} incidents by dollar impact are "
                    f"checked against history per sweep"
                ),
            }
            continue
        try:
            res = history_mod.lookup(inc)
            inc.history = history_mod.as_evidence(res)
            inc.history["looked_up"] = True
        except Exception as e:
            inc.history = {"looked_up": False, "reason": f"history lookup failed: {e}"}
        n += 1


def absorb_symptoms(incidents: list, verdicts: list, coverage: list) -> list:
    """Second pass: fold clusters that are SYMPTOMS of a bigger one into it.

    Atom-based clustering correctly keeps independent dimension families apart,
    but that is too strict for a real incident: when Android demand fails, the
    ecommerce category and tier_2 publishers also breach, because the affected
    apps live in them. Those are not separate incidents, and reporting them as
    such recreates the alert fatigue clustering exists to prevent -- 52 incidents
    for two real causes, in the measured case.

    The absorption test is evidence the larger incident already computed, not a new
    heuristic: incident A's partner-spread analysis says whether A's cause is
    upstream of dimension D. If A found D 'uniform' -- most of D's entities
    breached -- then a smaller cluster rooted in D is A showing through D, and it is
    absorbed.

    Symmetrically, this does NOT absorb a cluster whose dimension A found flat or
    concentrated: that is genuinely separate, and merging it would hide a second
    real problem behind the first.
    """
    if len(incidents) < 2:
        return incidents

    absorbed = set()
    for bigger in incidents:  # already sorted by impact, so larger absorbs smaller
        if id(bigger) in absorbed:
            continue
        uniform_dims = {
            r["check"].split(":", 1)[1]
            for r in bigger.ruled_out
            if r["check"].startswith("dimension:")
            and r["numbers"].get("breadth", 0.0) >= UNIFORM_BREADTH_FOR_ABSORB
        }
        if not uniform_dims:
            continue
        for smaller in incidents:
            if smaller is bigger or id(smaller) in absorbed:
                continue
            if abs(smaller.impact_usd) > abs(bigger.impact_usd):
                continue
            if smaller.direction != bigger.direction:
                continue
            if smaller.root_scope_type not in uniform_dims:
                continue
            if not _windows_overlap((smaller.opened_at, smaller.last_seen_at),
                                    (bigger.opened_at, bigger.last_seen_at)):
                continue
            # Re-stamp the absorbed breaches onto the surviving incident, or they
            # would keep pointing at an incident that is about to be discarded and
            # would vanish from both member lists.
            for v in smaller.members:
                v.incident_id = bigger.incident_id
                v.signature = bigger.signature
                v.gated_by_impact = bigger.gated_by_impact
            bigger.members.extend(smaller.members)
            bigger.member_event_count = len(bigger.members)
            # Impact is NOT added. The absorbed cluster is the same cause seen through
            # another dimension -- that is precisely why it was absorbed -- so its dollars
            # are the same dollars. Adding them would inflate the incident by however many
            # symptom dimensions happened to breach. The absorbed cluster's own figure is
            # kept below for reference.
            bigger.breached_metrics = sorted(set(bigger.breached_metrics) | set(smaller.breached_metrics))
            bigger.absorbed.append({
                "root": smaller.root_label,
                "metric": smaller.root_metric,
                "impact_usd": smaller.impact_usd,
                "events": smaller.member_event_count,
                "reason": (
                    f"{smaller.root_label} breached too, but {bigger.root_label}'s own spread "
                    f"analysis already found {smaller.root_scope_type} uniformly affected, so this "
                    f"is the same cause seen through {smaller.root_scope_type} rather than a "
                    f"separate incident. Its ${abs(smaller.impact_usd):,.2f} is the same money as "
                    f"the parent's, not additional to it."
                ),
            })
            absorbed.add(id(smaller))

    return [i for i in incidents if id(i) not in absorbed]


# Absorption uses a slightly higher bar than the wording threshold in
# uniformity.py: calling a dimension "spread" in prose is a softer claim than
# silently merging another finding into this one, and the cost of a wrong merge
# (a hidden second incident) is higher than the cost of a wrong word.
UNIFORM_BREADTH_FOR_ABSORB = 0.60


def _root_score(v, sibling: dict, cluster_impact: float) -> float:
    """Ranking for "concentrated where it is, uniform where it is".

    Multiplicative rather than additive so a member failing any one criterion
    outright cannot win on the strength of the others -- a scope whose every
    sibling also breached is not a root at any impact level.
    """
    st = sibling.get(v.scope_type)
    if st is not None and st.evaluated > 1:
        # 1.0 when this value alone breached; ~0 when all its siblings did too.
        isolation = 1.0 - (st.breached - 1) / max(1, st.evaluated - 1)
    elif v.scope_type == "global":
        # Global is uniform by definition and concentrated in nothing. It is a
        # valid root only when nothing more specific qualifies, so it is scored
        # low rather than excluded -- an incident with no localisable segment is a
        # real outcome and should still be reported.
        isolation = 0.05
    else:
        isolation = 0.5
    impact_share = abs(getattr(v, "impact_usd", 0.0)) / cluster_impact if cluster_impact else 0.0
    # Coarser scopes preferred on otherwise-equal evidence.
    coarseness = 1.0 / (1.0 + specificity(scope(v.scope_type)))
    return max(isolation, 0.0) * (0.15 + impact_share) * (0.5 + coarseness)


def _root_grain_breakdown(members: list, root, partners: dict) -> dict:
    """Where the exposure sits, decomposed so the parts actually add up.

    A decomposition is only meaningful across a dimension that PARTITIONS the traffic:
    every app is exactly one app, so per-app dollars are additive. Mixing scope types --
    an `os_family` figure beside a `category` figure beside a `global` figure -- counts the
    same events several times and produces a list whose total means nothing.

    So this picks one dimension: the most concentrated partner (fewest entities breaching)
    at the root's own grain and metric. That is the dimension where the money is actually
    localised, and it is the one an operator can act on entity by entity.

    Falls back to the root breach alone when no partner dimension has members at that
    grain -- one honest number rather than an impressive but incoherent list.
    """
    if not partners:
        return decompose_impact([root])

    # Most concentrated first: a dimension where few entities breached is where the
    # exposure is localised, whereas one where everything breached just mirrors the cause.
    ranked = sorted(
        (s for s in partners.values() if s.evaluated > 0 and s.breached > 0),
        key=lambda s: s.breadth,
    )
    for stat in ranked:
        parts = [
            m for m in members
            if m.scope_type == stat.scope_type
            and m.grain == root.grain
            and m.metric == root.metric
        ]
        if parts:
            out = decompose_impact(parts)
            out["dimension"] = stat.scope_type
            out["basis_note"] = (
                f"Split across {stat.scope_type}, which partitions the traffic, so these figures "
                f"are additive. {stat.breached} of {stat.evaluated} {stat.scope_type} entities "
                f"breached at the {root.grain} grain."
            )
            return out

    out = decompose_impact([root])
    out["dimension"] = root.scope_type
    out["basis_note"] = (
        "No partner dimension had breaches at this incident's own metric and grain, so the "
        "exposure is reported only at the root scope rather than split across overlapping views."
    )
    return out


def _build_incident(members: list, all_verdicts: list, coverage: list) -> Incident:
    total_impact = sum(abs(getattr(v, "impact_usd", 0.0)) for v in members)
    direction = members[0].direction

    # Sibling spread per scope_type, restricted to this cluster's direction, so
    # "how many siblings moved" is measured on the same event.
    sibling = spread_profile(all_verdicts, coverage, direction=direction)

    root = max(members, key=lambda v: _root_score(v, sibling, total_impact))

    metric_stats = spread_profile(all_verdicts, coverage, metric=root.metric,
                                 direction=direction, grain=root.grain)
    partners = partner_profile(root.scope_type, metric_stats)
    sib_stat = sibling_spread(root.scope_type, root.scope_value, all_verdicts, coverage,
                              metric=root.metric, direction=direction, grain=root.grain)

    # THE INCIDENT'S EXPOSURE IS THE ROOT BREACH'S, NOT THE SUM OF ITS MEMBERS.
    #
    # Summing was wrong, and badly so. An incident's members describe overlapping views
    # of the SAME money: `global fill_rate`, `os_family=Android fill_rate` and
    # `os_version=Android 15 fill_rate` are three measurements of one shortfall, and the
    # same breach also appears at 1d, 5d, 10d, 1w, 2w and 3w. Adding them multiplied one
    # incident's cost by the number of angles the system happened to observe it from --
    # measured here, $1,680 claimed against a root breach of ~$25, an overstatement of
    # roughly 60x that grew with coverage. Better coverage must not inflate the bill.
    #
    # The root breach is the one non-overlapping, defensible measurement: one metric, one
    # scope, one grain. Other members stay attached as corroboration and are presented as
    # alternative views rather than as additive contributions.
    # ...but the ROOT BREACH ALONE is one window, and an incident usually is not.
    #
    # The root's own figure covers a single window at a single scope. For a three-day
    # outage detected at the 1d grain that reports one day of it -- measured: $24.54 against
    # a spec ground truth of ~$73 for the same incident. So the correct figure is the root
    # scope and metric at ONE grain, summed over the DISTINCT windows the incident spans.
    # That is additive by construction: same scope, same grain, non-overlapping in time.
    #
    # Members at other scopes and other grains are excluded from the sum precisely because
    # they are the same money seen again (that path gave $1,680, a ~60x overstatement that
    # grew as coverage improved).
    root_windows = {
        (m.window_start, m.window_end): float(getattr(m, "impact_usd", 0.0) or 0.0)
        for m in members
        if m.metric == root.metric
        and m.scope_type == root.scope_type
        and m.scope_value == root.scope_value
        and m.grain == root.grain
    }
    root_impact = float(getattr(root, "impact_usd", 0.0) or 0.0)
    signed_impact = sum(root_windows.values()) if root_windows else root_impact
    windows_spanned = max(1, len(root_windows))
    match = match_signature(
        metric=root.metric, direction=direction,
        root_scope_type=root.scope_type, root_scope_value=root.scope_value,
        partner_stats=partners, sibling_stat=sib_stat, impact_usd=signed_impact,
    )
    season = seasonality_disproof(sib_stat, root.scope_type, root.scope_value)

    metrics = sorted({v.metric for v in members})
    # Fingerprint: what makes two occurrences "the same kind of incident" for the
    # purposes of historical memory. Deliberately excludes time and dollar amount
    # -- a recurrence is the same mechanism on the same scope shape, not the same
    # size.
    fingerprint = "|".join([
        match.signature, direction, root.scope_type, root.scope_value, root.metric,
        ",".join(metrics),
    ])

    from engine.grains import GRAIN_REGISTRY

    grain_days = max(
        GRAIN_REGISTRY[root.grain].seconds / 86400.0 if root.grain in GRAIN_REGISTRY else 1.0,
        1.0 / 288,  # a 5-minute window still gets a finite divisor
    )
    # Divided by the total span, not by one window's length, so the rate stays a rate no
    # matter how many windows the incident covers.
    per_day = signed_impact / (grain_days * windows_spanned)

    now = utc_now()
    inc = Incident(
        incident_id=str(uuid.uuid4()),
        # The ROOT breach's window, deliberately NOT min/max across all members. Members span
        # 14 grains, so a 3-week corroborating member would drag opened_at back three weeks
        # and make a one-day incident claim it started on Jun 5. That figure is consumed as a
        # real time range in three places -- the investigation window (scanner.py), the
        # history cutoff (history.py) and the headline the operator reads -- so it has to be
        # the window the incident was actually measured in. Coarser members are corroboration,
        # not extra duration; attach_span_impact is what legitimately extends this, and only
        # over consecutive windows of the root's OWN grain.
        opened_at=root.window_start,
        last_seen_at=root.window_end,
        root_scope_type=root.scope_type,
        root_scope_value=root.scope_value,
        root_metric=root.metric,
        grain=root.grain,
        direction=direction,
        signature=match.signature,
        signature_confidence=match.confidence,
        mechanism=match.mechanism,
        owner=match.owner,
        impact_usd=signed_impact,
        impact_usd_per_day=per_day,
        windows_spanned=windows_spanned,
        root_window_start=root.window_start,
        root_window_end=root.window_end,
        member_event_count=len(members),
        breached_metrics=metrics,
        fingerprint=fingerprint,
        members=members,
        seasonality=season,
        impact_breakdown=_root_grain_breakdown(members, root, partners),
    )

    # The $ gate: recorded either way, alerted only above it, and the gate value is stated
    # so suppression is visible rather than silent. Applied to the DAILY RATE so the gate
    # means the same thing at every grain -- against the raw window figure, a trivial slice
    # would clear a $1 gate simply by being observed over three weeks.
    if abs(per_day) < settings.impact_usd_gate:
        inc.gated_by_impact = True

    # Stamp the incident onto its member breaches, so metric_events rows carry the
    # link. Done HERE rather than as a second write pass: the sweep persists its
    # verdicts after clustering, so setting the fields now means one insert carries
    # them. Without it `metric_events.incident_id` stays NULL and an incident's own
    # member list comes back empty -- the breaches are all still in the table, just
    # not attributable to the incident they explain.
    for v in members:
        v.incident_id = inc.incident_id
        v.signature = match.signature
        v.status = "clustered"
        v.gated_by_impact = inc.gated_by_impact

    # Ruled-out list: every partner dimension that was checked and cleared, with
    # its own numbers, plus the seasonality argument and the $ gate.
    for st in sorted(partners.values(), key=lambda s: -s.evaluated):
        inc.ruled_out.append({
            "check": f"dimension:{st.scope_type}",
            "reason": st.as_reason(),
            "numbers": {"breached": st.breached, "evaluated": st.evaluated,
                        "breadth": round(st.breadth, 4),
                        "top_value": st.top_value,
                        "concentration": round(st.concentration, 4)},
            "source_steps": st.source_steps,
        })
    inc.ruled_out.append({
        "check": "seasonality",
        "reason": season.get("reason", ""),
        "numbers": {k: v for k, v in season.items() if k != "reason"},
        "source_steps": sorted({s for st in partners.values() for s in st.source_steps}),
    })
    if inc.gated_by_impact:
        inc.ruled_out.append({
            "check": "impact_gate",
            "reason": (f"estimated exposure ${abs(signed_impact):,.2f} is below the "
                       f"${settings.impact_usd_gate:,.2f} alerting gate, so this is recorded in the "
                       f"audit history but not raised -- a large deviation on a commercially "
                       f"immaterial slice is not an incident"),
            "numbers": {"impact_usd": signed_impact, "gate_usd": settings.impact_usd_gate},
            "source_steps": [],
        })
    return inc


def alertable(incidents: list) -> list:
    """Incidents worth acting on: above the dollar gate and costing money, most expensive
    first. Gated and gain-direction incidents are still persisted and still queryable --
    they are just not raised.

    Gains are excluded from the ACTION list but not from the record. An above-band move is
    genuinely diagnostic (a CTR spike is click fraud, a requests spike is bot traffic, an
    eCPM spike is a misconfigured floor) so it must stay visible -- but it does not belong
    at the top of a list of things costing money, which is where absolute-value ranking put
    it.
    """
    return [i for i in incidents if not i.gated_by_impact and i.impact_usd_per_day > 0]


def gains(incidents: list) -> list:
    """Above-band, money-arriving findings. Reported separately, never as an outage."""
    return [i for i in incidents if not i.gated_by_impact and i.impact_usd_per_day <= 0]


def summarize(incidents: list, limit: int = 10) -> str:
    lines = []
    for i in incidents[:limit]:
        lines.append(i.summary())
        lines.append(f"    mechanism: {i.mechanism[:220]}")
        lines.append(f"    owner: {i.owner}  confidence: {i.signature_confidence:.2f}  "
                     f"members: {i.member_event_count}  metrics: {', '.join(i.breached_metrics)}")
    if len(incidents) > limit:
        lines.append(f"  ... and {len(incidents) - limit} more incident(s)")
    return "\n".join(lines)
