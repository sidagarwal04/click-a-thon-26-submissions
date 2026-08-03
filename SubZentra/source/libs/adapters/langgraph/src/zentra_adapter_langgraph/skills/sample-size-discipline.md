---
name: Sample size discipline
applies_to: cube_analyst, evaluator
---

A total tells you what moved; the count behind it tells you whether the
movement means anything. Where the catalog offers a measure that counts
records, include it alongside the measures you were actually asked about — a
result that does not carry its own sample cannot be trusted at any confidence.

`sample_size` is how many underlying records your figures rest on, not how many
rows came back. Two monthly totals covering four orders each is a sample_size
of eight. Read it from a count measure in the result where one is present; if
the result genuinely does not say, report 0 rather than guessing.

Count independently. Where another agent has reported a sample size, arriving
at the same number by your own route is the point; copying theirs establishes
nothing.
