import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Lecionamento, LecionamentoInput } from "@/types/api";

interface LecionamentosFilter {
  professor?: number;
  turma?: number;
  disciplina?: number;
  ativo?: boolean;
}

const LECIONAMENTOS_KEY = ["lecionamentos"] as const;

// `enabled` permite desligar a query (ex.: id de professor inválido na URL),
// evitando buscar a lista inteira sem escopo. Default true, compatível com
// os chamadores existentes.
export function useLecionamentos(
  filter: LecionamentosFilter = {},
  enabled = true,
) {
  return useQuery({
    queryKey: [...LECIONAMENTOS_KEY, filter],
    queryFn: async (): Promise<Lecionamento[]> => {
      const { data } = await api.get<Lecionamento[]>("/lecionamentos/", {
        params: filter,
      });
      return data;
    },
    enabled,
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: LECIONAMENTOS_KEY });
}

export function useCreateLecionamento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: LecionamentoInput): Promise<Lecionamento> => {
      const { data } = await api.post<Lecionamento>("/lecionamentos/", input);
      return data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteLecionamento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/lecionamentos/${id}/`);
    },
    onSuccess: () => invalidateAll(qc),
  });
}
