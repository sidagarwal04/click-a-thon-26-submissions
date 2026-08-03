import { Paper, Box, Typography } from '@mui/material';
import { LineChart } from '@mui/x-charts/LineChart';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';
import { C, SERIES_COLORS } from '../theme';
import { fmtClock } from '../api';

/**
 * The amber reference line is the whole point: peak concurrency is a
 * moment, not an aggregate. Marking exactly when it happened is what
 * makes "you cannot precompute peak" visible rather than just stated.
 */
export default function PeakChart({ title, caption, x, series, peakAt, peakValue, height = 300 }) {
  const empty = !x?.length;

  return (
    <Paper elevation={0} sx={{ p: 2.25, bgcolor: C.surface, height: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 0.5, flexWrap: 'wrap' }}>
        <Typography variant="subtitle2" sx={{ fontSize: 14 }}>{title}</Typography>
        {peakAt && (
          <Typography sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: C.peak }}>
            peak {peakValue} @ {fmtClock(peakAt)}
          </Typography>
        )}
      </Box>
      {caption && <Typography sx={{ fontSize: 11.5, color: C.muted, mb: 1 }}>{caption}</Typography>}

      {empty ? (
        <Box sx={{ height, display: 'grid', placeItems: 'center' }}>
          <Typography sx={{ color: C.muted, fontSize: 13 }}>
            No viewing in this range. Widen the dates or clear a filter.
          </Typography>
        </Box>
      ) : (
        <LineChart
          height={height}
          xAxis={[{ data: x, scaleType: 'time', valueFormatter: (d) => fmtClock(d) }]}
          series={series.map((s, i) => ({
            showMark: false,
            curve: 'linear',
            color: s.color || SERIES_COLORS[i % SERIES_COLORS.length],
            ...s,
          }))}
          margin={{ left: 58, right: 16, top: 16, bottom: 28 }}
          grid={{ horizontal: true }}
          slotProps={{
            legend: {
              labelStyle: { fontSize: 11, fill: C.muted },
              itemMarkWidth: 9, itemMarkHeight: 9, markGap: 5, itemGap: 14,
            },
          }}
          sx={{
            '& .MuiChartsAxis-line, & .MuiChartsAxis-tick': { stroke: C.line },
            '& .MuiChartsAxis-tickLabel': { fill: C.muted, fontSize: 10.5, fontFamily: '"JetBrains Mono", monospace' },
            '& .MuiChartsGrid-line': { stroke: C.line, strokeDasharray: '2 4' },
          }}
        >
          {peakAt && (
            <ChartsReferenceLine
              x={peakAt}
              lineStyle={{ stroke: C.peak, strokeWidth: 1, strokeDasharray: '3 3' }}
              labelStyle={{ fill: C.peak, fontSize: 10, fontFamily: '"JetBrains Mono", monospace' }}
              label="peak"
              labelAlign="start"
            />
          )}
        </LineChart>
      )}
    </Paper>
  );
}
