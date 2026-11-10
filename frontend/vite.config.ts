// `defineConfig` sai do `vitest/config`, não do `vite`: é o mesmo helper
// com o campo `test` tipado. Com o do `vite`, `tsc -b` reprova o bloco de
// teste abaixo (TS2769) e o `npm run build` quebra junto.
import { defineConfig } from "vitest/config";
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
        // Os chunks de rota ficam FORA do precache. O `React.lazy` do
        // `App.tsx` separa as duas árvores justamente pra o responsável
        // não baixar a UI de gestão — e o precache desfazia isso, porque
        // o service worker é um só por origem e puxava `StaffApp` (454
        // KiB, 107 kB gzip) na instalação de quem só abre o portal.
        // Eles não se perdem: a regra de `runtimeCaching` abaixo guarda
        // o chunk que o usuário de fato carregou. E não há download a
        // mais na primeira visita: o SW instala DEPOIS de a página já ter
        // buscado o chunk de que precisava — o que também significa que
        // o chunk só entra no cache de runtime da SEGUNDA visita em
        // diante, quando o SW já controla a página. Quem abre uma vez só
        // e fica sem rede na seguinte perde o chunk (antes não perdia,
        // porque vinha no precache). Aceito: offline não é escopo do PWA
        // hoje (`CLAUDE.md`, "App mobile (PWA)" — a decisão foi "com
        // conexão na sala"), e tanto o portal quanto a chamada precisam
        // da API de qualquer jeito.
        // Rota nova com `lazy` na raiz entra nesta lista.
        globIgnores: [
          "assets/StaffApp-*.js",
          "assets/PortalApp-*.js",
          // Subsets de fonte que um app pt-BR não chega a pedir. O
          // `@font-face` do fontsource traz `unicode-range`, então o
          // browser só busca o arquivo quando aparece um glifo da faixa —
          // e os acentos do português são precompostos (á = U+00E1), que
          // moram no subset `latin`. Cirílico e vietnamita eram 29,7 KiB
          // baixados na instalação pra nunca serem usados. Continuam no
          // build: se um nome exigir, vem pela rede como qualquer fonte.
          // O `latin-ext` FICA — é dele que saem os sobrenomes
          // poloneses/húngaros/tchecos do sul do país.
          "assets/geist-cyrillic-*.woff2",
          "assets/geist-vietnamese-*.woff2",
          // Tamanhos de ícone que nenhuma marcação pede: o `index.html`
          // usa 16, 32 e 180, e o `manifest` usa 192 e 512. Os arquivos
          // seguem em `public/` (não são meus pra apagar), mas não têm
          // por que ocupar o precache. Atenção ao 128: o backend usa um
          // **de cópia própria** em `apps/common/static/branding/` pro
          // PDF e pros emails — este aqui, o do front, é que não tem
          // quem o referencie.
          "diario-diniz-badge-48.png",
          "diario-diniz-badge-64.png",
          "diario-diniz-badge-128.png",
          "diario-diniz-badge-256.png",
        ],
        runtimeCaching: [
          {
            // `CacheFirst` porque o nome traz hash do conteúdo: a URL é
            // imutável, e build novo gera URL nova em vez de mudar esta.
            // `maxEntries` segura o acúmulo entre deploys.
            urlPattern: /\/assets\/(StaffApp|PortalApp)-[^/]+\.js$/,
            handler: "CacheFirst",
            options: {
              cacheName: "chunks-de-rota",
              expiration: { maxEntries: 6 },
            },
          },
        ],
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
