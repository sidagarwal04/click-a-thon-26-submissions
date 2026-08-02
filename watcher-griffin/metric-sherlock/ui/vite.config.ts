import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-only proxy so the React app can call relative /api, /investigate,
// /healthz paths without CORS -- matches the same relative-path contract
// the nginx reverse proxy uses in the docker-compose production setup
// (see ui/nginx.conf), so no code differs between dev and prod.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8088',
      '/investigate': 'http://127.0.0.1:8088',
      '/healthz': 'http://127.0.0.1:8088',
    },
  },
})
