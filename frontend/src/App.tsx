import { QueryClientProvider } from "@tanstack/react-query";

import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/features/auth/AuthContext";
import { queryClient } from "@/lib/queryClient";
import { AppRoutes } from "@/routes";

// Componente raiz: encadeia os provedores globais.
//
// Ordem importa: o AuthProvider faz uma chamada à API (login),
// portanto QueryClientProvider precisa estar acima caso futuramente o
// AuthContext queira usar useQuery internamente. Hoje não usa, mas
// deixar a ordem assim evita refator depois.
//
// <Toaster /> renderiza no canto da tela; toasts são disparados via
// `toast()` do sonner em qualquer ponto do app.
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppRoutes />
        <Toaster richColors position="top-right" />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
