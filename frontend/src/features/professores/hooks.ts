import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Professor } from "@/types/api";

const PROFESSORES_KEY = ["professores"] as const;

// Listagem read-only — usada pra popular selects em forms (ex.: quem
// registrou a ocorrência). CRUD de professor entra em fase futura.
export function useProfessores() {
  return useQuery({
    queryKey: PROFESSORES_KEY,
    queryFn: async (): Promise<Professor[]> => {
      const { data } = await api.get<Professor[]>("/professores/");
      return data;
    },
  });
}
