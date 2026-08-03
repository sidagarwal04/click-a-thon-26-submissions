import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API holds the ClickHouse credentials; the browser never sees them.
// Proxying /api in dev keeps the frontend origin-clean and means no CORS
// special-casing between dev and a built bundle.
export default defineConfig({
  plugins: [react()],
  // The same proxy has to be declared for `preview` as well as `server`:
  // preview serves the built bundle and does NOT inherit server.proxy, so a
  // demo run from dist would 404 every /api call while dev worked fine.
  server: { port: 5173, proxy: { "/api": "http://localhost:8787" } },
  preview: { port: 5173, proxy: { "/api": "http://localhost:8787" } },
});
