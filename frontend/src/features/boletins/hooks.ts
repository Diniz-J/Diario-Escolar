import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { baixarArquivo } from "@/lib/download";
import type { Boletim } from "@/types/api";

interface BoletimParams {
  data_inicio?: string;
  data_fim?: string;
  // Atalho: passa `?periodo=<id>` em vez de datas. Backend resolve.
  periodo?: number;
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

// PDF do boletim individual. `periodo` opcional (sem ele, gera anual);
// `nome` opcional (sem ele, usa o nome sugerido pelo backend).
export function useBaixarBoletimPDF() {
  return useMutation({
    mutationFn: async (params: {
      alunoId: number;
      periodo?: number;
      nome?: string;
    }): Promise<void> => {
      await baixarArquivo(
        `/boletins/aluno/${params.alunoId}/pdf/`,
        params.periodo ? { periodo: params.periodo } : {},
        ".pdf",
        params.nome,
      );
    },
    onError: () => toast.error("Não foi possível gerar o boletim em PDF."),
  });
}

// Export plano CSV/XLSX das avaliações do aluno na janela.
export function useExportarAvaliacoesAluno() {
  return useMutation({
    mutationFn: async (params: {
      alunoId: number;
      formato: "csv" | "xlsx";
      periodo?: number;
      nome?: string;
    }): Promise<void> => {
      await baixarArquivo(
        `/boletins/aluno/${params.alunoId}/avaliacoes/`,
        {
          formato: params.formato,
          ...(params.periodo ? { periodo: params.periodo } : {}),
        },
        `.${params.formato}`,
        params.nome,
      );
    },
    onError: () => toast.error("Não foi possível exportar as avaliações."),
  });
}
