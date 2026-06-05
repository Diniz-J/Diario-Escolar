import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type {
  PeriodoAvaliativo,
  PeriodoAvaliativoInput,
} from "@/types/api";

// Filtros opcionais aceitos pelo backend (DjangoFilterBackend).
// Quando o componente passa `ativo`, vira `?ativo=true|false` na URL.
interface PeriodosFiltro {
  ano_letivo?: number;
  ativo?: boolean;
}

const PERIODOS_KEY = ["periodos-avaliativos"] as const;

export function usePeriodosAvaliativos(filtro?: PeriodosFiltro) {
  return useQuery({
    queryKey: [...PERIODOS_KEY, filtro ?? {}],
    queryFn: async (): Promise<PeriodoAvaliativo[]> => {
      const { data } = await api.get<PeriodoAvaliativo[]>(
        "/periodos-avaliativos/",
        { params: filtro },
      );
      return data;
    },
  });
}

export function useCreatePeriodoAvaliativo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (
      input: PeriodoAvaliativoInput,
    ): Promise<PeriodoAvaliativo> => {
      const { data } = await api.post<PeriodoAvaliativo>(
        "/periodos-avaliativos/",
        input,
      );
      return data;
    },
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: PERIODOS_KEY });
      toast.success(`Período ${p.nome} criado.`);
    },
    onError: () =>
      toast.error("Não foi possível criar o período. Confira datas e nome."),
  });
}

export function useUpdatePeriodoAvaliativo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<PeriodoAvaliativoInput>;
    }): Promise<PeriodoAvaliativo> => {
      const { data } = await api.patch<PeriodoAvaliativo>(
        `/periodos-avaliativos/${id}/`,
        patch,
      );
      return data;
    },
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: PERIODOS_KEY });
      toast.success(`Período ${p.nome} atualizado.`);
    },
    onError: () => toast.error("Não foi possível atualizar o período."),
  });
}

// Soft delete: backend marca `ativo=False`.
export function useDeactivatePeriodoAvaliativo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/periodos-avaliativos/${id}/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PERIODOS_KEY });
      toast.success("Período desativado.");
    },
    onError: () => toast.error("Não foi possível desativar o período."),
  });
}

// Reativar = PATCH com `ativo=true`. Atalho conveniente pra UI.
export function useReactivatePeriodoAvaliativo() {
  const update = useUpdatePeriodoAvaliativo();
  return {
    ...update,
    mutate: (id: number) => update.mutate({ id, patch: { ativo: true } }),
    mutateAsync: (id: number) =>
      update.mutateAsync({ id, patch: { ativo: true } }),
  };
}
