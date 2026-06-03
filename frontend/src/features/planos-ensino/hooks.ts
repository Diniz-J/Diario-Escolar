import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type { Paginated, PlanoEnsino, PlanoEnsinoInput } from "@/types/api";

interface PlanosFilter {
  turma?: number;
  disciplina?: number;
  ano_letivo?: number;
  ativo?: boolean;
}

const PLANOS_KEY = ["planos-ensino"] as const;

export function usePlanosEnsino(filter: PlanosFilter = {}) {
  return useQuery({
    queryKey: [...PLANOS_KEY, filter],
    queryFn: async (): Promise<PlanoEnsino[]> => {
      const { data } = await api.get<PlanoEnsino[]>("/planos-ensino/", {
        params: filter,
      });
      return data;
    },
  });
}

// Ver `useAlunosPaginated` em features/alunos/hooks.ts pra justificativa.
export function usePlanosEnsinoPaginated(
  filter: PlanosFilter = {},
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...PLANOS_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<PlanoEnsino>> => {
      const { data } = await api.get<Paginated<PlanoEnsino> | PlanoEnsino[]>(
        "/planos-ensino/",
        { params: { ...filter, ...pagination } },
      );
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
  });
}

export function usePlanoEnsino(id: number | undefined) {
  return useQuery({
    queryKey: [...PLANOS_KEY, "detail", id],
    queryFn: async (): Promise<PlanoEnsino> => {
      const { data } = await api.get<PlanoEnsino>(`/planos-ensino/${id}/`);
      return data;
    },
    enabled: id != null && Number.isFinite(id),
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: PLANOS_KEY });
}

export function useCreatePlanoEnsino() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: PlanoEnsinoInput): Promise<PlanoEnsino> => {
      const { data } = await api.post<PlanoEnsino>("/planos-ensino/", input);
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Plano de ensino criado.");
    },
    onError: () => toast.error("Não foi possível criar o plano."),
  });
}

export function useUpdatePlanoEnsino() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<PlanoEnsinoInput>;
    }): Promise<PlanoEnsino> => {
      const { data } = await api.patch<PlanoEnsino>(
        `/planos-ensino/${id}/`,
        patch,
      );
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Plano atualizado.");
    },
    onError: () => toast.error("Não foi possível atualizar o plano."),
  });
}

export function useDeletePlanoEnsino() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/planos-ensino/${id}/`);
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Plano excluído.");
    },
    onError: () => toast.error("Não foi possível excluir o plano."),
  });
}
