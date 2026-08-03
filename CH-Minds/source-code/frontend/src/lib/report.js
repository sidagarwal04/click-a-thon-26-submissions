import { jsPDF } from "jspdf"
import autoTable from "jspdf-autotable"

const MARGIN = 14
const PAGE_WIDTH = 210 // A4 mm

function pct(v) {
  return v == null ? "n/a" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`
}

function num(v) {
  if (v == null) return "n/a"
  const rounded = Math.round(v * 10000) / 10000
  return rounded.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

export function buildInvestigationPdf(result, langfuseTraceUrl) {
  const doc = new jsPDF({ unit: "mm", format: "a4" })
  let y = MARGIN

  function ensureSpace(need) {
    const pageHeight = doc.internal.pageSize.getHeight()
    if (y + need > pageHeight - MARGIN) {
      doc.addPage()
      y = MARGIN
    }
  }

  function heading(text) {
    ensureSpace(10)
    doc.setFont("helvetica", "bold")
    doc.setFontSize(12)
    doc.text(text, MARGIN, y)
    y += 6
    doc.setFont("helvetica", "normal")
    doc.setFontSize(10)
  }

  function paragraph(text) {
    const lines = doc.splitTextToSize(text, PAGE_WIDTH - MARGIN * 2)
    for (const line of lines) {
      ensureSpace(5)
      doc.text(line, MARGIN, y)
      y += 5
    }
    y += 2
  }

  function table(head, body) {
    ensureSpace(14)
    autoTable(doc, {
      startY: y,
      margin: { left: MARGIN, right: MARGIN },
      head: [head],
      body,
      theme: "grid",
      styles: { fontSize: 9, cellPadding: 2 },
      headStyles: { fillColor: [124, 58, 237] },
    })
    y = doc.lastAutoTable.finalY + 6
  }

  doc.setFont("helvetica", "bold")
  doc.setFontSize(16)
  doc.text("Why Did It Move - Investigation Report", MARGIN, y)
  y += 8
  doc.setFont("helvetica", "normal")
  doc.setFontSize(10)
  const pageWidth = doc.internal.pageSize.getWidth();

  doc.text(`Metric: ${result.metric}`, MARGIN, y);

  doc.text(`Day: ${result.day}`, pageWidth - MARGIN, y, {
    align: "right",
  });

  y += 7;
  doc.text(`Generated: ${new Date().toISOString()}`, MARGIN, y)
  y += 8

  heading("Diagnosis")
  paragraph(result.diagnosis_text || "(no narration)")
  if (result.confidence != null) {
    paragraph(`Confidence: ${(result.confidence * 100).toFixed(0)}% - computed from how far the responsible segment's deviation sits past the detection threshold, not a fixed/hardcoded figure.`)
  }

  if (result.overall) {
    heading("Overall")
    table(
      ["Actual", "Baseline", "Deviation"],
      [[num(result.overall.actual), num(result.overall.baseline), pct(result.overall.pct_deviation)]]
    )
  }

  if (result.driving_factors?.length) {
    heading("Driving factor(s)")
    table(
      ["Metric", "Actual", "Baseline", "Deviation"],
      result.driving_factors.map((f) => [f.metric, num(f.actual), num(f.baseline), pct(f.pct_deviation)])
    )
  }

  if (result.responsible_segment) {
    const s = result.responsible_segment
    heading("Responsible segment")
    const rows = [[`${s.dimension} = ${s.value}`, num(s.actual), num(s.baseline), pct(s.pct_deviation), num(s.requests)]]
    if (s.refined_by) {
      const r = s.refined_by
      rows.push([`↳ further localized to ${r.dimension} = ${r.value}`, num(r.actual), num(r.baseline), pct(r.pct_deviation), num(r.requests)])
    }
    table(["Segment", "Actual", "Baseline", "Deviation", "Requests"], rows)
  }

  if (result.checked_and_ruled_out?.length) {
    heading("Checked and ruled out")
    for (const line of result.checked_and_ruled_out) {
      paragraph(`•  ${line}`)
    }
  }

  heading("Trace")
  paragraph(`Langfuse trace ID: ${result.langfuse_trace_id || "none"}`)
  if (langfuseTraceUrl) {
    ensureSpace(6)
    doc.setTextColor(37, 99, 235)
    doc.textWithLink("Open full trace in Langfuse", MARGIN, y, { url: langfuseTraceUrl })
    doc.setTextColor(0, 0, 0)
    y += 6
  }

  doc.addPage()
  y = MARGIN
  heading("Appendix: raw cited numbers (JSON)")
  paragraph("This is the exact structured data computed by ClickHouse and handed to the LLM for narration - the LLM never saw raw event rows, only this.")
  const evidence = {
    overall: result.overall,
    driving_factors: result.driving_factors,
    responsible_segment: result.responsible_segment,
  }
  doc.setFont("courier", "normal")
  doc.setFontSize(8)
  const jsonLines = JSON.stringify(evidence, null, 2).split("\n")
  for (const line of jsonLines) {
    ensureSpace(4)
    doc.text(line, MARGIN, y)
    y += 4
  }
  doc.setFont("helvetica", "normal")

  return doc
}

export function downloadPdf(doc, filename) {
  doc.save(filename)
}
