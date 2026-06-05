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
//
// `nomeCustomizado` (sem extensão) sobrescreve o nome sugerido pelo
// backend via Content-Disposition. Quando ausente, usa o nome do
// backend (default `boletim_<matricula>_<periodo>.pdf` etc.).
async function downloadArquivo(
  url: string,
  params: Record<string, unknown>,
  extensao?: string,
  nomeCustomizado?: string,
) {
  const resp = await api.get(url, { params, responseType: "blob" });
  // Content-Disposition vem do backend: `attachment; filename="..."`.
  const disp = resp.headers["content-disposition"] as string | undefined;
  const matchNome = disp?.match(/filename="?([^"]+)"?/);
  const nomeDoBackend = matchNome ? matchNome[1] : "download";
  const nomeFinal = nomeCustomizado
    ? `${nomeCustomizado}${extensao ?? ""}`
    : nomeDoBackend;
  const blobUrl = URL.createObjectURL(resp.data as Blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = nomeFinal;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Libera memória depois de um tick.
  setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
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
      await downloadArquivo(
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
      await downloadArquivo(
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
