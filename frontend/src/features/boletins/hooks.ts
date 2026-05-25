import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Boletim } from "@/types/api";

interface BoletimParams {
  data_inicio?: string;
  data_fim?: string;
}

// Boletim por aluno — endpoint contínuo (sem persistência). Cada chamada
// recalcula no backend.
export function useBoletim(
  alunoId: number | undefined,
  params: BoletimParams = {},
) {
  return useQuery({
    queryKey: ["boletim", alunoId, params],
    queryFn: async (): Promise<Boletim> => {
      const { data } = await api.get<Boletim>(
        `/boletins/aluno/${alunoId}/`,
        { params },
      );
      return data;
    },
    enabled: alunoId != null && Number.isFinite(alunoId),
  });
}
