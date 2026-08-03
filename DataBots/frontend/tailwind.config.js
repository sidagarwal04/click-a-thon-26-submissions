/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Steel blue accent — replaces the purple/indigo brand color
        brand: {
          50:  '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        // Neutral dark backgrounds
        surface: {
          50:  '#f8fafc',
          100: '#f1f5f9',
          700: '#1a2234',
          800: '#111827',
          900: '#0d1525',
          950: '#080e1a',
        },
        slate: {
          850: '#151e2e',
          900: '#0f172a',
          950: '#090d16',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'glow-blue':  '0 0 20px rgba(59, 130, 246, 0.15)',
        'glow-red':   '0 0 16px rgba(239, 68, 68, 0.18)',
        'glow-green': '0 0 16px rgba(16, 185, 129, 0.14)',
      },
      animation: {
        'fade-in':    'fadeIn 0.25s ease-out',
        'slide-up':   'slideUp 0.2s ease-out',
        'slide-in-r': 'slideInRight 0.22s ease-out',
      },
      keyframes: {
        fadeIn:       { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp:      { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        slideInRight: { from: { opacity: '0', transform: 'translateX(12px)' }, to: { opacity: '1', transform: 'translateX(0)' } },
      },
    },
  },
  plugins: [],
}
