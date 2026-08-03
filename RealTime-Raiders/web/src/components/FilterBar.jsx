import { Paper, Box, TextField, MenuItem, Button, Typography } from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import dayjs from 'dayjs';
import { C } from '../theme';

// ClickHouse hands back naive 'YYYY-MM-DD HH:MM:SS' strings that the charts
// render as-is. Parsing them as naive wall-clock — no timezone applied — means
// what the picker shows matches what the charts show. Treating them as UTC and
// letting dayjs localise would shift every filter by the browser's offset.
const toDay = (s) => (s ? dayjs(s, 'YYYY-MM-DD HH:mm:ss') : null);
const fromDay = (d) => (d && d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : '');

export default function FilterBar({ meta, filters, onChange, onReset, extra }) {
  const set = (k) => (e) => onChange({ ...filters, [k]: e.target.value });

  const field = {
    size: 'small',
    sx: {
      minWidth: 158,
      '& .MuiInputBase-root': { bgcolor: C.ground, fontSize: 13 },
      '& .MuiInputLabel-root': { fontSize: 12.5 },
    },
  };

  // Clamp to the data actually loaded, so you can't silently pick an empty range.
  const minDT = toDay(meta?.min_minute);
  const maxDT = toDay(meta?.max_minute);

  const pickerSlots = {
    textField: {
      size: 'small',
      sx: {
        minWidth: 210,
        '& .MuiInputBase-root': {
          bgcolor: C.ground,
          fontSize: 13,
          fontFamily: '"JetBrains Mono", monospace',
        },
        '& .MuiInputLabel-root': { fontSize: 12.5, fontFamily: '"Inter", sans-serif' },
      },
    },
    // Match the console's instrument look rather than the default light popover.
    desktopPaper: {
      sx: {
        bgcolor: C.surface,
        border: `1px solid ${C.line}`,
        backgroundImage: 'none',
        '& .MuiPickersDay-root': { fontFamily: '"JetBrains Mono", monospace', fontSize: 12.5 },
        '& .MuiMultiSectionDigitalClockSection-item': {
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: 12.5,
        },
      },
    },
    actionBar: { actions: ['clear', 'today', 'accept'] },
  };

  return (
    <Paper elevation={0} sx={{ p: 1.75, bgcolor: C.surface }}>
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
        <Typography variant="overline" sx={{ mr: 0.5 }}>Filters</Typography>

        <DateTimePicker
          label="From"
          value={toDay(filters.from)}
          onChange={(d) => onChange({ ...filters, from: fromDay(d) })}
          minDateTime={minDT}
          maxDateTime={toDay(filters.to) || maxDT}
          ampm={false}
          format="YYYY-MM-DD HH:mm"
          views={['year', 'month', 'day', 'hours', 'minutes']}
          slotProps={pickerSlots}
        />

        <DateTimePicker
          label="To"
          value={toDay(filters.to)}
          onChange={(d) => onChange({ ...filters, to: fromDay(d) })}
          minDateTime={toDay(filters.from) || minDT}
          maxDateTime={maxDT}
          ampm={false}
          format="YYYY-MM-DD HH:mm"
          views={['year', 'month', 'day', 'hours', 'minutes']}
          slotProps={pickerSlots}
        />

        <TextField {...field} select label="Platform" value={filters.platform || ''} onChange={set('platform')}>
          <MenuItem value="">All platforms</MenuItem>
          {(meta?.platforms || []).map((p) => <MenuItem key={p} value={p}>{p}</MenuItem>)}
        </TextField>

        <TextField {...field} select label="Country" value={filters.country || ''} onChange={set('country')}>
          <MenuItem value="">All countries</MenuItem>
          {(meta?.countries || []).map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
        </TextField>

        <TextField {...field} select label="Content type" value={filters.video_type || ''} onChange={set('video_type')}>
          <MenuItem value="">All types</MenuItem>
          {(meta?.video_types || []).map((v) => <MenuItem key={v} value={v}>{v}</MenuItem>)}
        </TextField>

        {extra}

        <Box sx={{ flex: 1 }} />
        <Button size="small" startIcon={<RestartAltIcon sx={{ fontSize: 16 }} />} onClick={onReset}
          sx={{ color: C.muted, fontSize: 12.5, textTransform: 'none' }}>
          Reset
        </Button>
      </Box>
    </Paper>
  );
}