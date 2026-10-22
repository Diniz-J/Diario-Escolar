// `defineConfig` sai do `vitest/config`, não do `vite`: é o mesmo helper
// com o campo `test` tipado. Com o do `vite`, `tsc -b` reprova o bloco de
// teste abaixo (TS2769) e o `npm run build` quebra junto.
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Configuração do Vite — bundler de desenvolvimento e build.
// - `react`: ativa Fast Refresh (hot reload de componentes React).
// - `tailwindcss`: processa as classes utility na hora do build.
// - `resolve.alias`: permite importar com `@/components/...` em vez de
//   caminhos relativos com `../../..`. Convenção comum em projetos React.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Testes: jsdom porque os componentes usam `radix-ui`, que depende de
  // bastante API de DOM (jsdom é o ambiente completo). `VITE_API_URL` é
  // fixada aqui pra os handlers do MSW terem base previsível — em teste a
  // env não existe, e o axios cairia em URL relativa à origem do jsdom.
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    env: { VITE_API_URL: "http://api.test/api/v1" },
  },
});
