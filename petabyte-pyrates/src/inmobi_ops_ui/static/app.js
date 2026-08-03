const state = {
  incidents: [],
  filter: "all",
  search: "",
  selectedId: null,
};

const els = {
  body: document.getElementById("incidents-body"),
  meta: document.getElementById("result-meta"),
  search: document.getElementById("search-input"),
  refresh: document.getElementById("refresh-btn"),
  stats: {
    total: document.getElementById("stat-total"),
    open: document.getElementById("stat-open"),
    closed: document.getElementById("stat-closed"),
    rca: document.getElementById("stat-rca"),
    latest: document.getElementById("stat-latest"),
  },
  detailEmpty: document.getElementById("detail-empty"),
  detailContent: document.getElementById("detail-content"),
  detailId: document.getElementById("detail-id"),
  detailTitle: document.getElementById("detail-title"),
  detailBadges: document.getElementById("detail-badges"),
  detailMetrics: document.getElementById("detail-metrics"),
  detailRca: document.getElementById("detail-rca"),
  detailEvidence: document.getElementById("detail-evidence"),
  errorSection: document.getElementById("error-section"),
  detailError: document.getElementById("detail-error"),
  closeDetail: document.getElementById("close-detail"),
  toast: document.getElementById("toast"),
};

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.remove("hidden");
  window.setTimeout(() => els.toast.classList.add("hidden"), 4000);
}

function formatHour(value) {
  if (!value) return "—";
  const date = new Date(value.replace(" ", "T") + "Z");
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const pct = Number(value) * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

function deltaClass(value) {
  const n = Number(value);
  if (Number.isNaN(n) || Math.abs(n) < 0.0001) return "flat";
  return n < 0 ? "down" : "up";
}

function badge(label, kind) {
  const safe = String(kind || "unknown").toLowerCase().replace(/\s+/g, "_");
  return `<span class="badge badge-${safe}">${label}</span>`;
}

function matchesFilter(incident) {
  const { filter } = state;
  if (filter === "all") return true;
  if (filter === "open") return incident.status === "open";
  if (filter === "closed") return incident.status === "closed";
  if (filter === "pending") return incident.disposition === "pending";
  return incident.disposition === filter;
}

function matchesSearch(incident) {
  const q = state.search.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    incident.metric_name,
    incident.region,
    incident.ad_format,
    incident.slice_value,
    incident.slice_type,
    incident.severity,
    incident.status,
    incident.disposition,
    incident.anomaly_id,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
}

function filteredIncidents() {
  return state.incidents.filter((incident) => matchesFilter(incident) && matchesSearch(incident));
}

function renderStats(stats) {
  els.stats.total.textContent = stats.total ?? "0";
  els.stats.open.textContent = stats.open_count ?? "0";
  els.stats.closed.textContent = stats.closed_count ?? "0";
  els.stats.rca.textContent = stats.with_rca ?? "0";
  els.stats.latest.textContent = formatHour(stats.latest_metric_hour);
}

function renderTable() {
  const rows = filteredIncidents();
  els.meta.textContent = `${rows.length} anomal${rows.length === 1 ? "y" : "ies"} on radar`;

  if (!rows.length) {
    els.body.innerHTML = `<tr><td colspan="7" class="empty">No anomalies match your filters.</td></tr>`;
    return;
  }

  els.body.innerHTML = rows
    .map((incident) => {
      const selected = incident.anomaly_id === state.selectedId ? "selected" : "";
      const segment = `${incident.region || "—"} · ${incident.ad_format || "—"}`;
      const slice = incident.slice_value || incident.slice_type || "";
      return `
        <tr class="${selected}" data-id="${incident.anomaly_id}">
          <td class="cell-time">
            <strong>${formatHour(incident.metric_hour)}</strong>
            <span>detected ${formatHour(incident.detected_at)}</span>
          </td>
          <td class="cell-segment">
            <strong>${segment}</strong>
            <span>${slice}</span>
          </td>
          <td class="cell-metric">${incident.metric_name || "—"}</td>
          <td class="delta ${deltaClass(incident.delta_pct)}">${formatPct(incident.delta_pct)}</td>
          <td>${badge(incident.severity || "unknown", incident.severity)}</td>
          <td>${badge(incident.status || "unknown", incident.status)}</td>
          <td>${badge((incident.disposition || "pending").replace(/_/g, " "), incident.disposition)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderDetailMetrics(items) {
  els.detailMetrics.innerHTML = items
    .map(
      ([label, value]) => `
        <div>
          <dt>${label}</dt>
          <dd>${value}</dd>
        </div>
      `,
    )
    .join("");
}

async function loadDetail(anomalyId) {
  state.selectedId = anomalyId;
  renderTable();

  const response = await fetch(`/api/incidents/${anomalyId}`);
  if (!response.ok) {
    showToast("Could not load anomaly detail.");
    return;
  }
  const incident = await response.json();

  els.detailEmpty.classList.add("hidden");
  els.detailContent.classList.remove("hidden");

  els.detailId.textContent = incident.anomaly_id;
  els.detailTitle.textContent = `${incident.metric_name} · ${incident.region} / ${incident.ad_format}`;
  els.detailBadges.innerHTML = [
    badge(incident.severity, incident.severity),
    badge(incident.status, incident.status),
    badge((incident.disposition || "pending").replace(/_/g, " "), incident.disposition),
    incident.confidence_tier ? badge(`confidence ${incident.confidence_tier}`, "pending") : "",
  ].join("");

  renderDetailMetrics([
    ["Metric hour", formatHour(incident.metric_hour)],
    ["Current", Number(incident.current_value).toLocaleString()],
    ["Baseline", Number(incident.baseline_value).toLocaleString()],
    ["Delta", formatPct(incident.delta_pct)],
    ["Z-score", incident.z_score ?? "—"],
    ["Requests", Number(incident.volume_requests || 0).toLocaleString()],
    ["Detection", incident.detection_tier || "—"],
    ["Investigated", incident.investigated_at ? formatHour(incident.investigated_at) : "Not yet"],
  ]);

  const rca = incident.rca_description?.trim();
  els.detailRca.textContent = rca || "No RCA written yet. Run the agent against this anomaly_id.";

  const evidence = incident.evidence_parsed || incident.evidence_json;
  if (evidence && typeof evidence === "object") {
    els.detailEvidence.textContent = JSON.stringify(evidence, null, 2);
  } else if (evidence) {
    els.detailEvidence.textContent = String(evidence);
  } else {
    els.detailEvidence.textContent = "No evidence JSON yet.";
  }

  if (incident.last_error) {
    els.errorSection.classList.remove("hidden");
    els.detailError.textContent = incident.last_error;
  } else {
    els.errorSection.classList.add("hidden");
  }
}

function clearDetail() {
  state.selectedId = null;
  renderTable();
  els.detailContent.classList.add("hidden");
  els.detailEmpty.classList.remove("hidden");
}

async function refresh() {
  els.refresh.disabled = true;
  try {
    const [statsRes, incidentsRes] = await Promise.all([
      fetch("/api/stats"),
      fetch("/api/incidents"),
    ]);

    if (!statsRes.ok || !incidentsRes.ok) {
      const detail = !statsRes.ok ? await statsRes.text() : await incidentsRes.text();
      throw new Error(detail || "Failed to load data");
    }

    renderStats(await statsRes.json());
    state.incidents = await incidentsRes.json();
    renderTable();

    if (state.selectedId) {
      await loadDetail(state.selectedId);
    }
  } catch (error) {
    els.body.innerHTML = `<tr><td colspan="7" class="empty">Could not reach ClickHouse. Check CLICKHOUSE_HOST and credentials, then refresh.</td></tr>`;
    showToast(error.message || "Refresh failed");
  } finally {
    els.refresh.disabled = false;
  }
}

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((node) => node.classList.remove("chip-active"));
    chip.classList.add("chip-active");
    state.filter = chip.dataset.filter;
    renderTable();
  });
});

els.search.addEventListener("input", (event) => {
  state.search = event.target.value;
  renderTable();
});

els.body.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-id]");
  if (!row) return;
  loadDetail(row.dataset.id);
});

els.refresh.addEventListener("click", refresh);
els.closeDetail.addEventListener("click", clearDetail);

refresh();
window.setInterval(refresh, 30000);
