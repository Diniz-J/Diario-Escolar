import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type {
  EntregaTarefa,
  Paginated,
  Tarefa,
  TarefaInput,
} from "@/types/api";

interface TarefasFilter {
  turma?: number;
  disciplina?: number;
  vale_nota?: boolean;
}

const TAREFAS_BASE_KEY = ["tarefas"] as const;
const ENTREGAS_BASE_KEY = ["entregas-tarefa"] as const;

export function useTarefas(filter: TarefasFilter = {}) {
  return useQuery({
    queryKey: [...TAREFAS_BASE_KEY, filter],
    queryFn: async (): Promise<Tarefa[]> => {
      const { data } = await api.get<Tarefa[]>("/tarefas/", {
        params: filter,
      });
      return data;
    },
  });
}

// Ver `useAlunosPaginated` em features/alunos/hooks.ts pra justificativa.
export function useTarefasPaginated(
  filter: TarefasFilter = {},
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...TAREFAS_BASE_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<Tarefa>> => {
      const { data } = await api.get<Paginated<Tarefa> | Tarefa[]>(
        "/tarefas/",
        { params: { ...filter, ...pagination } },
      );
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
  });
}

export function useTarefa(id: number | undefined) {
  return useQuery({
    queryKey: [...TAREFAS_BASE_KEY, "detail", id],
    queryFn: async (): Promise<Tarefa> => {
      const { data } = await api.get<Tarefa>(`/tarefas/${id}/`);
      return data;
    },
    enabled: id != null && Number.isFinite(id),
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: TAREFAS_BASE_KEY });
  qc.invalidateQueries({ queryKey: ENTREGAS_BASE_KEY });
}

export function useCreateTarefa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: TarefaInput): Promise<Tarefa> => {
      const { data } = await api.post<Tarefa>("/tarefas/", input);
      return data;
    },
    onSuccess: (tarefa) => {
      invalidateAll(qc);
      toast.success(`Tarefa "${tarefa.titulo}" criada.`);
    },
    onError: () => toast.error("Não foi possível criar a tarefa."),
  });
}

export function useUpdateTarefa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<TarefaInput>;
    }): Promise<Tarefa> => {
      const { data } = await api.patch<Tarefa>(`/tarefas/${id}/`, patch);
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Tarefa atualizada.");
    },
    onError: () => toast.error("Não foi possível atualizar a tarefa."),
  });
}

export function useDeleteTarefa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/tarefas/${id}/`);
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Tarefa excluída.");
    },
    onError: () => toast.error("Não foi possível excluir a tarefa."),
  });
}

export function useEntregasDaTarefa(tarefaId: number | undefined) {
  return useQuery({
    queryKey: [...ENTREGAS_BASE_KEY, { tarefa: tarefaId }],
    queryFn: async (): Promise<EntregaTarefa[]> => {
      const { data } = await api.get<EntregaTarefa[]>("/entregas-tarefa/", {
        params: { tarefa: tarefaId },
      });
      return data;
    },
    enabled: tarefaId != null && Number.isFinite(tarefaId),
  });
}

// Atualiza uma entrega com optimistic update — clicar "entregue" muda a
// UI instantaneamente. Se o backend recusar (ex.: nota acima da máxima),
// reverte o snapshot e mostra toast.
export function useUpdateEntrega() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<
        Pick<EntregaTarefa, "entregue" | "data_entrega" | "nota" | "observacao">
      >;
    }): Promise<EntregaTarefa> => {
      const { data } = await api.patch<EntregaTarefa>(
        `/entregas-tarefa/${id}/`,
        patch,
      );
      return data;
    },
    onMutate: async ({ id, patch }) => {
      await qc.cancelQueries({ queryKey: ENTREGAS_BASE_KEY });
      const snapshots = qc.getQueriesData<EntregaTarefa[]>({
        queryKey: ENTREGAS_BASE_KEY,
      });
      snapshots.forEach(([key, lista]) => {
        if (!lista) return;
        qc.setQueryData<EntregaTarefa[]>(
          key,
          lista.map((e) => (e.id === id ? { ...e, ...patch } : e)),
        );
      });
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      ctx?.snapshots.forEach(([key, lista]) => qc.setQueryData(key, lista));
      toast.error("Não foi possível atualizar a entrega.");
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ENTREGAS_BASE_KEY });
    },
  });
}
