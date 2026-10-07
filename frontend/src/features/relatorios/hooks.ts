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
    onError: () =>
      toast.error("Não foi possível gerar o relatório de frequência."),
  });
}
