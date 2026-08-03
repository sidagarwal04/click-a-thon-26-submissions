import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // Keeps ClickHouse credentials server-side: the browser only ever
      // talks to the API container.
      '/api': { target: 'http://api:8080', changeOrigin: true },
    },
  },
});
