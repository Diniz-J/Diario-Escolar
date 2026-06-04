import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";

// 5 entidades cobertas pelo backend (apps/escola/resources.py +
// apps/planos_ensino/resources.py). O `path` é o prefixo do ViewSet
// (registrado em apps.escola.urls / apps.planos_ensino.urls).
export type EntidadeImportExport =
  | "alunos"
  | "turmas"
  | "disciplinas"
  | "professores"
  | "lecionamentos"
  | "planos-ensino";

export const ENTIDADES: { value: EntidadeImportExport; label: string }[] = [
  { value: "alunos", label: "Alunos" },
  { value: "turmas", label: "Turmas" },
  { value: "disciplinas", label: "Disciplinas" },
  { value: "professores", label: "Professores" },
  { value: "lecionamentos", label: "Lecionamentos (professor × turma × disciplina)" },
  { value: "planos-ensino", label: "Planos de ensino" },
];

// Resposta do POST `/{entidade}/import/`. Estrutura definida em
// `apps/common/import_export.executar_import`.
export interface ImportResultado {
  criados: number;
  pulados: { linha: string; motivo: string }[];
  erros: { linha: number | null; campo?: string | null; mensagem: string }[];
  persistido: boolean;
}

interface ImportInput {
  entidade: EntidadeImportExport;
  arquivo: File;
  confirmar: boolean;
  // Escola alvo — admin global precisa passar via `?escola=<id>` porque
  // o JWT dele não tem `escola_id`. Tela /import só lista escolas com
  // `importacao_em_lote_habilitada=true`, então o select já filtra
  // pelo pacote contratado.
  escolaId: number;
  // Só faz sentido pra `alunos` (cria turma faltante automaticamente).
  extras?: {
    turno_padrao?: string;
    ano_letivo_padrao?: string;
  };
}

// `useImportar` cobre os 2 modos: pré-visualização (`confirmar=false`)
// e persistência (`confirmar=true`). O backend roda dry-run no primeiro
// caso (savepoint roll back tudo, inclusive turma criada na hora).
export function useImportar() {
  return useMutation({
    mutationFn: async (input: ImportInput): Promise<ImportResultado> => {
      const formData = new FormData();
      formData.append("arquivo", input.arquivo);
      if (input.extras?.turno_padrao) {
        formData.append("turno_padrao", input.extras.turno_padrao);
      }
      if (input.extras?.ano_letivo_padrao) {
        formData.append("ano_letivo_padrao", input.extras.ano_letivo_padrao);
      }
      const params = new URLSearchParams({ escola: String(input.escolaId) });
      if (input.confirmar) params.set("confirmar", "true");
      const url = `/${input.entidade}/import/?${params.toString()}`;
      const { data } = await api.post<ImportResultado>(url, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
  });
}

// Download utilitário pra template ou export. Browser dispara o save
// via `<a>` temporário porque axios devolve blob inline.
async function baixarComoArquivo(
  url: string,
  nomeSugerido: string,
): Promise<void> {
  const resp = await api.get(url, { responseType: "blob" });
  const contentType = resp.headers["content-type"];
  const blob = new Blob([resp.data], {
    type:
      typeof contentType === "string"
        ? contentType
        : "application/octet-stream",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = nomeSugerido;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

export function useBaixarTemplate() {
  return useMutation({
    mutationFn: async (input: {
      entidade: EntidadeImportExport;
      formato: "csv" | "xlsx";
      escolaId: number;
    }) => {
      const params = new URLSearchParams({
        formato: input.formato,
        escola: String(input.escolaId),
      });
      const url = `/${input.entidade}/template/?${params.toString()}`;
      await baixarComoArquivo(
        url,
        `${input.entidade}_modelo.${input.formato}`,
      );
    },
  });
}

export function useExportar() {
  return useMutation({
    mutationFn: async (input: {
      entidade: EntidadeImportExport;
      formato: "csv" | "xlsx";
      escolaId: number;
    }) => {
      const params = new URLSearchParams({
        formato: input.formato,
        escola: String(input.escolaId),
      });
      const url = `/${input.entidade}/export/?${params.toString()}`;
      await baixarComoArquivo(
        url,
        `${input.entidade}.${input.formato}`,
      );
    },
  });
}
