import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup/vitest.setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "."),
      // Allow tests to import server-only modules without the runtime guard.
      "server-only": resolve(__dirname, "tests/setup/server-only-mock.ts"),
    },
  },
});
