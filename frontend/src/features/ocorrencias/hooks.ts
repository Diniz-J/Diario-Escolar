import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type {
  Ocorrencia,
  OcorrenciaInput,
  OcorrenciaStatus,
  Paginated,
} from "@/types/api";

interface OcorrenciasFilter {
  status?: OcorrenciaStatus;
  aluno?: number;
  turma?: number;
  // Range de datas (ISO YYYY-MM-DD), filtrado server-side via OcorrenciaFilter.
  data_inicio?: string;
  data_fim?: string;
}

const OCORRENCIAS_BASE_KEY = ["ocorrencias"] as const;

export function useOcorrencias(filter: OcorrenciasFilter = {}) {
  return useQuery({
    queryKey: [...OCORRENCIAS_BASE_KEY, filter],
    queryFn: async (): Promise<Ocorrencia[]> => {
      const { data } = await api.get<Ocorrencia[]>("/ocorrencias/", {
        params: filter,
      });
      return data;
    },
  });
}

// Ver `useAlunosPaginated` em features/alunos/hooks.ts pra justificativa.
export function useOcorrenciasPaginated(
  filter: OcorrenciasFilter = {},
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...OCORRENCIAS_BASE_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<Ocorrencia>> => {
      const { data } = await api.get<Paginated<Ocorrencia>>("/ocorrencias/", {
        params: { ...filter, ...pagination },
      });
      return data;
    },
    placeholderData: (previous) => previous,
  });
}

export function useOcorrencia(id: number | undefined) {
  return useQuery({
    queryKey: [...OCORRENCIAS_BASE_KEY, "detail", id],
    queryFn: async (): Promise<Ocorrencia> => {
      const { data } = await api.get<Ocorrencia>(`/ocorrencias/${id}/`);
      return data;
    },
    enabled: id != null && Number.isFinite(id),
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: OCORRENCIAS_BASE_KEY });
}

export function useCreateOcorrencia() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: OcorrenciaInput): Promise<Ocorrencia> => {
      const { data } = await api.post<Ocorrencia>("/ocorrencias/", input);
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Ocorrência registrada.");
    },
    onError: () => toast.error("Não foi possível registrar a ocorrência."),
  });
}

export function useUpdateOcorrencia() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<OcorrenciaInput>;
    }): Promise<Ocorrencia> => {
      const { data } = await api.patch<Ocorrencia>(
        `/ocorrencias/${id}/`,
        patch,
      );
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Ocorrência atualizada.");
    },
    onError: () => toast.error("Não foi possível atualizar a ocorrência."),
  });
}

export function useDeleteOcorrencia() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/ocorrencias/${id}/`);
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Ocorrência excluída.");
    },
    onError: () => toast.error("Não foi possível excluir a ocorrência."),
  });
}
