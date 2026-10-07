import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { baixarArquivo } from "@/lib/download";

// Formatos de download do relatório. `json` existe no backend pra quem
// quiser consumir na tela, mas aqui só tratamos os que baixam arquivo.
export type FormatoRelatorio = "pdf" | "csv" | "xlsx";

export interface FrequenciaParams {
  turma: number;
  // `periodo` tem precedência sobre as datas no backend — o dialog manda
  // um ou outro, nunca os dois.
  periodo?: number;
  data_inicio?: string;
  data_fim?: string;
  formato: FormatoRelatorio;
  // Nome do arquivo sem extensão. Sem ele, vale o sugerido pelo backend.
  nome?: string;
}

// Relatório de frequência da turma. O backend monta o conteúdo (incluindo
// o alerta de quem está abaixo do mínimo legal e o espaço de assinatura no
// PDF); aqui só disparamos o download.
export function useBaixarRelatorioFrequencia() {
  return useMutation({
    mutationFn: async ({
      nome,
      formato,
      ...filtros
    }: FrequenciaParams): Promise<void> => {
      await baixarArquivo(
        "/relatorios/frequencia/",
        { ...filtros, formato },
        `.${formato}`,
        nome,
      );
    },
    // Mesmo padrão dos outros dois hooks: `baixarArquivo` desembrulha o
    // detalhe do corpo em Blob (404 de turma, 400 de período ou datas).
    onError: (erro: Error) =>
      toast.error(
        erro.message || "Não foi possível gerar o relatório de frequência.",
      ),
  });
}

export interface OcorrenciasExportParams {
  // Só os filtros server-side da listagem. A busca da tela de
  // ocorrências é client-side (filtra nome de aluno e turma em JS) e
  // não tem equivalente no backend — mandá-la aqui viraria busca em
  // `descricao`, que é outra coisa.
  status?: string;
  data_inicio?: string;
  data_fim?: string;
  turma?: number;
  aluno?: number;
  formato: FormatoRelatorio;
  nome?: string;
}

// Exporta o mesmo recorte da listagem de ocorrências. O endpoint é uma
// action do próprio viewset, então os filtros valem lá exatamente como
// na tela.
export function useExportarOcorrencias() {
  return useMutation({
    mutationFn: async ({
      nome,
      formato,
      ...filtros
    }: OcorrenciasExportParams): Promise<void> => {
      await baixarArquivo(
        "/ocorrencias/exportar/",
        { ...filtros, formato },
        `.${formato}`,
        nome,
      );
    },
    onError: (erro: Error) => {
      // O backend recusa PDF de recorte muito grande e explica o que
      // fazer; `baixarArquivo` já desembrulha o detalhe do corpo em Blob.
      toast.error(
        erro.message || "Não foi possível exportar as ocorrências.",
      );
    },
  });
}

export interface AlunosExportParams {
  turma?: number;
  ativo?: boolean;
  formato: FormatoRelatorio;
  nome?: string;
}

// Relatório cadastral de alunos. Endpoint separado do `/alunos/export/`,
// que é o serviço de migração em massa (admin global + flag comercial):
// este é a lista que a secretaria tira da própria escola, e sai com o
// mesmo recorte da tela.
export function useExportarAlunos() {
  return useMutation({
    mutationFn: async ({
      nome,
      formato,
      ...filtros
    }: AlunosExportParams): Promise<void> => {
      await baixarArquivo(
        "/alunos/relatorio/",
        { ...filtros, formato },
        `.${formato}`,
        nome,
      );
    },
    onError: (erro: Error) => {
      // `baixarArquivo` desembrulha o detalhe do corpo em Blob — é por
      // ali que vem o aviso de recorte grande demais pro PDF.
      toast.error(erro.message || "Não foi possível exportar os alunos.");
    },
  });
}
