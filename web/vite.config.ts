import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8765",
      "/settings": "http://127.0.0.1:8765",
      "/rating-factors": "http://127.0.0.1:8765",
      "/groups": "http://127.0.0.1:8765",
      "/tracks": "http://127.0.0.1:8765",
      "/scan": "http://127.0.0.1:8765",
      "/queue": "http://127.0.0.1:8765",
      "/playlist-runs": "http://127.0.0.1:8765",
      "/media": "http://127.0.0.1:8765",
      "/library": "http://127.0.0.1:8765",
      "/stats": "http://127.0.0.1:8765",
      "/playback-events": "http://127.0.0.1:8765"
    }
  }
});
