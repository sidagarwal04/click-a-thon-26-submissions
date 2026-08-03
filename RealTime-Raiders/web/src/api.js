const BASE = import.meta.env.VITE_API_BASE || '/api';

const qs = (params) =>
  new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v != null)
  ).toString();

async function get(path, params = {}) {
  const res = await fetch(`${BASE}${path}?${qs(params)}`);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.json();
}

export const fetchMeta = () => get('/meta');
export const fetchOverview = (p) => get('/overview', p);
export const fetchSegments = (p) => get('/segments', p);

/** ClickHouse DateTime strings arrive as 'YYYY-MM-DD HH:MM:SS' in UTC. */
export const parseTs = (s) => (s ? new Date(`${s.replace(' ', 'T')}Z`) : null);

export const fmtInt = (n) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });

export const fmtNum = (n, d = 2) =>
  n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: d });

export const fmtBytes = (b) => {
  if (!b) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB'];
  let i = 0, v = Number(b);
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
};

export const fmtClock = (d) =>
  d ? d.toISOString().slice(0, 16).replace('T', ' ') : '—';
