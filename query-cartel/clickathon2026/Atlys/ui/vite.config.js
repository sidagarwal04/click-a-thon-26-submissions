import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Dev: proxy all /api/* calls to FastAPI at :8000
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Don't buffer SSE — tool loops stream multiple generations in one response.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            const ct = proxyRes.headers['content-type'] || ''
            if (ct.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache, no-transform'
              proxyRes.headers['x-accel-buffering'] = 'no'
            }
          })
        },
      },
    },
  },
  build: {
    // Production: output goes to service/static/ — FastAPI serves it at /
    outDir: '../service/static',
    emptyOutDir: true,
  },
})
