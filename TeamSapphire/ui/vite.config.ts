import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  // Relative, not '/', so the same build works from a domain root, a GitHub
  // Pages subpath, or a file:// open. The hosted demo lives under
  // /<repo>/<team>/demo/, where absolute asset paths 404 silently.
  base: './',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 3100,
    strictPort: true,
  },
  // Production build served on the same port as dev, so the URL in the
  // demo script and in CORS_ORIGINS never changes between the two.
  preview: {
    port: 3100,
    strictPort: true,
    host: true,
  },
})
