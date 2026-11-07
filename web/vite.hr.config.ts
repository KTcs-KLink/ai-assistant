import { defineConfig, mergeConfig } from "vite";
import base from "./vite.config.ts";

// Local transport only. Production hosting must route this same path to the BFF.
// No provider keys or environment files are loaded or copied by this configuration.
export default mergeConfig(
  base,
  defineConfig({
    server: {
      host: "127.0.0.1",
      port: 8825,
      strictPort: true,
      proxy: {
        "/api/benefits": {
          target: "http://127.0.0.1:8842",
          changeOrigin: true,
          headers: { origin: "http://127.0.0.1:8842" },
          timeout: 400000,
          proxyTimeout: 400000,
        },
      },
    },
  }),
);
