import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import * as Sentry from "@sentry/react";

import App from "./App.tsx";
import "./index.css";

// Sentry — captura exceções de render do React, promises rejeitadas e
// erros pegos pelo nosso ErrorBoundary. Inicializado antes de tudo pra
// não perder erro do próprio bootstrap (ex.: falha de import).
//
// Sem `VITE_SENTRY_DSN` (dev local), o SDK fica inerte. Em prod o DSN
// é injetado na build do Vercel — variáveis VITE_* viram literais no
// bundle, então não há custo de runtime.
const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
if (sentryDsn) {
  // Tunnel: o frontend manda envelopes pro nosso próprio backend em
  // vez do `ingest.sentry.io` direto. Adblockers populares (Opera,
  // uBlock, Brave) bloqueiam o host do Sentry — perderíamos erros de
  // todo usuário com adblock. O backend faz proxy validado (whitelist
  // em settings). Ver `apps/common/sentry_tunnel.py`.
  //
  // Sem `VITE_API_URL` (não devia acontecer em prod), cai pra path
  // relativo "/_sentry/" que ainda pode dar 404 mas pelo menos não
  // crasha o init.
  const apiUrl = import.meta.env.VITE_API_URL || "";
  Sentry.init({
    dsn: sentryDsn,
    tunnel: `${apiUrl}/_sentry/`,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? "production",
    // Só erro, sem APM/tracing — preserva quota do plano free pro que
    // importa (exceções). Pode subir depois se quiser medir latência.
    tracesSampleRate: 0,
    // Não envia URL/headers do usuário sem necessidade (LGPD).
    sendDefaultPii: false,
  });
}

// Entry point: monta a árvore React dentro de #root no index.html.
//
// - StrictMode: ativa avisos extras em dev (renderização dupla, deprecations).
//   Sem custo em produção.
// - BrowserRouter: usa a History API do navegador (URLs limpas, ex.: /dashboard).
//   Fornece o contexto que faz `useNavigate`, <Link>, <Routes> funcionarem.
// - Sentry.ErrorBoundary: pega erro de render que escaparia pro topo,
//   reporta ao Sentry e mostra um fallback. Sem isso, o React unmount
//   silenciosamente o subtree e o usuário vê tela branca.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Sentry.ErrorBoundary
      fallback={
        <div className="min-h-screen flex items-center justify-center p-6 text-center">
          <div className="space-y-2">
            <h1 className="text-xl font-semibold">Algo deu errado.</h1>
            <p className="text-sm text-muted-foreground">
              O erro foi registrado. Recarregue a página pra tentar de novo.
            </p>
          </div>
        </div>
      }
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Sentry.ErrorBoundary>
  </StrictMode>,
);
