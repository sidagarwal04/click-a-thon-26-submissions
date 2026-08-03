"""Mock topology generator -- the honest half of the anti-overfitting evidence.

`tests/test_generalization.py` proves the *source* names no known feature. That is
necessary and not sufficient: source can be clean and behaviour can still be tuned to
the five shapes we were handed. So this module emits `spec.md` + `events.ndjson` pairs
in exactly the shape of the shipped spec directories, for event topologies that are
deliberately OUTSIDE those five:

  deep_linear      8 sequential steps, two of them carrying objects nested TWO levels
                   deep (`payment.card.network`). Flattening must recurse past one level
                   or those fields land in the table as a stringified dict.

  double_fanout    parent -> child -> grandchild. Three id columns are plausible entity
                   keys and two of them tie on every primary criterion, so entity-key
                   derivation has to report ambiguity rather than pick silently.

  mutation_heavy   add / remove / reorder against a collection. Steps repeat and
                   interleave per entity, so pairwise step precedence is near 50/50 and
                   an ordered funnel is meaningless; net state is the only real metric.

  sparse_envelope  40% of rows carry no actor id and no device/geo. Half of that 40%
                   omits the key entirely and half sends the empty string, which is the
                   direct test of the `uniq(actor)` trap: after load, both look like ''.

Everything here is deterministic. The seed is a fixed constant and every timestamp is
derived from a fixed base instant -- a generator that reaches for the wall clock or an
unseeded RNG produces a different corpus on every run, which makes the suite useless as
a regression check (a behaviour change and a data change become indistinguishable).

    python tools/mock_spec.py --out tools/mock_specs
    python tools/mock_spec.py --check          # regenerate and diff against disk

Run the pipeline over the result with `tools/mock_eval.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

import orjson

# --------------------------------------------------------------------------
# determinism
# --------------------------------------------------------------------------

SEED = 20260801
BASE_TS = datetime(2026, 5, 4, 6, 0, 0)
DEFAULT_OUT = Path(__file__).resolve().parent / "mock_specs"


def _rng(topology: str) -> random.Random:
    """One stream per topology, seeded from the fixed constant plus the name.

    Deriving the per-topology seed means adding a fifth topology cannot shift the
    bytes of the first four.
    """
    h = hashlib.sha256(f"{SEED}:{topology}".encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _ts(offset_seconds: float) -> str:
    """ISO-8601 with milliseconds, matching the shipped event envelope exactly."""
    return (BASE_TS + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class _Ids:
    """32-char dashless hex, same shape as the shipped `id` column. Counter-driven."""

    def __init__(self, topology: str) -> None:
        self._salt = f"{SEED}:{topology}"
        self._n = 0

    def next(self, kind: str = "row") -> str:
        self._n += 1
        return hashlib.md5(f"{self._salt}:{kind}:{self._n}".encode()).hexdigest()


# --------------------------------------------------------------------------
# shared envelope
# --------------------------------------------------------------------------

_DEVICES = ["ios", "android", "web-user-b2c"]
_OS_FOR = {"ios": "iOS", "android": "Android", "web-user-b2c": "Mac OS X"}
_LIB_FOR = {"ios": "mobile-rn", "android": "mobile-rn", "web-user-b2c": "web-js"}
_COUNTRIES = [("IN", "Mumbai"), ("SG", "Singapore"), ("AE", "Dubai"), ("GB", "London")]
_APP_VERSIONS = ["7.44.0", "7.45.1", "7.46.0"]


@dataclass
class _Actor:
    """A stable per-entity slice of envelope values, so a funnel is coherent."""

    device_type: str
    os: str
    client_lib: str
    geoip_country_code: str
    city: str
    app_version: str

    @classmethod
    def draw(cls, rng: random.Random) -> "_Actor":
        d = rng.choice(_DEVICES)
        cc, city = rng.choice(_COUNTRIES)
        return cls(d, _OS_FOR[d], _LIB_FOR[d], cc, city, rng.choice(_APP_VERSIONS))

    def as_dict(self) -> dict[str, Any]:
        return {
            "device_type": self.device_type,
            "os": self.os,
            "app_version": self.app_version,
            "geoip_country_code": self.geoip_country_code,
            "city": self.city,
            "client_lib": self.client_lib,
        }


@dataclass
class Topology:
    name: str
    title: str
    spec_md: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def sorted_events(self) -> list[dict[str, Any]]:
        """Stable sort by timestamp only.

        Python's sort is stable, so events sharing a timestamp keep emission order --
        which is exactly the tiebreak the profiler falls back on.
        """
        return sorted(self.events, key=lambda e: e["timestamp"])


# --------------------------------------------------------------------------
# 1 -- deep linear: 8 sequential steps, objects nested two levels deep
# --------------------------------------------------------------------------

_DEEP_LINEAR_SPEC = """# Feature spec — Managed Booking Flow

## What it does
An eight-step assisted booking flow. The traveller picks an itinerary, books an
appointment slot, fills traveller details, uploads documents, is offered insurance,
pays, and receives a confirmation. Every step is strictly sequential: the product
will not render step N+1 until step N has emitted.

Two steps carry structured sub-objects rather than flat fields. The document scan
result and the payment instrument are each nested two levels deep, because the
upstream services return them that way and the SDK forwards the object verbatim.

## User actions (raw events emitted)
- `itinerary_viewed` — traveller opens an itinerary (`booking_id`, `destination`)
- `slot_selected` — picks an appointment slot (`slot_window`)
- `traveller_details_entered` — completes the personal-details form
- `document_uploaded` — uploads a document; carries a nested scan result
  (`document.kind`, `document.scan.quality_score`, `document.scan.page_count`)
- `insurance_offered` — an insurance add-on is shown (`insurance_tier`)
- `payment_initiated` — payment begins; carries a nested instrument
  (`payment.method`, `payment.card.network`, `payment.card.issuer_country`,
  `payment.amount_minor`)
- `payment_authorized` — the PSP authorises (`auth_latency_ms`)
- `booking_confirmed` — confirmation is issued

## Questions the PM will ask
- Step-through rate for all eight steps, and where the largest single drop sits.
- Does `payment.card.network` predict authorisation success?
- Does a low `document.scan.quality_score` predict abandonment at the next step?
- Authorisation latency by `device_type` and by `destination`.
"""

_SLOT_WINDOWS = ["morning", "afternoon", "evening"]
_DOC_KINDS = ["passport", "photo", "bank_statement"]
_CARD_NETWORKS = ["visa", "mastercard", "rupay", "amex"]
_INSURANCE_TIERS = ["none", "basic", "premium"]
_DESTINATIONS = ["FR", "GB", "US", "AE", "SG"]

_DEEP_LINEAR_STEPS = [
    "itinerary_viewed",
    "slot_selected",
    "traveller_details_entered",
    "document_uploaded",
    "insurance_offered",
    "payment_initiated",
    "payment_authorized",
    "booking_confirmed",
]
# Survival at each step. Strictly sequential, so a drop is terminal.
_DEEP_LINEAR_SURVIVAL = [1.00, 0.88, 0.79, 0.71, 0.66, 0.58, 0.50, 0.47]


def build_deep_linear() -> Topology:
    rng = _rng("deep_linear")
    ids = _Ids("deep_linear")
    events: list[dict[str, Any]] = []

    n_users = 340
    clock = 0.0
    for u in range(n_users):
        user_id = ids.next("user")
        actor = _Actor.draw(rng)
        for _ in range(rng.choice([1, 1, 1, 2, 2, 3])):     # a user may book more than once
            booking_id = ids.next("booking")
            destination = rng.choice(_DESTINATIONS)
            reached = 1
            r = rng.random()
            for i in range(1, len(_DEEP_LINEAR_STEPS)):
                if r <= _DEEP_LINEAR_SURVIVAL[i]:
                    reached = i + 1
                else:
                    break
            clock += rng.uniform(20, 90)
            t = clock
            for i in range(reached):
                step = _DEEP_LINEAR_STEPS[i]
                t += rng.uniform(4, 120)
                ev: dict[str, Any] = {
                    "event": step,
                    "id": ids.next("row"),
                    "timestamp": _ts(t),
                    **actor.as_dict(),
                    "user_id": user_id,
                    "booking_id": booking_id,
                    "destination": destination,
                }
                if step == "slot_selected":
                    ev["slot_window"] = rng.choice(_SLOT_WINDOWS)
                elif step == "document_uploaded":
                    # TWO levels: document.scan.quality_score
                    ev["document"] = {
                        "kind": rng.choice(_DOC_KINDS),
                        "scan": {
                            "quality_score": round(rng.uniform(0.35, 0.99), 3),
                            "page_count": rng.choice([1, 1, 2, 3]),
                        },
                    }
                elif step == "insurance_offered":
                    ev["insurance_tier"] = rng.choice(_INSURANCE_TIERS)
                elif step == "payment_initiated":
                    # TWO levels: payment.card.network
                    ev["payment"] = {
                        "method": rng.choice(["card", "card", "upi", "netbanking"]),
                        "card": {
                            "network": rng.choice(_CARD_NETWORKS),
                            "issuer_country": rng.choice(["IN", "SG", "AE", "GB"]),
                        },
                        "amount_minor": rng.randrange(180000, 940000, 100),
                    }
                elif step == "payment_authorized":
                    ev["auth_latency_ms"] = rng.randrange(240, 9800)
                events.append(ev)

    return Topology("deep_linear", "Managed Booking Flow", _DEEP_LINEAR_SPEC, events)


# --------------------------------------------------------------------------
# 2 -- double fan-out: parent -> child -> grandchild
# --------------------------------------------------------------------------

_DOUBLE_FANOUT_SPEC = """# Feature spec — Collaborative Trip Boards

## What it does
A traveller opens a shared board (the parent), starts one or more discussion threads
on it (the children), and anyone with the link posts replies to a thread (the
grandchildren). Reactions come from link recipients who may have no account at all.

The fan-out is two levels deep, so there is no single obvious entity key: a board, a
thread and a reply are each a defensible unit of analysis and the right answer depends
on the question being asked.

## User actions (raw events emitted)
- `board_opened` — a member opens a board (`board_id`)
- `thread_created` — a thread is started on the board (`board_id`, `thread_id`, `topic`)
- `thread_published` — the thread becomes visible to link recipients (`visibility`)
- `reply_posted` — a reply lands on a thread (`reply_id`, `reply_kind`)
- `reply_reacted` — a recipient reacts to a reply (`reaction`); carries no account

## Questions the PM will ask
- Threads per board, and replies per thread.
- Which `topic` produces the most replies per thread?
- Reaction rate per reply, split by `reply_kind`.
- What fraction of reactions come from people with no account?
"""

_TOPICS = ["visas", "flights", "stays", "budget", "docs"]
_REPLY_KINDS = ["text", "photo", "link", "poll"]
_REACTIONS = ["like", "love", "question", "flag"]
_VISIBILITY = ["link", "members"]


def build_double_fanout() -> Topology:
    """Board / thread / reply, with `board_id` and `thread_id` forced onto EQUAL
    row coverage and equal event-type counts.

    Coverage parity is not decoration: it pushes the entity-key decision past the two
    criteria that normally settle it, so we find out what the profiler does when its
    primary evidence is exhausted.
    """
    rng = _rng("double_fanout")
    ids = _Ids("double_fanout")
    events: list[dict[str, Any]] = []

    n_boards = 260
    clock = 0.0
    reply_pool: list[tuple[str, str, str, _Actor, float]] = []   # for later reactions

    for _ in range(n_boards):
        board_id = ids.next("board")
        owner = ids.next("user")
        actor = _Actor.draw(rng)
        clock += rng.uniform(30, 200)
        t = clock

        events.append({
            "event": "board_opened",
            "id": ids.next("row"),
            "timestamp": _ts(t),
            **actor.as_dict(),
            "user_id": owner,
            "board_id": board_id,
        })

        for _ in range(rng.choice([1, 1, 2, 2, 3, 4])):
            thread_id = ids.next("thread")
            topic = rng.choice(_TOPICS)
            t += rng.uniform(15, 240)
            events.append({
                "event": "thread_created",
                "id": ids.next("row"),
                "timestamp": _ts(t),
                **actor.as_dict(),
                "user_id": owner,
                "board_id": board_id,
                "thread_id": thread_id,
                "topic": topic,
            })
            if rng.random() > 0.14:
                t += rng.uniform(5, 90)
                events.append({
                    "event": "thread_published",
                    "id": ids.next("row"),
                    "timestamp": _ts(t),
                    **actor.as_dict(),
                    "user_id": owner,
                    "board_id": board_id,
                    "thread_id": thread_id,
                    "topic": topic,
                    "visibility": rng.choice(_VISIBILITY),
                })
                for _ in range(rng.choice([0, 1, 1, 2, 3, 5])):
                    reply_id = ids.next("reply")
                    replier = ids.next("user")
                    r_actor = _Actor.draw(rng)
                    t += rng.uniform(20, 600)
                    events.append({
                        "event": "reply_posted",
                        "id": ids.next("row"),
                        "timestamp": _ts(t),
                        **r_actor.as_dict(),
                        "user_id": replier,
                        "board_id": board_id,
                        "thread_id": thread_id,
                        "reply_id": reply_id,
                        "topic": topic,
                        "reply_kind": rng.choice(_REPLY_KINDS),
                    })
                    reply_pool.append((board_id, thread_id, reply_id, r_actor, t))

    # Reactions: keyed by thread_id + reply_id, NO board_id and NO account id. Exactly
    # as many as there are board_opened rows, so board_id and thread_id end up on the
    # same number of rows and the same number of event types (4 of 5 each).
    n_reactions = n_boards
    rng.shuffle(reply_pool)
    for i in range(n_reactions):
        _b, thread_id, reply_id, r_actor, t0 = reply_pool[i % len(reply_pool)]
        events.append({
            "event": "reply_reacted",
            "id": ids.next("row"),
            "timestamp": _ts(t0 + rng.uniform(30, 3600)),
            **_Actor.draw(rng).as_dict(),
            "thread_id": thread_id,
            "reply_id": reply_id,
            "reaction": rng.choice(_REACTIONS),
        })

    return Topology("double_fanout", "Collaborative Trip Boards", _DOUBLE_FANOUT_SPEC, events)


# --------------------------------------------------------------------------
# 3 -- mutation-heavy: add / remove / reorder against a collection
# --------------------------------------------------------------------------

_MUTATION_SPEC = """# Feature spec — Traveller Basket Editing

## What it does
A basket of add-on services that the traveller edits freely before checkout. Items go
in, come out, and get dragged into a different order, any number of times and in any
order. There is no canonical sequence: `item_removed` regularly precedes `item_added`
for the same basket, and a basket may be checked out with fewer items than were ever
added to it.

The only metric that means anything at basket level is net state — what is actually in
the basket when editing stops. Counting mutation events overstates engagement, and an
ordered funnel over the mutation events measures nothing at all.

## User actions (raw events emitted)
- `basket_created` — an empty basket is opened (`basket_id`)
- `item_added` — an item is added (`item_id`, `item_category`, `items_after`)
- `item_removed` — an item is taken out (`item_id`, `items_after`)
- `item_reordered` — an item is dragged (`position_from`, `position_to`, `items_after`)
- `basket_checked_out` — editing ends and the basket is paid for (`items_after`,
  `basket_value_minor`)

## Questions the PM will ask
- Net items per basket at checkout, not total mutations.
- Churn ratio: removals per addition, and does high churn predict abandonment?
- Which `item_category` is added and then removed most often?
- Do reorders correlate with checkout at all?
"""

_ITEM_CATEGORIES = ["insurance", "transfer", "lounge", "sim", "forex", "photo"]


def build_mutation_heavy() -> Topology:
    rng = _rng("mutation_heavy")
    ids = _Ids("mutation_heavy")
    events: list[dict[str, Any]] = []

    catalogue = [(ids.next("sku"), rng.choice(_ITEM_CATEGORIES)) for _ in range(120)]
    n_baskets = 420
    clock = 0.0

    for _ in range(n_baskets):
        basket_id = ids.next("basket")
        user_id = ids.next("user")
        actor = _Actor.draw(rng)
        clock += rng.uniform(20, 140)
        t = clock

        events.append({
            "event": "basket_created",
            "id": ids.next("row"),
            "timestamp": _ts(t),
            **actor.as_dict(),
            "user_id": user_id,
            "basket_id": basket_id,
            "items_after": 0,
        })

        held: list[tuple[str, str]] = []
        for _ in range(rng.randint(3, 12)):
            t += rng.uniform(3, 45)
            # An empty basket can only be added to; otherwise all three are live, which
            # is what makes pairwise precedence between them near 50/50.
            op = "item_added" if not held else rng.choices(
                ["item_added", "item_removed", "item_reordered"], weights=[5, 3, 2]
            )[0]
            if op == "item_added":
                sku, cat = rng.choice(catalogue)
                held.append((sku, cat))
                events.append({
                    "event": "item_added",
                    "id": ids.next("row"),
                    "timestamp": _ts(t),
                    **actor.as_dict(),
                    "user_id": user_id,
                    "basket_id": basket_id,
                    "item_id": sku,
                    "item_category": cat,
                    "items_after": len(held),
                })
            elif op == "item_removed":
                k = rng.randrange(len(held))
                sku, cat = held.pop(k)
                events.append({
                    "event": "item_removed",
                    "id": ids.next("row"),
                    "timestamp": _ts(t),
                    **actor.as_dict(),
                    "user_id": user_id,
                    "basket_id": basket_id,
                    "item_id": sku,
                    "item_category": cat,
                    "items_after": len(held),
                })
            else:
                a = rng.randrange(len(held))
                b = rng.randrange(len(held))
                sku, cat = held[a]
                held.insert(b, held.pop(a))
                events.append({
                    "event": "item_reordered",
                    "id": ids.next("row"),
                    "timestamp": _ts(t),
                    **actor.as_dict(),
                    "user_id": user_id,
                    "basket_id": basket_id,
                    "item_id": sku,
                    "item_category": cat,
                    "position_from": a,
                    "position_to": b,
                    "items_after": len(held),
                })

        if held and rng.random() < 0.62:
            t += rng.uniform(10, 300)
            events.append({
                "event": "basket_checked_out",
                "id": ids.next("row"),
                "timestamp": _ts(t),
                **actor.as_dict(),
                "user_id": user_id,
                "basket_id": basket_id,
                "items_after": len(held),
                "basket_value_minor": sum(rng.randrange(9900, 240000, 100) for _ in held),
            })

    return Topology("mutation_heavy", "Traveller Basket Editing", _MUTATION_SPEC, events)


# --------------------------------------------------------------------------
# 4 -- sparse envelope: 40% of rows carry no actor and no device/geo
# --------------------------------------------------------------------------

_SPARSE_SPEC = """# Feature spec — Airport Kiosk Assist

## What it does
A self-service kiosk at the airport. A traveller can use it entirely anonymously —
scan a document, read the result, walk away — or sign in partway through and have the
visit attached to their account.

Because the kiosk is a shared physical device, the SDK cannot fill the usual envelope
for an anonymous visit: there is no signed-in account, and the device and geo fields
are suppressed by the kiosk operator's privacy configuration. Roughly two rows in five
therefore arrive with an empty envelope. Some of those rows omit the account key
altogether and some send it as an empty string; both are anonymous.

## User actions (raw events emitted)
- `kiosk_woken` — the kiosk leaves standby (`visit_id`, `kiosk_lane`)
- `scan_started` — a document is placed on the scanner (`scan_kind`)
- `scan_completed` — the scan resolves (`scan_result`, `scan_duration_ms`)
- `assist_requested` — the traveller calls a human agent (`assist_reason`)
- `visit_closed` — the visit ends (`close_reason`)

## Questions the PM will ask
- Distinct travellers assisted per day — counting only real accounts.
- Scan success rate, split by `scan_kind` and by `kiosk_lane`.
- What share of visits are fully anonymous, and do they convert differently?
- Median scan duration, and does calling an agent follow a slow scan?
"""

_LANES = ["lane-a", "lane-b", "lane-c"]
_SCAN_KINDS = ["passport", "boarding_pass", "id_card"]
_SCAN_RESULTS = ["ok", "ok", "ok", "blurred", "unsupported"]
_ASSIST_REASONS = ["scan_failed", "language", "payment", "other"]
_CLOSE_REASONS = ["completed", "timeout", "abandoned"]

_SPARSE_STEPS = ["kiosk_woken", "scan_started", "scan_completed", "assist_requested", "visit_closed"]


def build_sparse_envelope() -> Topology:
    """40% anonymous rows, split between an ABSENT key and an EMPTY-STRING key.

    Both land in a non-Nullable String column as '' after load, so a bare
    uniq(user_id) reports one phantom traveller. Splitting the 40% across the two
    encodings means the profiler cannot get the right answer from null_frac alone.
    """
    rng = _rng("sparse_envelope")
    ids = _Ids("sparse_envelope")
    events: list[dict[str, Any]] = []

    n_visits = 620
    clock = 0.0
    for _ in range(n_visits):
        visit_id = ids.next("visit")
        actor = _Actor.draw(rng)
        lane = rng.choice(_LANES)
        # A visit is anonymous or not; the envelope follows the visit, not the row.
        anon = rng.random() < 0.40
        # Within the anonymous 40%, split the encoding of "no account".
        omit_key = anon and rng.random() < 0.625
        user_id = "" if anon else ids.next("user")

        clock += rng.uniform(15, 120)
        t = clock
        n_steps = rng.choices([1, 2, 3, 4, 5], weights=[6, 14, 40, 12, 28])[0]
        for i in range(n_steps):
            step = _SPARSE_STEPS[i]
            t += rng.uniform(2, 60)
            ev: dict[str, Any] = {
                "event": step,
                "id": ids.next("row"),
                "timestamp": _ts(t),
                "app_version": actor.app_version,
                "client_lib": "kiosk-embedded",
                "visit_id": visit_id,
                "kiosk_lane": lane,
            }
            if not anon:
                ev.update({
                    "device_type": actor.device_type,
                    "os": actor.os,
                    "geoip_country_code": actor.geoip_country_code,
                    "city": actor.city,
                })
            if not omit_key:
                ev["user_id"] = user_id
            if step == "scan_started":
                ev["scan_kind"] = rng.choice(_SCAN_KINDS)
            elif step == "scan_completed":
                ev["scan_result"] = rng.choice(_SCAN_RESULTS)
                ev["scan_duration_ms"] = rng.randrange(400, 12000)
            elif step == "assist_requested":
                ev["assist_reason"] = rng.choice(_ASSIST_REASONS)
            elif step == "visit_closed":
                ev["close_reason"] = rng.choice(_CLOSE_REASONS)
            events.append(ev)

    return Topology("sparse_envelope", "Airport Kiosk Assist", _SPARSE_SPEC, events)


# --------------------------------------------------------------------------
# registry + IO
# --------------------------------------------------------------------------

BUILDERS: dict[str, Callable[[], Topology]] = {
    "deep_linear": build_deep_linear,
    "double_fanout": build_double_fanout,
    "mutation_heavy": build_mutation_heavy,
    "sparse_envelope": build_sparse_envelope,
}


def build(name: str) -> Topology:
    if name not in BUILDERS:
        raise KeyError(f"unknown topology {name!r}; known: {', '.join(BUILDERS)}")
    return BUILDERS[name]()


def render(topo: Topology) -> tuple[str, bytes]:
    """(spec.md text, events.ndjson bytes). Pure -- no filesystem, for the check mode."""
    lines = [orjson.dumps(e) for e in topo.sorted_events()]
    return topo.spec_md, b"\n".join(lines) + b"\n"


def write(topo: Topology, root: Path = DEFAULT_OUT) -> dict[str, Path]:
    d = root / topo.name
    d.mkdir(parents=True, exist_ok=True)
    md, nd = render(topo)
    (d / "spec.md").write_text(md, encoding="utf-8")
    (d / "events.ndjson").write_bytes(nd)
    return {"dir": d, "spec": d / "spec.md", "events": d / "events.ndjson"}


def digest(topo: Topology) -> str:
    md, nd = render(topo)
    return hashlib.sha256(md.encode() + nd).hexdigest()[:16]


def _names(only: Iterable[str] | None) -> list[str]:
    return list(only) if only else list(BUILDERS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", nargs="*", choices=sorted(BUILDERS), default=None)
    ap.add_argument("--check", action="store_true",
                    help="rebuild twice and diff against disk; proves the corpus is reproducible")
    args = ap.parse_args(argv)

    rc = 0
    for name in _names(args.only):
        topo = build(name)
        if args.check:
            again = digest(build(name))
            here = digest(topo)
            d = args.out / name
            on_disk = ""
            if (d / "spec.md").exists() and (d / "events.ndjson").exists():
                on_disk = hashlib.sha256(
                    (d / "spec.md").read_bytes() + (d / "events.ndjson").read_bytes()
                ).hexdigest()[:16]
            ok = (here == again) and (on_disk == here)
            rc |= 0 if ok else 1
            print(f"{'ok  ' if ok else 'FAIL'} {name:<16} rebuild={here} again={again} "
                  f"disk={on_disk or '(missing)'}")
            continue
        paths = write(topo, args.out)
        n = len(topo.events)
        etypes = len({e["event"] for e in topo.events})
        print(f"{name:<16} {n:>6,} events  {etypes} event types  sha={digest(topo)}  "
              f"-> {paths['dir']}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
