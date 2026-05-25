import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

interface Disciplina {
  id: number;
  escola: number;
  nome: string;
  ativa: boolean;
  criado_em: string;
  atualizado_em: string;
}

const DISCIPLINAS_KEY = ["disciplinas"] as const;

// Listagem read-only — usada para popular selects (form de tarefa).
// CRUD ainda não existe no frontend (gerenciado pelo Django admin).
export function useDisciplinas() {
  return useQuery({
    queryKey: DISCIPLINAS_KEY,
    queryFn: async (): Promise<Disciplina[]> => {
      const { data } = await api.get<Disciplina[]>("/disciplinas/");
      return data;
    },
  });
}
