# SonyLIV track — What to submit at code freeze

Your submission is scored on the event's standard 6-criteria rubric (ClickHouse &
OSS Stack 25% · Problem Fit 20% · Technical Implementation 20% · Innovation 20% ·
Scalability & Impact 10% · Presentation 5%). The items below are the **evidence the
judges need** to score those criteria for this track. Missing evidence can't be
scored.

Track problem statement:
[PROBLEM_STATEMENT.md](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/SonyLiv/PROBLEM_STATEMENT.md)
— *"Counting the crowd: foreground-only concurrency at streaming scale."*

In addition to the [common submission requirements](README.md#how-to-submit), SonyLIV
teams must include the following.

## 1. Concurrency curve (mandatory)

A basic **concurrency curve**: concurrent viewers/sessions plotted over time, computed
from the dataset in the problem statement.

- Show at least one full window of interest (e.g. a match/event or a day of traffic),
  with visible peaks and ramps.
- Include the ClickHouse query (or queries) used to compute it — judges will look at
  how you model concurrency, not just the chart.
- Render it in your product UI or dashboard; a static screenshot in the README alone
  is not sufficient if your product has a UI.

## 2. Dataset filters (mandatory)

Your product must expose **filters matching the dimensions available in the dataset**
from the problem statement (for example: content title/asset, device/platform, geo/region,
subscription tier — use whatever dimensions the dataset actually provides).

- Filters must apply to the concurrency curve as well as any other views you build.
- Document in your README which dataset columns back each filter.

## 3. Everything else

All common requirements from the [root README](README.md#how-to-submit) apply:
source code, README with hosted demo link, architecture, recorded demo video
(2–3 min), and pitch deck PDF. Your demo video and hosted demo should show the
concurrency curve and filters working live.

## Notes

- You have creative liberty with the technical architecture, UI/UX of the product
  (can be lean also), final product use case and extra features built.
