const METRIC_LABELS = {
  revenue: "Revenue", fill_rate: "Fill rate", ecpm: "eCPM",
  requests: "Requests", ctr: "CTR", render_rate: "Render rate",
};
const REVENUE_FACTORS = ["requests", "fill_rate", "render_rate", "ecpm"];

function fmtNumber(v) {
  if (v === null || v === undefined) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (abs >= 1e3) return (v / 1e3).toFixed(2) + "K";
  if (abs < 1 && abs > 0) return v.toFixed(4);
  return v.toFixed(2);
}
function fmtPct(v) { return v === null || v === undefined ? "—" : (v * 100).toFixed(1) + "%"; }
function fmtSignedPct(v) { return v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`; }

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function showToast(message, type) {
  const container = document.getElementById("toast-container");
  const t = document.createElement("div");
  t.className = "toast" + (type ? ` ${type}` : "");
  t.textContent = message;
  container.appendChild(t);
  setTimeout(() => {
    t.classList.add("fade-out");
    setTimeout(() => t.remove(), 200);
  }, 4000);
}

// metric_rel_delta/segment_chains/severity/confidence all come straight from
// the API now (web.py: _derive_fields) -- computed once, server-side, so this
// page and the dashboard list can't drift out of sync with each other.
function confidenceRing(pct, size) {
  size = size || 30;
  const r = size / 2 - 3, c = 2 * Math.PI * r;
  if (pct === null) {
    return `<svg class="ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">` +
      `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="var(--gridline)" stroke-width="3"/></svg>`;
  }
  const off = c * (1 - pct / 100);
  return `<svg class="ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">` +
    `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="3"/>` +
    `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="url(#chartAreaGradient)" stroke-width="3" ` +
    `stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 ${size / 2} ${size / 2})"/>` +
    `</svg>`;
}

async function setupFollowupButtons(id, metricLabel, data) {
  const buttons = [document.getElementById("followup-btn-top"), document.getElementById("followup-btn-bottom")];
  try {
    const meta = await (await fetch("/api/meta")).json();
    if (!meta.librechat_followup_agent_id) return; // not configured; leave hidden
    const prompt =
      `Let's discuss incident ${id} (${metricLabel}, ${data.current_window[0]} to ${data.current_window[1]}). ` +
      `Call get_investigation('${id}') first, then help me understand it further.`;
    buttons.forEach((btn) => {
      btn.style.display = "";
      btn.addEventListener("click", () => {
        const url = new URL("/c/new", meta.librechat_base_url);
        url.searchParams.set("agent_id", meta.librechat_followup_agent_id);
        url.searchParams.set("prompt", prompt);
        url.searchParams.set("submit", "true");
        window.open(url.toString(), "_blank", "noopener");
      });
    });
  } catch (e) {
    console.error("Follow-up button setup failed:", e);
    showToast("Couldn't set up follow-up chat: " + e.message, "error");
  }
}

function setupLangfuseButton(data) {
  const btn = document.getElementById("langfuse-btn");
  if (!data.langfuse_trace_url) return;
  btn.style.display = "";
  btn.addEventListener("click", () => window.open(data.langfuse_trace_url, "_blank", "noopener"));
}

function setupDownloadButton(data) {
  document.getElementById("download-btn").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${data.id}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showToast("Downloaded " + a.download, "success");
  });
}

function setupExportButton() {
  document.getElementById("export-btn").addEventListener("click", () => window.print());
}

function setupSqlDownloadButton(data) {
  const btn = document.getElementById("sql-download-btn");
  if (!data.sql_script) return; // older saved incidents predate this field
  btn.style.display = "";
  btn.addEventListener("click", () => {
    const blob = new Blob([data.sql_script], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${data.id}.sql`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showToast("Downloaded " + a.download, "success");
  });
}

async function main() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  if (!id) { document.getElementById("title").textContent = "No incident id given"; return; }

  const res = await fetch(`/api/incidents/${encodeURIComponent(id)}`);
  if (!res.ok) { document.getElementById("title").textContent = "Not found"; return; }
  const data = await res.json();

  const metricLabel = METRIC_LABELS[data.metric] || data.metric;
  const relDelta = data.metric_rel_delta;
  const sev = data.severity;
  // One chain per independent cause the drill-down localized (almost always
  // one; more than one when two dimensions each independently cleared the
  // localization bar -- see attribution.drill_down's branch_factor).
  const chains = data.segment_chains || [];
  const conf = data.confidence;

  document.title = `${metricLabel} ${data.current_window[0]}..${data.current_window[1]} — Incident`;
  document.getElementById("title").textContent = `${metricLabel} ${relDelta >= 0 ? "Spike" : "Drop"}`;

  const sevBadge = document.getElementById("sevBadge");
  sevBadge.style.display = "";
  sevBadge.className = "sev-badge " + sev;
  sevBadge.textContent = sev.toUpperCase();

  document.getElementById("dateLabel").textContent =
    data.current_window[0] === data.current_window[1] ? data.current_window[0] : `${data.current_window[0]} .. ${data.current_window[1]}`;
  const confWrap = document.getElementById("confWrap");
  confWrap.innerHTML = conf === null
    ? `${confidenceRing(null, 22)}<span style="color:var(--text-muted);">Broad-based — no single localized cause</span>`
    : `${confidenceRing(conf, 22)}Confidence <b>${conf}%</b>`;

  document.getElementById("impactLabel").textContent = `${metricLabel} Impact`.toUpperCase();
  const impactValue = document.getElementById("impactValue");
  impactValue.textContent = fmtSignedPct(relDelta);
  impactValue.className = "impact-value " + (relDelta >= 0 ? "up" : "down");

  const narrativeEl = document.getElementById("narrative");
  narrativeEl.textContent = data.narrative;
  const links = el("div", "trace-links");
  if (data.langfuse_trace_url) {
    const a = el("a", null, "View Langfuse trace ->");
    a.href = data.langfuse_trace_url; a.target = "_blank"; a.rel = "noopener";
    links.appendChild(a);
  }
  if (data.local_trace_path) {
    links.appendChild(el("span", null, `Local trace: ${data.local_trace_path}`));
  }
  narrativeEl.appendChild(links);

  setupFollowupButtons(data.id, metricLabel, data);
  setupLangfuseButton(data);
  setupDownloadButton(data);
  setupSqlDownloadButton(data);
  setupExportButton();

  renderInvestigationTree(document.getElementById("itree"), data, metricLabel);
  renderFactors(data.decomposition);
  renderEvidence(data, metricLabel, chains);
  renderDrillTree(document.getElementById("drill-tree"), data.drill_down, 0);
  renderStepper();
}

// ---------------- Investigation Path: a Q&A decision tree ----------------
// Every step is built directly from real pipeline output: which factor/
// dimension was checked (dimensions_checked / REVENUE_FACTORS), which one
// won (primary_segment / drill_factor), and the real EP/lift/contribution
// numbers behind that choice. Rejected candidates are shown too, not just
// the winner -- "dynamic to which path it chose", not a fixed diagram.

const CHECK_ICON = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
const CROSS_ICON = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';
const ARROW_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>';

function dimLabel(name) {
  const s = name.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function renderInvestigationTree(container, data, metricLabel) {
  container.innerHTML = "";
  const decomp = data.decomposition;

  container.appendChild(el("div", "itree-stmt",
    `${metricLabel} ${data.metric_rel_delta >= 0 ? "increased" : "decreased"} by ${fmtPct(Math.abs(data.metric_rel_delta))}`));

  const factorStepNeeded = data.drill_factor && data.drill_factor !== data.metric;
  if (factorStepNeeded) {
    container.appendChild(buildFactorStep(decomp, data.drill_factor, metricLabel));
  }

  const factorLabel = factorStepNeeded ? (METRIC_LABELS[data.drill_factor] || data.drill_factor) : metricLabel;
  const level = data.drill_down;

  if (level && level.dimensions_checked && Object.keys(level.dimensions_checked).length) {
    renderDrillBranch(container, level, factorLabel, factorLabel, metricLabel, 0, []);
  } else {
    container.appendChild(buildBroadBasedEnding());
  }
}

// Walks one drill level and, for every dimension that cleared the
// localization bar at this level (level.primary_segments -- almost always
// one, but occasionally more than one when independent dimensions each
// disproportionately explain part of the same movement, see
// attribution.drill_down's branch_factor), recurses into that segment's own
// sub-drill (level.deeper, index-aligned with primary_segments). When more
// than one candidate qualifies, each gets its own indented `.itree-branch`
// so the fork is visually a fork, not another entry in one long column; the
// single-candidate case (the overwhelming majority of incidents) renders
// exactly as it always has, with no extra nesting. Each leaf (a branch with
// nothing further to localize) closes with its own Root Cause block built
// from exactly the chain of segments that got us there.
function renderDrillBranch(container, level, parentLabel, factorLabel, metricLabel, depth, chainPrefix) {
  container.appendChild(buildDimensionStep(level, parentLabel, depth));

  const primaries = level.primary_segments || [];
  if (!primaries.length) return;

  const deeper = level.deeper || [];
  const multi = primaries.length > 1;

  primaries.forEach((primary, i) => {
    let target = container;
    if (multi) {
      target = el("div", "itree-branch");
      const tag = el("div", "itree-branch-tag", `Independent cause ${i + 1} of ${primaries.length}`);
      target.appendChild(tag);
      container.appendChild(target);
    }

    target.appendChild(buildWhyAnswer(primary));

    const chain = chainPrefix.concat([primary]);
    const child = deeper[i];
    if (child && child.dimensions_checked && Object.keys(child.dimensions_checked).length) {
      renderDrillBranch(target, child, primary.value, factorLabel, metricLabel, depth + 1, chain);
    } else {
      target.appendChild(buildRootCauseBlock(chain, factorLabel, metricLabel));
    }
  });
}

function buildFactorStep(decomp, drillFactor, metricLabel) {
  const contributions = decomp.factor_contributions_to_revenue_delta || {};
  const revenueDelta = decomp.revenue_delta || 1;
  const winnerLabel = METRIC_LABELS[drillFactor] || drillFactor;
  // |revenueDelta|, not revenueDelta -- see the note in buildRootCauseBlock;
  // same sign-flip risk when the total delta is negative.
  const winnerPct = Math.abs((contributions[drillFactor] || 0) / Math.abs(revenueDelta)) * 100;

  const step = el("div", "itree-step");
  step.appendChild(el("div", "itree-q", `Which factor explains the ${metricLabel.toLowerCase()} movement?`));

  const candidates = el("div", "itree-candidates");
  REVENUE_FACTORS.forEach((f) => {
    const isWinner = f === drillFactor;
    const row = el("div", "itree-candidate " + (isWinner ? "chosen" : "rejected"));
    row.innerHTML = (isWinner ? CHECK_ICON : CROSS_ICON) + `<span>${METRIC_LABELS[f] || f}</span>` +
      (isWinner ? `<span class="stat">${winnerPct.toFixed(0)}% of movement</span>` : "");
    candidates.appendChild(row);
  });
  step.appendChild(candidates);

  const answer = el("div", "itree-answer");
  answer.innerHTML = `<b>Why ${winnerLabel}?</b> LMDI decomposition shows ${winnerLabel} contributed ${winnerPct.toFixed(0)}% ` +
    `of the ${metricLabel.toLowerCase()} movement — the largest share among the four revenue factors.`;
  step.appendChild(answer);

  const goto = el("div", "itree-goto");
  goto.innerHTML = `${ARROW_ICON} Investigate ${winnerLabel}`;
  step.appendChild(goto);
  return step;
}

function buildDimensionStep(level, parentLabel, depth) {
  const dims = level.dimensions_checked || {};
  const dimNames = Object.keys(dims);
  // Every dimension whose top candidate cleared the localization bar --
  // almost always one, but can be more than one (attribution.drill_down's
  // branch_factor). All of them are marked chosen here; renderDrillBranch
  // (the caller) is what actually recurses into each one afterward.
  const primaries = level.primary_segments || [];

  const step = el("div", "itree-step");
  step.appendChild(el("div", "itree-q", `Which dimension ${depth === 0 ? "best explains" : "explains"} the ${parentLabel} degradation?`));

  const candidates = el("div", "itree-candidates");
  dimNames.forEach((dimName) => {
    const winner = primaries.find((p) => p.dimension === dimName);
    const row = el("div", "itree-candidate " + (winner ? "chosen" : "rejected"));
    row.innerHTML = (winner ? CHECK_ICON : CROSS_ICON) + `<span>${dimLabel(dimName)}</span>` +
      (winner ? `<span class="stat">EP=${winner.explanatory_power.toFixed(2)} · Lift=${winner.lift.toFixed(1)}×</span>` : "");
    candidates.appendChild(row);
  });
  step.appendChild(candidates);

  if (!primaries.length) {
    step.appendChild(el("div", "itree-answer",
      "No dimension cleared the localization bar here — every segment checked moved in proportion to its own size."));
  }
  return step;
}

// The "Why {dim}={value}?" explanation + "Investigate {value}" transition
// for one qualifying candidate. Split out from buildDimensionStep so that
// when several candidates qualify at once, each gets its own answer/
// transition ahead of its own (independently rendered) sub-branch, instead
// of only ever being able to say "the" answer for a single winner.
function buildWhyAnswer(primary) {
  const wrap = el("div", "itree-why");
  const answer = el("div", "itree-answer");
  answer.innerHTML = `<b>Why ${dimLabel(primary.dimension)} = ${primary.value}?</b> ` +
    `${primary.value} alone explains ${fmtPct(primary.explanatory_power)} of the movement observed at this level — ` +
    `${primary.lift.toFixed(1)}× more than its size would predict. Other segments checked moved close to proportionally.`;
  wrap.appendChild(answer);
  const goto = el("div", "itree-goto");
  goto.innerHTML = `${ARROW_ICON} Investigate ${primary.value}`;
  wrap.appendChild(goto);
  return wrap;
}

function buildRootCauseBlock(chain, factorLabel, metricLabel) {
  const block = el("div", "itree-end");
  const card = el("div", "itree-rootcause");
  card.appendChild(el("div", "eyebrow", "ROOT CAUSE"));

  const chainRow = el("div", "itree-chain");
  chain.forEach((s, i) => {
    if (i > 0) chainRow.appendChild(el("span", "itree-chain-arrow", "→"));
    chainRow.appendChild(el("span", "itree-chain-item", s.value));
  });
  card.appendChild(chainRow);

  const last = chain[chain.length - 1];
  // This chain's own root-level explanatory_power, not the incident's
  // headline `confidence` figure -- confidence is defined as the single
  // strongest branch's EP (see web.py._confidence_for), which would
  // overstate a weaker second branch's own block if reused here.
  const pct = Math.max(0, Math.min(100, Math.round(chain[0].explanatory_power * 100)));
  card.appendChild(el("p", null,
    `${factorLabel} moved from ${fmtNumber(last.rate_baseline)} to ${fmtNumber(last.rate_current)} in this segment, ` +
    `explaining ${pct}% of the overall ${metricLabel.toLowerCase()} movement.`));
  block.appendChild(card);
  return block;
}

function buildBroadBasedEnding() {
  const block = el("div", "itree-end");
  const card = el("div", "itree-rootcause broad");
  card.appendChild(el("div", "eyebrow", "RESULT"));
  const chainRow = el("div", "itree-chain");
  chainRow.appendChild(el("span", "itree-chain-item", "No single segment stands out"));
  card.appendChild(chainRow);
  card.appendChild(el("p", null,
    "Every segment checked moved in proportion to its own size — this looks like a broad, system-wide " +
    "change rather than one localized cause."));
  block.appendChild(card);
  return block;
}

// ---------------- Contribution breakdown ----------------

function renderFactors(decomp) {
  const grid = document.getElementById("factor-grid");
  grid.innerHTML = "";
  const contributions = decomp.factor_contributions_to_revenue_delta || {};
  const revenueDelta = decomp.revenue_delta || 1;
  const maxAbs = Math.max(...REVENUE_FACTORS.map((f) => Math.abs(contributions[f] || 0)), 1e-9);

  REVENUE_FACTORS.forEach((f) => {
    const contrib = contributions[f] || 0;
    // |revenueDelta|, not revenueDelta: see the comment in renderWhy() -- same flip.
    const pctOfTotal = contrib / Math.abs(revenueDelta);
    const cls = contrib >= 0 ? "up" : "down";
    const row = el("div", "contrib-row");
    row.appendChild(el("div", "contrib-label", (METRIC_LABELS[f] || f).toLowerCase()));
    const track = el("div", "contrib-track");
    const fill = el("div", `contrib-fill ${cls}`);
    fill.style.width = `${(Math.abs(contrib) / maxAbs) * 100}%`;
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el("div", `contrib-value ${cls}`, fmtSignedPct(pctOfTotal)));
    grid.appendChild(row);
  });
}

// ---------------- Supporting evidence ----------------

function renderEvidence(data, metricLabel, chains) {
  const decomp = data.decomposition;
  const rows = [];
  rows.push([metricLabel, decomp.baseline_factors[data.metric], decomp.current_factors[data.metric], data.metric_rel_delta]);

  if (data.drill_factor && data.drill_factor !== data.metric) {
    const fLabel = METRIC_LABELS[data.drill_factor] || data.drill_factor;
    rows.push([fLabel, decomp.baseline_factors[data.drill_factor], decomp.current_factors[data.drill_factor], (decomp.factor_rel_deltas || {})[data.drill_factor]]);
  }
  // One card per independent chain's deepest segment -- almost always one,
  // but there can be more (see attribution.drill_down's branch_factor).
  chains.forEach((chain) => {
    if (!chain.length) return;
    const seg = chain[chain.length - 1];
    const segRel = seg.rate_baseline ? (seg.rate_current - seg.rate_baseline) / seg.rate_baseline : null;
    rows.push([`${seg.dimension} = ${seg.value}`, seg.rate_baseline, seg.rate_current, segRel]);
  });

  const grid = document.getElementById("detEvidence");
  grid.innerHTML = rows.map(([label, baseline, current, rel]) => {
    const neg = rel !== null && rel !== undefined && rel < 0;
    return `<div class="evidence-card">` +
      `<div class="evidence-metric">${label}</div>` +
      `<div class="evidence-row"><span>Baseline</span><span>${fmtNumber(baseline)}</span></div>` +
      `<div class="evidence-row"><span>Current</span><span>${fmtNumber(current)}</span></div>` +
      `<div class="evidence-row diff"><span>Difference</span><span class="${neg ? "neg" : "pos"}">${fmtSignedPct(rel)}</span></div>` +
      `</div>`;
  }).join("");
}

// ---------------- Full evidence (collapsed per-dimension tables) ----------------

function renderDrillTree(container, level, depth) {
  if (!level) return;
  const wrap = el("div", "drill-level" + (depth > 0 ? " nested" : ""));

  if (level.filters && level.filters.length) {
    const f = el("div", "dim-name", "Within: " + level.filters.map((x) => `${x.dimension}=${x.value}`).join(", "));
    wrap.appendChild(f);
  }

  const dims = level.dimensions_checked || {};
  const dimNames = Object.keys(dims);
  const totalSegments = dimNames.reduce((n, d) => n + (dims[d].top_segments || []).length, 0);
  // Every dimension whose top candidate cleared the bar at this level --
  // almost always one, but can be more than one (branch_factor).
  const primaries = level.primary_segments || [];

  const details = document.createElement("details");
  details.className = "evidence-details";
  const summary = document.createElement("summary");
  summary.textContent = primaries.length
    ? `Show full evidence at this level (${dimNames.length} dimensions, ${totalSegments} segments checked)`
    : `Show what was checked (${dimNames.length} dimensions, ${totalSegments} segments — none stood out)`;
  details.appendChild(summary);

  dimNames.forEach((dimName) => {
    const info = dims[dimName];
    const block = el("div", "dim-block");
    block.appendChild(el("div", "dim-name",
      `${dimName} (${info.n_segments_checked} segments checked, ${info.n_excluded_low_volume} excluded as low-volume)`));
    const table = document.createElement("table");
    table.className = "seg-table";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th>Status</th><th>Value</th><th>Rate (base → current)</th><th>Volume share</th><th>Explanatory power</th><th>Lift</th></tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    (info.top_segments || []).forEach((s) => {
      const isPrimary = primaries.some((p) => p.value === s.value && dimName === p.dimension);
      const tr = document.createElement("tr");
      tr.className = isPrimary ? "primary-row" : (s.ruled_out ? "ruled-out" : "");

      const statusTd = document.createElement("td");
      statusTd.textContent = isPrimary ? "Localized cause" : (s.ruled_out ? "Ruled out" : "Notable, not primary");
      tr.appendChild(statusTd);

      const cells = [
        s.value,
        `${fmtNumber(s.rate_baseline)} → ${fmtNumber(s.rate_current)}`,
        fmtPct(s.volume_share_current),
        s.explanatory_power,
        s.lift,
      ];
      cells.forEach((c, i) => {
        const td = document.createElement("td");
        td.textContent = c;
        if (i === 4 && Math.abs(s.lift) >= 1.8) td.className = "lift-cell hot";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    block.appendChild(table);
    details.appendChild(block);
  });

  wrap.appendChild(details);
  container.appendChild(wrap);

  // One recursive call per branch (index-aligned with primary_segments) --
  // almost always zero or one, but can be more than one.
  (level.deeper || []).forEach((child) => renderDrillTree(container, child, depth + 1));
}

// ---------------- Pipeline stepper ----------------

function renderStepper() {
  const steps = ["Baseline Comparison", "LMDI Decomposition", "Root Cause Localization", "AI Report Generation"];
  const wrap = document.getElementById("detStepper");
  wrap.innerHTML = "";
  steps.forEach((label, i) => {
    if (i > 0) wrap.appendChild(el("div", "step-line"));
    const step = el("div", "step");
    step.innerHTML = `<div class="step-dot">${CHECK_ICON}</div><div class="step-label">${label}</div>`;
    wrap.appendChild(step);
  });
}

main().catch((e) => {
  document.getElementById("title").textContent = "Failed to load";
  console.error(e);
  showToast("Failed to load investigation: " + e.message, "error");
});
