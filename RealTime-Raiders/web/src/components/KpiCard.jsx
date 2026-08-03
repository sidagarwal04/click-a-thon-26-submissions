import { Paper, Box, Typography, Tooltip } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { C } from '../theme';

/**
 * `moment` is the signature of this console: a peak is not a number you
 * can roll up, it is a number that happened at a specific minute. Cards
 * that have one show it in amber directly beneath the value.
 */
export default function KpiCard({ label, value, unit, moment, note, accent = false }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.25,
        height: '100%',
        bgcolor: C.surface,
        borderLeft: accent ? `2px solid ${C.peak}` : `1px solid ${C.line}`,
        display: 'flex',
        flexDirection: 'column',
        gap: 0.75,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <Typography variant="overline">{label}</Typography>
        {note && (
          <Tooltip title={note} placement="top">
            <InfoOutlinedIcon sx={{ fontSize: 13, color: C.muted, opacity: 0.6 }} />
          </Tooltip>
        )}
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.75 }}>
        <Typography
          sx={{
            fontFamily: '"JetBrains Mono", monospace',
            fontWeight: 500,
            fontSize: 27,
            lineHeight: 1.1,
            fontVariantNumeric: 'tabular-nums',
            color: C.text,
          }}
        >
          {value}
        </Typography>
        {unit && (
          <Typography sx={{ fontSize: 11, color: C.muted, fontFamily: '"JetBrains Mono", monospace' }}>
            {unit}
          </Typography>
        )}
      </Box>

      {moment && (
        <Typography
          sx={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: 11,
            color: C.peak,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          ↳ {moment}
        </Typography>
      )}
    </Paper>
  );
}
