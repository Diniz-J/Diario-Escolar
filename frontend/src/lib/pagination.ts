import type { Paginated } from "@/types/api";

// Aceita tanto o envelope DRF (`Paginated<T>`) quanto array cru.
// Útil enquanto o backend convive em fases — o frontend novo pode rodar
// contra um backend ainda sem o middleware de paginação (preview do
// Vercel apontando pra Render ainda na versão antiga).
export function normalizarPaginado<T>(
  data: Paginated<T> | T[],
): Paginated<T> {
  if (Array.isArray(data)) {
    return { count: data.length, next: null, previous: null, results: data };
  }
  return data;
}
