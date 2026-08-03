import { useEffect, useState } from 'react';
import { Routes, Route, NavLink, useLocation, Navigate } from 'react-router-dom';
import { Box, Container, Typography, CircularProgress } from '@mui/material';
import Overview from './pages/Overview';
import SegmentAnalysis from './pages/SegmentAnalysis';
import { fetchMeta } from './api';
import { C } from './theme';

const EMPTY = { from: '', to: '', platform: '', country: '', video_type: '', content_id: '' };

function Tab({ to, children }) {
  const { pathname } = useLocation();
  const active = pathname === to;
  return (
    <NavLink to={to} style={{ textDecoration: 'none' }}>
      <Box
        sx={{
          px: 0.25, py: 1.5,
          fontFamily: '"Space Grotesk", sans-serif',
          fontSize: 13.5, fontWeight: 500,
          color: active ? C.text : C.muted,
          borderBottom: `2px solid ${active ? C.trace : 'transparent'}`,
          transition: 'color .15s',
          '&:hover': { color: C.text },
        }}
      >
        {children}
      </Box>
    </NavLink>
  );
}

export default function App() {
  const [meta, setMeta] = useState(null);
  const [filters, setFilters] = useState(EMPTY);
  const [bootErr, setBootErr] = useState(null);

  useEffect(() => {
    fetchMeta()
      .then((m) => {
        setMeta(m);
        setFilters((f) => ({ ...f, from: m.min_minute, to: m.max_minute }));
      })
      .catch((e) => setBootErr(e.message));
  }, []);

  const resetFilters = () =>
    setFilters({ ...EMPTY, from: meta?.min_minute || '', to: meta?.max_minute || '' });

  if (bootErr) {
    return (
      <Container sx={{ py: 10, textAlign: 'center' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Can’t reach the API</Typography>
        <Typography sx={{ color: C.muted, fontSize: 13.5 }}>
          {bootErr}. Check that the api container is up and that conc_minute has rows.
        </Typography>
      </Container>
    );
  }

  if (!meta) {
    return (
      <Box sx={{ height: '100vh', display: 'grid', placeItems: 'center' }}>
        <CircularProgress size={22} sx={{ color: C.trace }} />
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: C.ground }}>
      <Box sx={{ borderBottom: `1px solid ${C.line}`, bgcolor: C.surface }}>
        <Container maxWidth="xl">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
            <Box sx={{ py: 1.5, display: 'flex', alignItems: 'baseline', gap: 1.25 }}>
              <Typography sx={{ fontFamily: '"Space Grotesk", sans-serif', fontWeight: 700, fontSize: 16, letterSpacing: '-0.02em' }}>
                Concurrency Console
              </Typography>
              <Typography sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10.5, color: C.trace, letterSpacing: '0.1em' }}>
                FOREGROUND ONLY
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 3 }}>
              <Tab to="/">Overview</Tab>
              <Tab to="/segments">Segment analysis</Tab>
            </Box>
            <Box sx={{ flex: 1 }} />
            <Typography sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10.5, color: C.muted }}>
              {meta.min_minute?.slice(0, 10)} → {meta.max_minute?.slice(0, 10)}
            </Typography>
          </Box>
        </Container>
      </Box>

      <Container maxWidth="xl" sx={{ py: 2.5 }}>
        <Routes>
          <Route path="/" element={<Overview meta={meta} filters={filters} setFilters={setFilters} resetFilters={resetFilters} />} />
          <Route path="/segments" element={<SegmentAnalysis meta={meta} filters={filters} setFilters={setFilters} resetFilters={resetFilters} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Container>
    </Box>
  );
}
