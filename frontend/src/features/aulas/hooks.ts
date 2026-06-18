import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type {
  AgendaSlot,
  RegistroAula,
  RegistroAulaInput,
} from "@/types/api";

const AULAS_KEY = ["registros-aula"] as const;

interface AulasFilter {
  turma?: number;
  disciplina?: number;
  professor?: number;
  status?: string;
  data_inicio?: string;
  data_fim?: string;
}

// `enabled` permite desligar a query (ex.: id de professor inválido na URL),
// evitando buscar todas as aulas da escola sem escopo. Default true.
export function useRegistrosAula(filter: AulasFilter = {}, enabled = true) {
  return useQuery({
    queryKey: [...AULAS_KEY, filter],
    queryFn: async (): Promise<RegistroAula[]> => {
      const { data } = await api.get<RegistroAula[]>("/registros-aula/", {
        params: filter,
      });
      return data;
    },
    enabled,
  });
}

export function useRegistroAula(id: number | undefined) {
  return useQuery({
    queryKey: [...AULAS_KEY, "detail", id],
    queryFn: async (): Promise<RegistroAula> => {
      const { data } = await api.get<RegistroAula>(`/registros-aula/${id}/`);
      return data;
    },
    enabled: id != null && Number.isFinite(id),
  });
}

interface AgendaParams {
  turma: number;
  disciplina: number;
  // Mês no formato YYYY-MM.
  mes: string;
  professor?: number;
}

// Projeção dos slots de aula do mês — calculada server-side a partir dos
// `dias_semana` do lecionamento (sem tabela). Só dispara com turma,
// disciplina e mês definidos.
export function useAgendaAula(params: Partial<AgendaParams>) {
  const { turma, disciplina, mes, professor } = params;
  return useQuery({
    queryKey: [...AULAS_KEY, "agenda", params],
    queryFn: async (): Promise<AgendaSlot[]> => {
      const { data } = await api.get<AgendaSlot[]>("/registros-aula/agenda/", {
        params: { turma, disciplina, mes, professor },
      });
      return data;
    },
    enabled: turma != null && disciplina != null && !!mes,
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: AULAS_KEY });
}

export function useCreateRegistroAula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: RegistroAulaInput): Promise<RegistroAula> => {
      const { data } = await api.post<RegistroAula>("/registros-aula/", input);
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Aula registrada.");
    },
    onError: () => toast.error("Não foi possível registrar a aula."),
  });
}

export function useUpdateRegistroAula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<RegistroAulaInput>;
    }): Promise<RegistroAula> => {
      const { data } = await api.patch<RegistroAula>(
        `/registros-aula/${id}/`,
        patch,
      );
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Aula atualizada.");
    },
    onError: () => toast.error("Não foi possível atualizar a aula."),
  });
}

// Conferência da direção: `lancado` → `conferido`. A transição é exclusiva
// da action `conferir` (backend grava quem/quando e exige IsAdminOrDiretor),
// então não há equivalente via PATCH de status.
export function useConferirAula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<RegistroAula> => {
      const { data } = await api.post<RegistroAula>(
        `/registros-aula/${id}/conferir/`,
      );
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Aula conferida.");
    },
    onError: () => toast.error("Não foi possível conferir a aula."),
  });
}

export function useDeleteRegistroAula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/registros-aula/${id}/`);
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Registro de aula excluído.");
    },
    onError: () => toast.error("Não foi possível excluir o registro."),
  });
}

// Download via axios+Blob preservando o Bearer (window.location perderia
// auth). Mesmo padrão de features/boletins/hooks.ts; `nomeCustomizado`
// (sem extensão) sobrescreve o nome sugerido pelo backend.
async function baixarBlob(
  url: string,
  params: Record<string, unknown>,
  extensao: string,
  nomeCustomizado?: string,
) {
  const resp = await api.get(url, { params, responseType: "blob" });
  const disp = resp.headers["content-disposition"] as string | undefined;
  const matchNome = disp?.match(/filename="?([^"]+)"?/);
  const nomeDoBackend = matchNome ? matchNome[1] : "download";
  const nomeFinal = nomeCustomizado
    ? `${nomeCustomizado}${extensao}`
    : nomeDoBackend;
  const blobUrl = URL.createObjectURL(resp.data as Blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = nomeFinal;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
}

interface DiarioPdfParams {
  professor: number;
  status?: string;
  data_inicio?: string;
  data_fim?: string;
  turma?: number;
  disciplina?: number;
  // Nome do arquivo sem extensão (do dialog). Sem ele, usa o do backend.
  nome?: string;
}

// PDF do diário do professor (recortado pelos filtros da ficha). O backend
// gera o conteúdo + espaço de assinatura; aqui só disparamos o download.
export function useBaixarDiarioPDF() {
  return useMutation({
    mutationFn: async ({ nome, ...filtros }: DiarioPdfParams): Promise<void> => {
      await baixarBlob("/registros-aula/pdf/", filtros, ".pdf", nome);
    },
    onError: () => toast.error("Não foi possível gerar o PDF do diário."),
  });
}
