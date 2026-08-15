import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // :8000 is often another service on this host. Override with ARCHIVERR_API.
        target: process.env.ARCHIVERR_API || "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
});
