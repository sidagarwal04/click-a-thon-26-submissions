import { useEffect, useMemo, useState } from 'react';
import { Grid, Box, Paper, Typography, TextField, MenuItem, Table, TableBody, TableCell, TableHead, TableRow, LinearProgress, Alert, ToggleButton, ToggleButtonGroup } from '@mui/material';
import KpiCard from '../components/KpiCard';
import PeakChart from '../components/PeakChart';
import QueryTelemetry from '../components/QueryTelemetry';
import FilterBar from '../components/FilterBar';
import { fetchSegments, parseTs, fmtInt, fmtNum, fmtClock } from '../api';
import { C, SERIES_COLORS } from '../theme';

export default function SegmentAnalysis({ meta, filters, setFilters, resetFilters }) {
  const [dimension, setDimension] = useState('platform');
  const [topN, setTopN] = useState(8);
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let alive = true;
    setBusy(true);
    fetchSegments({ ...filters, dimension, top: topN })
      .then((r) => alive && (setD(r), setErr(null)))
      .catch((e) => alive && setErr(e.message))
      .finally(() => alive && setBusy(false));
    return () => { alive = false; };
  }, [JSON.stringify(filters), dimension, topN]);

  const rows = d?.breakdown || [];
  const conc = d?.concentration || {};
  const dimLabel = (meta?.dimensions || []).find((x) => x.key === dimension)?.label || dimension;

  // Pivot the flat (bucket, segment) rows into one series per segment.
  const chart = useMemo(() => {
    const src = d?.series || [];
    if (!src.length) return { x: [], series: [] };
    const buckets = [...new Set(src.map((p) => p.t))].sort();
    const idx = new Map(buckets.map((b, i) => [b, i]));
    const bySeg = new Map();
    src.forEach((p) => {
      if (!bySeg.has(p.seg_label)) bySeg.set(p.seg_label, new Array(buckets.length).fill(null));
      bySeg.get(p.seg_label)[idx.get(p.t)] = Number(p.peak);
    });
    return {
      x: buckets.map(parseTs),
      series: [...bySeg.entries()].map(([label, data], i) => ({
        label: label || '—', data, color: SERIES_COLORS[i % SERIES_COLORS.length],
      })),
    };
  }, [d]);

  const leader = rows[0];

  const dimensionPicker = (
    <TextField
      select size="small" label="Segment by" value={dimension}
      onChange={(e) => setDimension(e.target.value)}
      sx={{ minWidth: 158, '& .MuiInputBase-root': { bgcolor: C.ground, fontSize: 13 }, '& .MuiInputLabel-root': { fontSize: 12.5 } }}
    >
      {(meta?.dimensions || []).map((x) => <MenuItem key={x.key} value={x.key}>{x.label}</MenuItem>)}
    </TextField>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <FilterBar meta={meta} filters={filters} onChange={setFilters} onReset={resetFilters} extra={dimensionPicker} />
      {busy && <LinearProgress sx={{ height: 2, bgcolor: 'transparent' }} />}
      {err && <Alert severity="error" variant="outlined">Couldn’t load segments: {err}</Alert>}

      <QueryTelemetry timings={d?.timings} />

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard label={`${dimLabel}s in range`} value={fmtInt(conc.segments)}
            note="Distinct values of the selected dimension that recorded any foreground viewing." />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard accent label="Busiest segment" value={leader?.seg_label || '—'}
            moment={leader ? `peak ${fmtInt(leader.peak)} @ ${fmtClock(parseTs(leader.peak_minute))}` : null}
            note="Ranked by peak concurrency, not by total watch time — the two often disagree." />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard label="Largest segment share" value={fmtNum(conc.largest_share_pct, 1)} unit="%"
            note="Share of all foreground session-minutes held by the single biggest segment." />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard label="Top decile share" value={fmtNum(conc.top_decile_share_pct, 1)} unit="%"
            note="How concentrated demand is. A high number means a handful of segments carry the load." />
        </Grid>
      </Grid>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Typography variant="overline">Show top</Typography>
        <ToggleButtonGroup size="small" exclusive value={topN} onChange={(_, v) => v && setTopN(v)}>
          {[5, 8, 12, 20].map((n) => (
            <ToggleButton key={n} value={n}
              sx={{ px: 1.5, py: 0.4, fontSize: 12, fontFamily: '"JetBrains Mono", monospace', color: C.muted, borderColor: C.line,
                '&.Mui-selected': { color: C.ground, bgcolor: C.trace, '&:hover': { bgcolor: C.trace } } }}>
              {n}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      <PeakChart
        title={`Concurrency by ${dimLabel.toLowerCase()}`}
        caption="Each line peaks at its own minute. Summing these gives total concurrency; taking their maximum does not."
        x={chart.x}
        series={chart.series}
        height={340}
      />

      <Paper elevation={0} sx={{ p: 2.25, bgcolor: C.surface }}>
        <Typography variant="subtitle2" sx={{ fontSize: 14, mb: 1 }}>{dimLabel} breakdown</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{dimLabel}</TableCell>
              <TableCell align="right">Peak</TableCell>
              <TableCell align="right">Peaked at</TableCell>
              <TableCell align="right">Average</TableCell>
              <TableCell align="right">Session-minutes</TableCell>
              <TableCell align="right">Share</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={row.seg} hover>
                <TableCell sx={{ fontSize: 12.5 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: SERIES_COLORS[i % SERIES_COLORS.length] }} />
                    {row.seg_label || row.seg}
                  </Box>
                </TableCell>
                <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}>
                  {fmtInt(row.peak)}
                </TableCell>
                <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11.5, color: C.peak }}>
                  {fmtClock(parseTs(row.peak_minute))}
                </TableCell>
                <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}>
                  {fmtNum(row.avg)}
                </TableCell>
                <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums', color: C.muted }}>
                  {fmtInt(row.session_minutes)}
                </TableCell>
                <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}>
                  {fmtNum(row.share_pct, 1)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
