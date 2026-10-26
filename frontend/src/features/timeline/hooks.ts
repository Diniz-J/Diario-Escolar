import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { TimelineAluno } from "@/types/api";

export interface TimelineParams {
  data_inicio?: string;
  data_fim?: string;
}

// Timeline do aluno — endpoint de agregação (sem persistência), no molde
// do boletim: cada chamada remonta a partir de ocorrências, presença e
// histórico cadastral.
export function useTimelineAluno(
  alunoId: number | undefined,
  params: TimelineParams = {},
) {
  return useQuery({
    queryKey: ["timeline-aluno", alunoId, params],
    queryFn: async (): Promise<TimelineAluno> => {
      const { data } = await api.get<TimelineAluno>(
        `/timeline/aluno/${alunoId}/`,
        { params },
      );
      return data;
    },
    enabled: alunoId != null && Number.isFinite(alunoId),
  });
}
