import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
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

// Download de arquivo via axios+Blob — preserva o Bearer no header
// (não dá pra usar `window.location` direto porque perderia auth).
// Cria URL temporária com createObjectURL, dispara click invisível,
// limpa.
async function downloadArquivo(url: string, params: Record<string, unknown>) {
  const resp = await api.get(url, { params, responseType: "blob" });
  // Content-Disposition vem do backend: `attachment; filename="..."`.
  const disp = resp.headers["content-disposition"] as string | undefined;
  const matchNome = disp?.match(/filename="?([^"]+)"?/);
  const nome = matchNome ? matchNome[1] : "download";
  const blobUrl = URL.createObjectURL(resp.data as Blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Libera memória depois de um tick.
  setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
}

// PDF do boletim individual. `periodo` opcional: sem ele, gera anual.
export function useBaixarBoletimPDF() {
  return useMutation({
    mutationFn: async (params: {
      alunoId: number;
      periodo?: number;
    }): Promise<void> => {
      await downloadArquivo(`/boletins/aluno/${params.alunoId}/pdf/`, {
        ...(params.periodo ? { periodo: params.periodo } : {}),
      });
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
    }): Promise<void> => {
      await downloadArquivo(
        `/boletins/aluno/${params.alunoId}/avaliacoes/`,
        {
          formato: params.formato,
          ...(params.periodo ? { periodo: params.periodo } : {}),
        },
      );
    },
    onError: () => toast.error("Não foi possível exportar as avaliações."),
  });
}
