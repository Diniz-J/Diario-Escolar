import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type { Disciplina, DisciplinaInput, Paginated } from "@/types/api";

const DISCIPLINAS_KEY = ["disciplinas"] as const;

export function useDisciplinas() {
  return useQuery({
    queryKey: DISCIPLINAS_KEY,
    queryFn: async (): Promise<Disciplina[]> => {
      const { data } = await api.get<Disciplina[]>("/disciplinas/");
      return data;
    },
  });
}

// Ver `useAlunosPaginated` em features/alunos/hooks.ts pra justificativa.
export function useDisciplinasPaginated(pagination: {
  page: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: [...DISCIPLINAS_KEY, "paginated", pagination],
    queryFn: async (): Promise<Paginated<Disciplina>> => {
      const { data } = await api.get<Paginated<Disciplina> | Disciplina[]>(
        "/disciplinas/",
        { params: pagination },
      );
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
  });
}

export function useCreateDisciplina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: DisciplinaInput): Promise<Disciplina> => {
      const { data } = await api.post<Disciplina>("/disciplinas/", input);
      return data;
    },
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: DISCIPLINAS_KEY });
      toast.success(`Disciplina ${d.nome} criada.`);
    },
    onError: () => toast.error("Não foi possível criar a disciplina."),
  });
}

export function useUpdateDisciplina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<DisciplinaInput>;
    }): Promise<Disciplina> => {
      const { data } = await api.patch<Disciplina>(
        `/disciplinas/${id}/`,
        patch,
      );
      return data;
    },
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: DISCIPLINAS_KEY });
      toast.success(`Disciplina ${d.nome} atualizada.`);
    },
    onError: () => toast.error("Não foi possível atualizar a disciplina."),
  });
}

export function useDeleteDisciplina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/disciplinas/${id}/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: DISCIPLINAS_KEY });
      toast.success("Disciplina excluída.");
    },
    onError: () => toast.error("Não foi possível excluir a disciplina."),
  });
}
