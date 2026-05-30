import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // WebSocket routes — must be listed before the generic /resume HTTP rule
      "/resume/chat": { target: "ws://localhost:8000", ws: true },
      "/resume/cover-letter": { target: "ws://localhost:8000", ws: true },
      // HTTP routes
      "/resume": "http://localhost:8000",
      "/jobs": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
