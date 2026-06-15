import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type {
  ItemPresenca,
  Paginated,
  PresencaStatus,
  RegistroPresenca,
  RegistroPresencaInput,
} from "@/types/api";

const REGISTROS_KEY = ["registros-presenca"] as const;
const ITENS_KEY = ["itens-presenca"] as const;

interface RegistrosFilter {
  turma?: number;
  data?: string;
  // Range de datas (ISO YYYY-MM-DD), filtrado server-side via RegistroPresencaFilter.
  data_inicio?: string;
  data_fim?: string;
}

export function useRegistros(filter: RegistrosFilter = {}) {
  return useQuery({
    queryKey: [...REGISTROS_KEY, filter],
    queryFn: async (): Promise<RegistroPresenca[]> => {
      // Endpoint pagina por default (PaginacaoCompulsoria); este hook
      // serve dashboard/UltimasChamadasCard que precisam de tudo de uma
      // vez — `page_size=all` é o opt-out reservado pra esse caso.
      // `normalizarPaginado` defende contra mudança futura no contrato.
      const { data } = await api.get<
        RegistroPresenca[] | Paginated<RegistroPresenca>
      >("/registros-presenca/", {
        params: { ...filter, page_size: "all" },
      });
      return normalizarPaginado(data).results;
    },
  });
}

// Ver `useAlunosPaginated` em features/alunos/hooks.ts pra justificativa.
export function useRegistrosPaginated(
  filter: RegistrosFilter = {},
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...REGISTROS_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<RegistroPresenca>> => {
      const { data } = await api.get<
        Paginated<RegistroPresenca> | RegistroPresenca[]
      >("/registros-presenca/", { params: { ...filter, ...pagination } });
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
  });
}

export function useRegistro(id: number | undefined) {
  return useQuery({
    queryKey: [...REGISTROS_KEY, "detail", id],
    queryFn: async (): Promise<RegistroPresenca> => {
      const { data } = await api.get<RegistroPresenca>(
        `/registros-presenca/${id}/`,
      );
      return data;
    },
    enabled: id != null && Number.isFinite(id),
  });
}

export function useCreateRegistro() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (
      input: RegistroPresencaInput,
    ): Promise<RegistroPresenca> => {
      const { data } = await api.post<RegistroPresenca>(
        "/registros-presenca/",
        input,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: REGISTROS_KEY });
      qc.invalidateQueries({ queryKey: ITENS_KEY });
      toast.success("Chamada criada.");
    },
    onError: () => toast.error("Não foi possível criar a chamada."),
  });
}

export function useDeleteRegistro() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/registros-presenca/${id}/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: REGISTROS_KEY });
      qc.invalidateQueries({ queryKey: ITENS_KEY });
      toast.success("Chamada excluída.");
    },
    onError: () => toast.error("Não foi possível excluir a chamada."),
  });
}

// Lista itens filtrados por registro (uso típico: tela de chamada).
export function useItensDoRegistro(registroId: number | undefined) {
  return useQuery({
    queryKey: [...ITENS_KEY, { registro: registroId }],
    queryFn: async (): Promise<ItemPresenca[]> => {
      const { data } = await api.get<ItemPresenca[]>("/itens-presenca/", {
        params: { registro: registroId },
      });
      return data;
    },
    enabled: registroId != null && Number.isFinite(registroId),
  });
}

// Atualiza só o status (caso de uso principal: clicar P/A/J/R na chamada).
// Optimistic update: muda na UI imediatamente, reverte se o backend
// rejeitar. Deixa a chamada com sensação de "instantânea".
export function useUpdateItemStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      status,
    }: {
      id: number;
      status: PresencaStatus;
    }): Promise<ItemPresenca> => {
      const { data } = await api.patch<ItemPresenca>(
        `/itens-presenca/${id}/`,
        { status },
      );
      return data;
    },
    onMutate: async ({ id, status }) => {
      // Cancela queries em voo pra evitar overwrite do optimistic.
      await qc.cancelQueries({ queryKey: ITENS_KEY });
      // Atualiza todos os caches de itens já carregados.
      const snapshots = qc.getQueriesData<ItemPresenca[]>({
        queryKey: ITENS_KEY,
      });
      snapshots.forEach(([key, lista]) => {
        if (!lista) return;
        qc.setQueryData<ItemPresenca[]>(
          key,
          lista.map((i) => (i.id === id ? { ...i, status } : i)),
        );
      });
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      // Restaura snapshots em caso de falha.
      ctx?.snapshots.forEach(([key, lista]) => {
        qc.setQueryData(key, lista);
      });
      toast.error("Não foi possível atualizar a presença.");
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ITENS_KEY });
    },
  });
}
