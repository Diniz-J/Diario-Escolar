import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App.tsx";
import "./index.css";

// Entry point: monta a árvore React dentro de #root no index.html.
//
// - StrictMode: ativa avisos extras em dev (renderização dupla, deprecations).
//   Sem custo em produção.
// - BrowserRouter: usa a History API do navegador (URLs limpas, ex.: /dashboard).
//   Fornece o contexto que faz `useNavigate`, <Link>, <Routes> funcionarem.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
