"""The deck's content and styling. 15 landscape slides, 16:9.

Palette is lifted verbatim from the dashboard's dark theme
(frontend/src/styles/variables-final.css) so the deck reads as the same product, not an
approximation of it.
"""
from __future__ import annotations

CSS = """
@page { size: 1280px 720px; margin: 0; }

:root {
  --canvas:  #0D0F13;
  --surface: #12141B;
  --raised:  #181B23;
  --line:    #262A34;
  --ink:     #D3D5D9;
  --muted:   #888B97;
  --faint:   #5A5E6B;
  --accent:  #DCCC51;
  --blue:    #4274D5;
  --good:    #2F9855;
  --bad:     #C4514F;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { background: var(--canvas); }
body { font-family: var(--sans); -webkit-font-smoothing: antialiased; }

.slide {
  width: 1280px; height: 720px;
  background: var(--canvas);
  color: var(--ink);
  padding: 62px 76px;
  position: relative;
  overflow: hidden;
  page-break-after: always;
  display: flex; flex-direction: column;
}
.slide:last-child { page-break-after: auto; }

/* hairline top accent — the only ornament, carries the brand colour */
.slide::before {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, var(--accent) 0%, var(--accent) 22%, var(--line) 22%);
}

.num {
  position: absolute; right: 40px; bottom: 30px;
  font-family: var(--mono); font-size: 12px; color: #3E424C; letter-spacing: .06em;
}

.eyebrow {
  font-family: var(--mono); font-size: 12px; letter-spacing: .18em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 20px;
}
.body > .eyebrow { margin-bottom: -13px; }  /* sits tight to its heading, not a gap away */
h1 { font-size: 58px; font-weight: 700; letter-spacing: -.03em; line-height: 1.04; }
h2 { font-size: 40px; font-weight: 700; letter-spacing: -.025em; line-height: 1.1; margin-bottom: 8px; }
h3 { font-size: 19px; font-weight: 650; letter-spacing: -.01em; margin-bottom: 8px; }
p  { font-size: 18px; line-height: 1.55; color: var(--muted); max-width: 66ch; }
p.lead { font-size: 23px; line-height: 1.45; color: var(--ink); max-width: 60ch; }
strong { color: var(--ink); font-weight: 650; }
em { color: var(--accent); font-style: normal; }

/* content is centred in the slide rather than stacked from the top — otherwise every
   text-only slide leaves a dead band across the bottom third */
.body { flex: 1; display: flex; flex-direction: column; justify-content: center;
        gap: 22px; margin-top: 8px; }
.row  { display: flex; gap: 26px; }
.col  { flex: 1; min-width: 0; }

.card {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 10px; padding: 22px 24px;
}
.card.accent { border-color: #3A3722; background: #16160F; }
.card.bad    { border-color: #3A2624; background: #170F0F; }
.card.good   { border-color: #1E3527; background: #0E1611; }

.mono { font-family: var(--mono); }
code  { font-family: var(--mono); font-size: .92em; color: var(--accent); }

pre {
  font-family: var(--mono); font-size: 14.5px; line-height: 1.75;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 10px; padding: 20px 24px; color: var(--muted);
  overflow: hidden; white-space: pre;
}
pre b { color: var(--ink); font-weight: 600; }
pre .a { color: var(--accent); }
pre .g { color: var(--good); }
pre .r { color: var(--bad); }
pre .d { color: #4A4E58; }

table { border-collapse: collapse; width: 100%; font-size: 16px; }
th {
  text-align: left; font-family: var(--mono); font-size: 11px; letter-spacing: .12em;
  text-transform: uppercase; color: var(--faint); font-weight: 600;
  padding: 0 14px 10px 0; border-bottom: 1px solid var(--line);
}
td { padding: 11px 14px 11px 0; border-bottom: 1px solid #1B1E26; color: var(--muted); }
td.k { color: var(--ink); font-weight: 600; }
tr:last-child td { border-bottom: 0; }

.shot {
  width: 100%; border-radius: 10px; border: 1px solid var(--line);
  display: block; object-fit: cover; object-position: top left;
}

.kpi { display: flex; gap: 44px; }
.kpi div span { display: block; }
.kpi .v { font-size: 42px; font-weight: 700; color: var(--accent); letter-spacing: -.03em; line-height: 1; }
.kpi .l { font-family: var(--mono); font-size: 11.5px; letter-spacing: .1em;
          text-transform: uppercase; color: var(--faint); margin-top: 9px; }

/* Architecture diagram. Drawn with borders rather than box-drawing characters: the corner
   glyphs fall back to a font with different metrics and the boxes render as broken brackets. */
.dia { display: flex; flex-direction: column; align-items: center; gap: 0; }
.box {
  background: var(--raised); border: 1px solid #2E3340; border-radius: 8px;
  padding: 13px 20px; font-family: var(--mono); font-size: 13.5px; color: var(--muted);
  display: flex; align-items: center; gap: 18px;
}
.box .t { color: var(--ink); font-weight: 700; letter-spacing: .06em; font-size: 12px; }
.conn { width: 1px; height: 34px; background: #333846; position: relative; }
.conn::after {
  content: ""; position: absolute; bottom: 0; left: -3.5px;
  border-left: 4px solid transparent; border-right: 4px solid transparent;
  border-top: 6px solid #333846;
}
.conn > span {
  position: absolute; left: 15px; top: 9px; white-space: nowrap;
  font-family: var(--mono); font-size: 11.5px; color: var(--faint); line-height: 1;
}
.stage { display: flex; gap: 12px; }
.stage > div {
  background: var(--surface); border: 1px solid #2E3340; border-radius: 7px;
  padding: 11px 17px; text-align: center; min-width: 178px;
}
.stage b { display: block; font-family: var(--mono); font-size: 12px; letter-spacing: .07em;
           color: var(--accent); margin-bottom: 5px; }
.stage i { font-style: normal; font-size: 13.5px; color: var(--muted); }

ul { list-style: none; display: flex; flex-direction: column; gap: 13px; }
li { font-size: 17.5px; line-height: 1.5; color: var(--muted); padding-left: 20px; position: relative; }
li::before { content: "—"; position: absolute; left: 0; color: var(--accent); }
"""


def _slide(n: int, eyebrow: str, body: str, total: int = 15) -> str:
    # eyebrow lives inside .body so it travels with the heading when the block centres
    return (f'<section class="slide">'
            f'<div class="body"><div class="eyebrow">{eyebrow}</div>{body}</div>'
            f'<div class="num">{n:02d} / {total}</div></section>')


def render(*, dashboard: str, replay: str, trace: str, depth: str, chat: str) -> str:
    S: list[str] = []

    # 01 — title
    S.append(
        '<section class="slide" style="justify-content:center">'
        '<div class="eyebrow" style="margin-top:auto">Click-a-thon 2026 · InMobi track</div>'
        '<h1>Automated<br>Root-Cause Analyst</h1>'
        '<p class="lead" style="margin-top:26px">A metric moved. It tells you <em>which segment</em> '
        'did it — in seconds.</p>'
        '<div style="margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end">'
        '<div class="mono" style="font-size:14px;color:var(--faint);line-height:1.9">'
        'Jalagaara Gang<br>'
        '<span style="color:var(--muted)">Rohan M Rao · Ankith Dinakar · Shashank · Shreyas Bharadhwaj</span>'
        '</div>'
        '<div class="mono" style="font-size:14px;color:var(--accent);text-align:right">'
        'clickathon.kangasys.com</div>'
        '</div><div class="num">01 / 15</div></section>')

    # 02 — problem
    S.append(_slide(2, "The problem", """
      <h2>Alerts tell you <em>what</em>. Nobody tells you <em>why</em>.</h2>
      <p>Revenue drops four percent. The dashboard turns red. Then an analyst starts slicing —
      by country, by device, by OS, by app, by advertiser — comparing each cut against a
      baseline, by hand, for hours.</p>
      <div class="row" style="margin-top:6px">
        <div class="card col"><div class="kpi"><div>
          <span class="v">9M</span><span class="l">ad events</span></div></div>
          <p style="font-size:15.5px;margin-top:14px">Five weeks of requests, fills,
          impressions, clicks and revenue.</p></div>
        <div class="card col"><div class="kpi"><div>
          <span class="v">11</span><span class="l">dimensions</span></div></div>
          <p style="font-size:15.5px;margin-top:14px">Region, country, OS, device, format,
          category, tier, vertical, campaign, app, advertiser.</p></div>
        <div class="card col accent"><div class="kpi"><div>
          <span class="v">10<sup style="font-size:20px">4</sup>+</span>
          <span class="l">segment combinations</span></div></div>
          <p style="font-size:15.5px;margin-top:14px">The bottleneck was never the data.
          It was human attention.</p></div>
      </div>"""))

    # 03 — what we built  (dashboard shot)
    S.append(_slide(3, "What we built", """
      <h2>Ask in plain English. Get the segment, and the evidence.</h2>
      <div class="row" style="flex:1;align-items:flex-start">
        <div style="flex:0 0 380px;display:flex;flex-direction:column;gap:14px">
          <p style="font-size:16.5px">Three stages, all computed in ClickHouse:</p>
          <ul style="gap:11px">
            <li><strong>Detect</strong> — is this move real, or ordinary noise?</li>
            <li><strong>Decompose</strong> — revenue = requests × fill rate × eCPM.
                Which factor moved?</li>
            <li><strong>Drill down</strong> — which segment inside it is responsible,
                and what was cleared?</li>
          </ul>
          <div class="card good" style="padding:15px 18px">
            <p style="font-size:15px;color:var(--ink)">Live on real data, with the diagnosis,
            the factor split and the ruled-out list all on one screen.</p></div>
        </div>
        <div class="col"><img class="shot" src="IMG_DASH" style="height:405px"></div>
      </div>""").replace("IMG_DASH", dashboard))

    # 04 — the obvious approach fails
    S.append(_slide(4, "The insight · 1 of 3", """
      <h2>The obvious way to rank segments is <em>wrong</em>.</h2>
      <p>Rank each segment by how much of the gap it explains, descend into the biggest,
      repeat. It is the first thing anyone writes — and it fails, for a reason that is not
      obvious until you measure it.</p>
      <div class="row" style="margin-top:4px">
        <div class="card bad col">
          <h3 style="color:var(--bad)">What it returns</h3>
          <pre style="background:transparent;border:0;padding:0;font-size:14px">
<span class="d">true cause  </span> <b>one condition</b>

<span class="d">what it says</span> <b>one condition</b>
             <span class="r">AND the busiest tier</span>
             <span class="r">AND the busiest region</span>
             <span class="r">AND the busiest device</span></pre>
          <p style="font-size:15.5px;margin-top:12px">Three extra conditions. Each explains
          nothing, and each one is wrong.</p>
        </div>
        <div class="card col">
          <h3>Why</h3>
          <p style="font-size:16px">For a <strong>uniform</strong> effect, the share of the gap a
          segment explains is simply <strong>its share of traffic</strong>.</p>
          <p style="font-size:16px;margin-top:12px">So the ranking does not find the culprit.
          It finds <em>the biggest slice</em> — then the biggest slice inside that, and keeps
          going until it runs out of dimensions.</p>
        </div>
      </div>"""))

    # 05 — lift
    S.append(_slide(5, "The insight · 2 of 3", """
      <h2>Divide by size. Everything falls out.</h2>
      <p>Score each segment by a counterfactual — restore its component sums to baseline and
      measure how much of the gap closes — then divide that by the segment's share of the
      metric's own volume.</p>
      <pre style="font-size:19px;text-align:center;padding:26px">
<span class="a">lift</span>  =   gap this segment closes   <span class="d">÷</span>   its share of the volume</pre>
      <div class="row">
        <div class="card col">
          <div class="kpi"><div><span class="v" style="color:var(--muted)">≈ 1</span>
          <span class="l">merely large</span></div></div>
          <p style="font-size:16px;margin-top:12px">Closes about its own share. Big, innocent,
          and correctly ignored.</p></div>
        <div class="card col accent">
          <div class="kpi"><div><span class="v">≫ 1</span>
          <span class="l">the culprit</span></div></div>
          <p style="font-size:16px;margin-top:12px">Closes far more than its size explains.
          The only kind of segment worth naming.</p></div>
      </div>
      <p style="font-size:16px">Descend into the disproportionate one, add it to the filter,
      recurse. Stop when nothing left is both material and disproportionate.</p>"""))

    # 06 — proof
    S.append(_slide(6, "The insight · 3 of 3", """
      <h2>We implemented both, and measured.</h2>
      <p>Same engine, same data, same windows — only the ranking rule changed.</p>
      <div class="row" style="margin-top:8px">
        <div class="card bad col" style="text-align:center;padding:30px">
          <div class="l mono" style="font-size:11.5px;letter-spacing:.12em;color:var(--faint);
               text-transform:uppercase">Rank by contribution</div>
          <div style="font-size:64px;font-weight:700;color:var(--bad);letter-spacing:-.04em;
               margin:14px 0 6px">none</div>
          <p style="font-size:15.5px;margin:0 auto">of the known anomalies localized correctly</p>
        </div>
        <div class="card good col" style="text-align:center;padding:30px">
          <div class="l mono" style="font-size:11.5px;letter-spacing:.12em;color:var(--faint);
               text-transform:uppercase">Rank by lift</div>
          <div style="font-size:64px;font-weight:700;color:var(--good);letter-spacing:-.04em;
               margin:14px 0 6px">all</div>
          <p style="font-size:15.5px;margin:0 auto">including the hard cases that follow</p>
        </div>
      </div>
      <p style="font-size:16.5px">Both cases are pinned as regression tests — a false positive
      now fails the build like any other bug.</p>"""))

    # 07 — hard case: blame nobody  (replay shot)
    S.append(_slide(7, "Hard case · 1 of 2", """
      <h2>Sometimes the right answer is <em>nobody</em>.</h2>
      <div class="row" style="flex:1;align-items:flex-start">
        <div style="flex:0 0 400px;display:flex;flex-direction:column;gap:14px">
          <p style="font-size:16.5px">When a metric drops uniformly across every region and every
          hour, there is no guilty segment. Naming one is a <strong>false positive</strong> — and
          a confident, specific, wrong answer is worse than no answer.</p>
          <div class="card" style="padding:16px 18px">
            <p style="font-size:15.5px;color:var(--ink)">The stop criterion catches this by
            construction: nothing is disproportionate, so the search stops at the population and
            reports the move without a culprit.</p></div>
          <p style="font-size:15.5px">The system also shows its working — every step that led to
          the verdict, replayable.</p>
        </div>
        <div class="col"><img class="shot" src="IMG_REPLAY" style="height:410px;object-fit:contain;background:var(--surface)"></div>
      </div>""").replace("IMG_REPLAY", replay))

    # 08 — hard case: intersection
    S.append(_slide(8, "Hard case · 2 of 2", """
      <h2>Some causes exist only at an <em>intersection</em>.</h2>
      <p>A segment can look unremarkable on every dimension taken alone, and still be badly
      broken where two of them meet.</p>
      <pre style="font-size:17px;padding:26px">
  <span class="d">scanning one dimension at a time</span>

  os_version                     <span class="d">small move   — under the threshold</span>
  region                         <span class="d">small move   — under the threshold</span>
  <span class="d">→ nothing found</span>

  <span class="d">scanning the intersection</span>

  <b>region</b> <span class="d">AND</span> <b>os_version</b>            <span class="r">fill rate roughly halved</span></pre>
      <p style="font-size:16.5px">A single-dimension scan is <strong>structurally blind</strong>
      to this class of anomaly — averaging over everyone else dilutes it below any sensible
      floor. The search descends through combinations for exactly this reason.</p>"""))

    # 09 — architecture
    S.append(_slide(9, "Architecture", """
      <h2>ClickHouse is the detective. The LLM is the journalist.</h2>
      <div class="dia">
        <div class="box"><span class="t">API</span>
          <span>/investigate &nbsp; /narrate &nbsp; /scan &nbsp; /v1/chat/completions</span></div>
        <div class="conn"><span>browser &nbsp;·&nbsp; dashboard &nbsp;·&nbsp; LibreChat</span></div>
        <div class="mono" style="font-size:11.5px;letter-spacing:.14em;color:var(--faint);
             margin:2px 0 10px">RCA ENGINE</div>
        <div class="stage">
          <div><b>1 · DETECTION</b><i>did it move?</i></div>
          <div><b>2 · DECOMPOSITION</b><i>which factor?</i></div>
          <div><b>3 · DRILL-DOWN</b><i>which segment?</i></div>
        </div>
        <div class="conn"><span>every stage is SQL</span></div>
        <div class="box" style="border-color:#3A3722">
          <span class="t" style="color:var(--accent)">CLICKHOUSE</span>
          <span>events &nbsp;·&nbsp; rollup &nbsp;·&nbsp; evidence</span></div>
        <div class="conn"><span>bundle in, prose out</span></div>
        <div class="box"><span class="t">NARRATOR</span>
          <span>writes sentences · guardrail verifies every number</span></div>
        <div class="conn"><span style="color:var(--accent)">one Langfuse trace &nbsp;·&nbsp; one span per SQL statement</span></div>
      </div>
      <p style="font-size:15.5px;margin:0 auto;text-align:center">Results are written back into
      ClickHouse — investigation history is itself queryable in SQL.</p>"""))

    # 10 — where the analysis runs (trace shot)
    S.append(_slide(10, "Proof · where the analysis runs", """
      <h2>Not a claim. A trace.</h2>
      <div class="row" style="flex:1;align-items:flex-start">
        <div style="flex:0 0 356px;display:flex;flex-direction:column;gap:13px">
          <p style="font-size:16.5px">Every SQL statement is a span, nested under the
          investigation automatically. The span tree <em>is</em> the pipeline:</p>
          <div class="card mono" style="padding:16px 20px;font-size:14px">
            <div style="color:var(--ink);font-weight:600">investigation:fill_rate</div>
            <div style="border-left:1px solid #333846;margin:7px 0 0 7px;padding:2px 0 2px 15px;
                 display:flex;flex-direction:column;gap:6px;color:var(--accent)">
              <span>detect</span><span>decompose</span><span>drilldown</span></div>
          </div>
          <p style="font-size:15.5px">Open any span and the ClickHouse query that produced the
          number is right there, with its result.</p>
          <div class="card accent" style="padding:14px 17px">
            <p style="font-size:15px;color:var(--ink)">The LLM has no database access and
            performs no arithmetic.</p></div>
        </div>
        <div class="col"><img class="shot" src="IMG_TRACE" style="height:412px;object-fit:contain;background:var(--surface)"></div>
      </div>""").replace("IMG_TRACE", trace))

    # 11 — depth / ruled out (depth shot)
    S.append(_slide(11, "Proof · what was ruled out", """
      <h2>Every dimension checked. Then it stops.</h2>
      <div class="row" style="flex:1;align-items:flex-start">
        <div style="flex:0 0 356px;display:flex;flex-direction:column;gap:13px">
          <p style="font-size:16.5px">At each depth the engine scores <strong>every value of
          every dimension</strong> — region, country, OS, device, format, category, tier,
          vertical, campaign type, app, advertiser.</p>
          <p style="font-size:16.5px">Then <code>depth-1:stop</code>: nothing left is both
          material and disproportionate, so the search ends rather than inventing depth.</p>
          <div class="card good" style="padding:14px 17px">
            <p style="font-size:15px;color:var(--ink)">The ruled-out list is not written by the
            model. It is what the search actually examined and cleared.</p></div>
        </div>
        <div class="col"><img class="shot" src="IMG_DEPTH" style="height:412px;object-fit:contain;background:var(--surface)"></div>
      </div>""").replace("IMG_DEPTH", depth))

    # 12 — detection
    S.append(_slide(12, "Detection", """
      <h2>Three detectors. Thresholds learned, not guessed.</h2>
      <table>
        <tr><th style="width:190px">Detector</th><th>Baseline</th><th style="width:290px">Strength</th></tr>
        <tr><td class="k mono">robust_z</td><td>Same weekday and hour, trailing weeks — median centre, MAD spread</td><td>Deterministic, fully traceable</td></tr>
        <tr><td class="k mono">seasonal_ml</td><td>Per weekday × hour profile built from all history, scored on residuals</td><td>Pools hundreds of points, far steadier</td></tr>
        <tr><td class="k mono">isolation_forest</td><td>scikit-learn over a per-hour feature vector</td><td>Catches unusual metric <em>combinations</em></td></tr>
      </table>
      <div class="row" style="margin-top:2px">
        <div class="card col accent">
          <h3>Calibrated per metric</h3>
          <p style="font-size:16px">A ratio over millions of requests is stable — a small move is
          real. One over a few thousand clicks swings wildly — the same move is noise. Each
          metric's floor is measured from its own volatility, so one shared threshold cannot
          drown the system in false positives.</p></div>
        <div class="card col">
          <h3>Every factor, not just revenue</h3>
          <p style="font-size:16px">A regression inside one factor can be masked by growth in
          another, leaving the headline metric flat while something is genuinely broken
          underneath. Revenue-only detection never sees it.</p></div>
      </div>"""))

    # 13 — trust
    S.append(_slide(13, "Trust", """
      <h2>Every number reproducible. The model cannot invent one.</h2>
      <div class="row" style="flex:1">
        <div class="col" style="display:flex;flex-direction:column;gap:16px">
          <div class="card">
            <h3>The bundle carries its own receipts</h3>
            <p style="font-size:16px">Each investigation stores the anomaly, the factor split,
            the drill-down path, the ruled-out list — and <code>queries[]</code>, the SQL behind
            every figure. Any number can be recomputed independently.</p></div>
          <div class="card good">
            <h3>Deterministic by construction</h3>
            <p style="font-size:16px"><code>/investigate</code> has no LLM in the path. Call it
            twice, diff the result — same input, same bundle.</p></div>
        </div>
        <div class="col">
          <div class="card bad" style="height:100%">
            <h3 style="color:var(--bad)">The guardrail</h3>
            <p style="font-size:16px">Every number in the prose is extracted and checked against
            the evidence. Anything absent is rejected.</p>
            <pre style="background:transparent;border:0;padding:14px 0 0;font-size:14px">
<span class="g">✓</span>  a figure that appears in the bundle
<span class="g">✓</span>  the same figure, sensibly rounded
<span class="r">✗</span>  a figure that appears nowhere
<span class="r">✗</span>  a real figure wearing invented units</pre>
            <p style="font-size:15.5px;margin-top:12px">That last one matters: a genuine number
            restated with an added currency symbol or scale suffix passes a naive digit check
            while overstating the value by orders of magnitude.</p>
            <p style="font-size:15.5px;margin-top:10px">The verdict is stored on the bundle, so a
            failed check is <strong>visible</strong>, not silent.</p>
          </div>
        </div>
      </div>"""))

    # 14 — unseen incident (chat shot)
    S.append(_slide(14, "Built for the unseen incident", """
      <h2>Point it at a window it has never seen.</h2>
      <div class="row" style="flex:1;align-items:flex-start">
        <div style="flex:0 0 430px;display:flex;flex-direction:column;gap:13px">
          <p style="font-size:16.5px">No case list, no ground truth, no hints.
          <code>POST /scan</code> sweeps a date range and finds the incidents itself.</p>
          <ul style="gap:10px">
            <li>Every metric, <strong>and every value of every dimension</strong> — not just
                population aggregates</li>
            <li>Echoes of one underlying event folded together</li>
            <li>Findings ranked, localized, and each one a full Evidence Bundle</li>
          </ul>
          <div class="card accent" style="padding:15px 18px">
            <p style="font-size:15.5px;color:var(--ink)">A large collapse confined to a small
            slice barely moves the global metric. Segment-level sweeping is what makes those
            findable at all.</p></div>
          <p style="font-size:15.5px">Then ask follow-ups in plain English — the conversation
          carries the investigation with it.</p>
        </div>
        <div class="col"><img class="shot" src="IMG_CHAT" style="height:408px;object-fit:contain;background:var(--surface)"></div>
      </div>""").replace("IMG_CHAT", chat))

    # 15 — scale & close
    S.append(_slide(15, "Scale · deployment · links", """
      <h2>Runs today. Scales by construction.</h2>
      <div class="row">
        <div class="card col">
          <h3>Cost is bounded, not linear</h3>
          <p style="font-size:16px">A targeted investigation is a handful of grouped scans over
          a rollup. A full blind sweep is roughly <strong>50 queries</strong>. Greedy search with
          a stop criterion keeps that flat as dimensions grow, instead of exploding
          combinatorially.</p></div>
        <div class="card col">
          <h3>Deployed properly</h3>
          <p style="font-size:16px">Docker Compose on EC2 behind nginx and TLS. Secrets in SSM
          Parameter Store, read through an IAM instance role — none in the repo, none in the
          image, no keys on the host. Reproducible from <code>deploy/</code>.</p></div>
      </div>
      <div class="card" style="margin-top:2px">
        <h3>Where it fits</h3>
        <p style="font-size:16px">The engine is dimension-agnostic — it reads the dimension list
        from config and scores whatever it is given. Nothing in it is specific to ad tech.</p>
      </div>
      <div style="margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;
                  border-top:1px solid var(--line);padding-top:22px">
        <div class="mono" style="font-size:14.5px;line-height:2;color:var(--muted)">
          <span style="color:var(--accent)">clickathon.kangasys.com</span>  ·  live demo<br>
          <span style="color:var(--accent)">traces.kangasys.com</span>  ·  Langfuse<br>
          <span style="color:var(--accent)">chat.kangasys.com</span>  ·  LibreChat
        </div>
        <div class="mono" style="font-size:13px;color:var(--faint);text-align:right;line-height:1.9">
          github.com/Rohanmrao/Clickathon2026<br>
          Jalagaara Gang · Click-a-thon 2026
        </div>
      </div>"""))

    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>Automated Root-Cause Analyst — Jalagaara Gang</title>"
            f"<style>{CSS}</style></head><body>{''.join(S)}</body></html>")
