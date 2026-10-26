import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";

// Configuração do Vite — bundler de desenvolvimento e build.
// - `react`: ativa Fast Refresh (hot reload de componentes React).
// - `tailwindcss`: processa as classes utility na hora do build.
// - `VitePWA`: gera o manifest e o service worker (app instalável). Ver bloco abaixo.
// - `resolve.alias`: permite importar com `@/components/...` em vez de
//   caminhos relativos com `../../..`. Convenção comum em projetos React.
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // PWA: empacota o front atual como app instalável (responsável lê o
    // portal, professor lança presença no celular). Não é app nativo — é o
    // mesmo build que já roda no Vercel, com manifest + service worker.
    VitePWA({
      // `autoUpdate`: quando sai build novo, o SW se atualiza sozinho e
      // nunca prende o usuário numa versão velha. O registro é injetado
      // automaticamente no index.html (`injectRegister: "auto"`, default),
      // então não há código de registro no main.tsx.
      registerType: "autoUpdate",
      // Ícones já existem em public/ (badges). Entram no precache.
      includeAssets: [
        "favicon.svg",
        "favicon.png",
        "diario-diniz-badge-180.png",
      ],
      manifest: {
        name: "Diário Diniz",
        short_name: "Diário",
        description:
          "Diário Escolar — portal do responsável e lançamento de presença.",
        lang: "pt-BR",
        theme_color: "#3a4524", // --olive-dark (barra de status, igual à sidebar)
        background_color: "#f5efe0", // --paper (tela de splash)
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          {
            src: "/diario-diniz-badge-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/diario-diniz-badge-512.png",
            sizes: "512x512",
            type: "image/png",
          },
          // `maskable`: deixa o Android recortar o ícone no formato do
          // launcher sem cortar conteúdo.
          {
            src: "/diario-diniz-badge-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // O SW cuida só do shell estático (JS/CSS/HTML/ícones/fontes).
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        // A API é a fonte da verdade e NÃO passa pelo SW: a navegação SPA
        // cai no index.html via navigateFallback, e sem este denylist uma
        // rota /api/ serviria o HTML cacheado. (Hoje a API é cross-origin
        // pelo VITE_API_URL e o SW já não a intercepta; o denylist é a
        // garantia explícita caso um dia vire same-origin por proxy.)
        navigateFallbackDenylist: [/^\/api/],
      },
      // Desligado em dev pra não interferir no hot reload.
      devOptions: {
        enabled: false,
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
