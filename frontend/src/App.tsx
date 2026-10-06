import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";

import { Toaster } from "@/components/ui/sonner";
import { queryClient } from "@/lib/queryClient";

// As duas árvores carregam sob demanda e viram chunks separados: o
// responsável não baixa a UI administrativa e o funcionário não baixa a do
// portal (`PORTAL.md`, seção 4.5). Elas compartilham só o `QueryClient`, o
// `Toaster` e os componentes de `components/ui` — nenhum contexto de
// sessão, porque as sessões são independentes (tokens em chaves próprias).
const StaffApp = lazy(() => import("@/StaffApp"));
const PortalApp = lazy(() => import("@/portal/PortalApp"));

function Carregando() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-sm text-muted-foreground">Carregando...</p>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<Carregando />}>
        <Routes>
          <Route path="/portal/*" element={<PortalApp />} />
          <Route path="/*" element={<StaffApp />} />
        </Routes>
      </Suspense>
      {/* `bottom-right` evita que toasts sobreponham botões de ação
          no canto superior direito das páginas (ex.: Resolver/Arquivar
          em ocorrências). */}
      <Toaster richColors position="bottom-right" />
    </QueryClientProvider>
  );
}

export default App;
