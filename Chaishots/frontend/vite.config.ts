import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const LOCAL_API = "http://127.0.0.1:8000";
const DEPLOYED_API = "http://13.233.192.95:8000";

export default defineConfig(({ mode }) => {
  // `mode` is "development" for `vite dev` and "production" for `vite build`.
  // VITE_API_PROXY_TARGET overrides both, so a local dev server can be pointed
  // at the deployed backend without editing this file.
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_PROXY_TARGET ?? (mode === "production" ? DEPLOYED_API : LOCAL_API);

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 3000,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 3000,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
        },
      },
    },
  };
});
