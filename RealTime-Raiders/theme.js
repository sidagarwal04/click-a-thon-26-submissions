import { createTheme } from '@mui/material/styles';

/**
 * Palette borrowed from video engineering instruments — waveform monitors
 * and vectorscopes — rather than generic dashboard dark mode. Teal is the
 * trace colour; amber is reserved exclusively for peak markers so that
 * seeing amber anywhere on the page means "this is the moment it peaked".
 */
export const C = {
  ground: '#0B131C',
  surface: '#14202D',
  raised: '#1C2B3A',
  line: 'rgba(232, 239, 245, 0.09)',
  trace: '#3FD0C9',
  peak: '#FFB444',
  alt: '#C874D9',
  alt2: '#6E8CE8',
  alt3: '#5FBF7F',
  text: '#E8EFF5',
  muted: '#7B93A9',
};

export const SERIES_COLORS = [C.trace, C.alt, C.alt2, C.alt3, '#E8825F', '#9AA8D9', '#4FA8C4', '#D9B44F'];

const theme = createTheme({
  palette: {
    mode: 'dark',
    background: { default: C.ground, paper: C.surface },
    primary: { main: C.trace },
    secondary: { main: C.peak },
    text: { primary: C.text, secondary: C.muted },
    divider: C.line,
  },
  typography: {
    fontFamily: '"Inter", system-ui, sans-serif',
    h1: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600, letterSpacing: '-0.02em' },
    h2: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600, letterSpacing: '-0.02em' },
    h6: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600, letterSpacing: '-0.01em' },
    subtitle2: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 500 },
    overline: {
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: 10.5,
      letterSpacing: '0.14em',
      fontWeight: 500,
      color: C.muted,
    },
  },
  shape: { borderRadius: 4 },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: `1px solid ${C.line}`,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: C.line, paddingTop: 10, paddingBottom: 10 },
        head: {
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: 10.5,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: C.muted,
        },
      },
    },
    MuiButtonBase: { defaultProps: { disableRipple: true } },
  },
});

export default theme;
