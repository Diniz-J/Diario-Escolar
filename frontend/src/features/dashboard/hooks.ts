import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { MetricasDashboard } from "@/types/api";

// Métricas agregadas do dashboard (presença média + reincidência de
// ocorrências). O endpoint mora na app `relatorios` do backend, onde
// vive a régua de presença efetiva (P/R/J contam, só A é falta), mas o
// hook fica aqui porque quem consome é o dashboard.
//
// A janela é fixa no servidor (30 dias): a tela não tem seletor de
// período, e a resposta devolve as pontas pra sublinha do card.
export function useMetricasDashboard(turmaId: number | null) {
  return useQuery({
    queryKey: ["metricas-dashboard", turmaId],
    queryFn: async (): Promise<MetricasDashboard> => {
      const { data } = await api.get<MetricasDashboard>(
        "/relatorios/dashboard/",
        { params: turmaId ? { turma: turmaId } : {} },
      );
      return data;
    },
  });
}
