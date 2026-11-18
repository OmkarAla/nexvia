import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const cornerstonePackages = [
  "@cornerstonejs/core",
  "@cornerstonejs/dicom-image-loader",
  "@cornerstonejs/codec-libjpeg-turbo-8bit",
  "@cornerstonejs/codec-openjpeg",
  "@cornerstonejs/codec-openjph",
  "@cornerstonejs/codec-charls",
];

export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
  resolve: { dedupe: ["@cornerstonejs/core"] },
  optimizeDeps: { include: cornerstonePackages },
  build: { commonjsOptions: { transformMixedEsModules: true } },
  worker: { format: "es" },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
});
