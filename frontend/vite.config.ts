import { defineConfig } from "vite";
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
});
