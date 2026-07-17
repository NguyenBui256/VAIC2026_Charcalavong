import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Vite config — Story 1.1 skeleton.
// AC6: `npm run dev` boots Vite dev server on :5173 without errors.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true, // allow LAN testing
    strictPort: false,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
