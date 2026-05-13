import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    // Base path: "/" para local, "/portopt/" para GitHub Pages.
    // VITE_BASE é setado pelo workflow .github/workflows/deploy-frontend.yml
    base: env.VITE_BASE || "/",
    server: {
      port: 5173,
      proxy: {
        "/api": "http://localhost:8000",
        "/health": "http://localhost:8000",
      },
    },
  };
});
