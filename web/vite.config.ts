import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiPort = process.env.API_PORT ?? "8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/graphql": `http://localhost:${apiPort}` },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router"],
          mui: ["@mui/material", "@emotion/react", "@emotion/styled"],
          grid: ["@mui/x-data-grid"],
          data: ["@apollo/client", "graphql", "oidc-client-ts", "zod", "react-hook-form"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
