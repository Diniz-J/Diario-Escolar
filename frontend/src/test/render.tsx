import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { AuthProvider } from "@/features/auth/AuthContext";

// Monta um componente com os três contextos que as telas exigem:
// TanStack Query, rota (os cards usam <Link>) e auth (`useAuth` lança
// erro explícito fora do <AuthProvider>).
//
// `retry: false` é obrigatório, não preferência: com o retry default o
// teste de falha esperaria as tentativas antes de `isError` virar true.
export function renderizar(ui: ReactElement, rotaInicial = "/") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[rotaInicial]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
