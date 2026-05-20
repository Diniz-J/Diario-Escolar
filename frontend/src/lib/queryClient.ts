import { QueryClient } from "@tanstack/react-query";

// Instância única do QueryClient — gerencia o cache de TODA query do app.
//
// Defaults sensatos pra app autenticado:
// - `staleTime`: por 30s, dados são considerados "frescos" — não refaz
//   request automaticamente. Reduz tráfego em navegação rápida.
// - `gcTime`: 5min sem componentes usando uma query → cache é descartado.
// - `retry`: 1 tentativa extra em caso de falha. 401 e 403 NÃO devem
//   retentar (refresh já é tratado pelo interceptor do axios).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: (failureCount, error) => {
        // Erros de auth/permissão não são transitórios — não retentar.
        const status =
          typeof error === "object" && error !== null && "response" in error
            ? (error as { response?: { status?: number } }).response?.status
            : undefined;
        if (status === 401 || status === 403) return false;
        return failureCount < 1;
      },
    },
  },
});
