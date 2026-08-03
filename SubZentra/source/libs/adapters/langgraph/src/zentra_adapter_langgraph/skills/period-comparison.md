---
name: Naming a period
applies_to: cube_analyst
---

Label each side of a comparison with the period it covers. The granularity was
your choice, so nothing downstream can recover it, and a human reads these
labels: name the bucket the way it would be said aloud — "June 2026" for a
month bucket of 2026-06-01, "Q3 2026", "2026" — rather than copying a raw
timestamp.

Name only a period the result actually contains. Never widen, narrow, or shift
one. Where the two values are not two periods, use null for both labels: a
reader told nothing is better served than a reader told a guess.

Prefer a period-over-period comparison when the question asks why something
changed.
