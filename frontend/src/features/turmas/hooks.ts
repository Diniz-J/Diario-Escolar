import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Turma } from "@/types/api";

const TURMAS_KEY = ["turmas"] as const;

// Por enquanto só listagem — precisamos das turmas pra popular o select
// no form de aluno.
export function useTurmas() {
  return useQuery({
    queryKey: TURMAS_KEY,
    queryFn: async (): Promise<Turma[]> => {
      const { data } = await api.get<Turma[]>("/turmas/");
      return data;
    },
  });
}
