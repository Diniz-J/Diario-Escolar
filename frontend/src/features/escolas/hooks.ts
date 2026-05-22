import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Escola } from "@/types/api";

// Listagem read-only. Admin vê todas; usuários comuns recebem apenas a
// sua escola via EscopoEscolaMixin do backend.
const ESCOLAS_KEY = ["escolas"] as const;

export function useEscolas() {
  return useQuery({
    queryKey: ESCOLAS_KEY,
    queryFn: async (): Promise<Escola[]> => {
      const { data } = await api.get<Escola[]>("/escolas/");
      return data;
    },
  });
}
