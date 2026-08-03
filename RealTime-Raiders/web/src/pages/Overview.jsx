import { useEffect, useState } from 'react';
import { Grid, Box, Paper, Typography, Table, TableBody, TableCell, TableHead, TableRow, LinearProgress, Alert } from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import KpiCard from '../components/KpiCard';
import PeakChart from '../components/PeakChart';
import QueryTelemetry from '../components/QueryTelemetry';
import FilterBar from '../components/FilterBar';
import { fetchOverview, parseTs, fmtInt, fmtNum, fmtClock } from '../api';
import { C } from '../theme';

export default function Overview({ meta, filters, setFilters, resetFilters }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let alive = true;
    setBusy(true);
    fetchOverview(filters)
      .then((r) => alive && (setD(r), setErr(null)))
      .catch((e) => alive && setErr(e.message))
      .finally(() => alive && setBusy(false));
    return () => { alive = false; };
  }, [JSON.stringify(filters)]);

  const s = d?.summary || {};
  const r = d?.reach || {};
  const peakAt = parseTs(s.peak_minute);
  const ts = d?.timeseries || [];
  const hourly = d?.hourly || [];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <FilterBar meta={meta} filters={filters} onChange={setFilters} onReset={resetFilters} />
      {busy && <LinearProgress sx={{ height: 2, bgcolor: 'transparent' }} />}
      {err && <Alert severity="error" variant="outlined">Couldn’t load KPIs: {err}</Alert>}

      <QueryTelemetry timings={d?.timings} />

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            accent
            label="Peak concurrency"
            value={fmtInt(s.peak_concurrency)}
            unit="sessions"
            moment={fmtClock(peakAt)}
            note="Sessions actively watching in the foreground during the busiest single minute. Summed across every dimension, then maximised over minutes — never stored."
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            label="Average concurrency"
            value={fmtNum(s.avg_concurrency)}
            unit="sessions"
            note="Total active session-minutes divided by every minute in the range, including minutes with no viewing at all."
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            accent
            label="Peak concurrent viewers"
            value={fmtInt(r.peak_concurrent_users)}
            unit="users"
            moment={fmtClock(parseTs(r.peak_users_minute))}
            note="Distinct users, not sessions. One person on a phone and a TV is two sessions but one viewer, so this is merged rather than summed."
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            label="Foreground viewing"
            value={fmtInt(s.active_session_minutes)}
            unit="session-minutes"
            note="Backgrounded time is excluded. Measured heartbeats continue while the app is backgrounded, so those minutes are subtracted explicitly."
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <KpiCard
            label="Minutes with viewing"
            value={`${fmtInt(s.minutes_with_viewing)} / ${fmtInt(s.minutes_in_range)}`}
            note="Minutes that had at least one active session, against the full length of the selected range."
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <KpiCard
            label="Peak to average ratio"
            value={s.avg_concurrency > 0 ? fmtNum(s.peak_concurrency / s.avg_concurrency, 1) : '—'}
            unit="×"
            note="How spiky demand is. A high ratio means capacity has to be sized for a moment, not for the day."
          />
        </Grid>
      </Grid>

      <PeakChart
        title="Concurrency over time"
        caption="Minute-level foreground concurrency. Long ranges are bucketed by maximum, never by average, so the peak survives downsampling intact."
        x={ts.map((p) => parseTs(p.t))}
        series={[
          { data: ts.map((p) => Number(p.peak)), label: 'Peak in bucket', area: true, color: C.trace },
          { data: ts.map((p) => Number(p.avg)), label: 'Average in bucket', color: C.alt2 },
        ]}
        peakAt={peakAt}
        peakValue={fmtInt(s.peak_concurrency)}
        height={330}
      />

      <Grid container spacing={2}>
        <Grid item xs={12} md={7}>
          <Paper elevation={0} sx={{ p: 2.25, bgcolor: C.surface, height: '100%' }}>
            <Typography variant="subtitle2" sx={{ fontSize: 14, mb: 0.5 }}>Peak and average by hour</Typography>
            <Typography sx={{ fontSize: 11.5, color: C.muted, mb: 1 }}>
              Hourly peak is the maximum of that hour’s 60 minute values — not an average of averages.
            </Typography>
            {hourly.length ? (
              <BarChart
                height={280}
                xAxis={[{ scaleType: 'band', data: hourly.map((h) => fmtClock(parseTs(h.hour)).slice(5)) }]}
                series={[
                  { data: hourly.map((h) => Number(h.peak)), label: 'Peak', color: C.trace },
                  { data: hourly.map((h) => Number(h.avg)), label: 'Average', color: C.alt },
                ]}
                margin={{ left: 58, right: 16, top: 16, bottom: 46 }}
                grid={{ horizontal: true }}
                slotProps={{ legend: { labelStyle: { fontSize: 11, fill: C.muted }, itemMarkWidth: 9, itemMarkHeight: 9 } }}
                sx={{
                  '& .MuiChartsAxis-line, & .MuiChartsAxis-tick': { stroke: C.line },
                  '& .MuiChartsAxis-tickLabel': { fill: C.muted, fontSize: 10, fontFamily: '"JetBrains Mono", monospace' },
                  '& .MuiChartsGrid-line': { stroke: C.line, strokeDasharray: '2 4' },
                }}
              />
            ) : (
              <Box sx={{ height: 280, display: 'grid', placeItems: 'center' }}>
                <Typography sx={{ color: C.muted, fontSize: 13 }}>No hours to show yet.</Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={5}>
          <Paper elevation={0} sx={{ p: 2.25, bgcolor: C.surface, height: '100%' }}>
            <Typography variant="subtitle2" sx={{ fontSize: 14, mb: 0.5 }}>Platforms, and when each peaked</Typography>
            <Typography sx={{ fontSize: 11.5, color: C.muted, mb: 1 }}>
              Each platform peaks at its own minute. That is why peak can’t be precomputed or rolled up.
            </Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Platform</TableCell>
                  <TableCell align="right">Peak</TableCell>
                  <TableCell align="right">Peaked at</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(d?.platformMix || []).map((p) => (
                  <TableRow key={p.label}>
                    <TableCell sx={{ fontSize: 12.5 }}>{p.label}</TableCell>
                    <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}>
                      {fmtInt(p.peak)}
                    </TableCell>
                    <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11.5, color: C.peak }}>
                      {fmtClock(parseTs(p.peak_minute))}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Grid>
      </Grid>

      <Paper elevation={0} sx={{ p: 2.25, bgcolor: C.surface }}>
        <Typography variant="subtitle2" sx={{ fontSize: 14, mb: 1 }}>Most-watched titles by peak concurrency</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Title</TableCell>
              <TableCell>Type</TableCell>
              <TableCell align="right">Peak</TableCell>
              <TableCell align="right">Peaked at</TableCell>
              <TableCell align="right">Session-minutes</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(d?.topContent || []).map((t) => (
              <TableRow key={t.content_id} hover>
                <TableCell sx={{ fontSize: 12.5 }}>{t.title || `#${t.content_id}`}</TableCell>
                <TableCell sx={{ fontSize: 12, color: C.muted }}>{t.video_type || '—'}</TableCell>
                <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}>
                  {fmtInt(t.peak)}
                </TableCell>
                <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11.5, color: C.peak }}>
                  {fmtClock(parseTs(t.peak_minute))}
                </TableCell>
                <TableCell align="right" sx={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums', color: C.muted }}>
                  {fmtInt(t.session_minutes)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
