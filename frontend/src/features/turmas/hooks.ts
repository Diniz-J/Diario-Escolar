import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Turma, TurmaInput } from "@/types/api";

const TURMAS_KEY = ["turmas"] as const;

export function useTurmas() {
  return useQuery({
    queryKey: TURMAS_KEY,
    queryFn: async (): Promise<Turma[]> => {
      const { data } = await api.get<Turma[]>("/turmas/");
      return data;
    },
  });
}

// Detalhe de uma turma. `enabled` evita disparar quando id ainda não
// está disponível (ex.: render inicial antes do useParams resolver).
export function useTurma(id: number | undefined) {
  return useQuery({
    queryKey: [...TURMAS_KEY, id],
    queryFn: async (): Promise<Turma> => {
      const { data } = await api.get<Turma>(`/turmas/${id}/`);
      return data;
    },
    enabled: id != null && Number.isFinite(id),
  });
}

export function useCreateTurma() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: TurmaInput): Promise<Turma> => {
      const { data } = await api.post<Turma>("/turmas/", input);
      return data;
    },
    onSuccess: (turma) => {
      qc.invalidateQueries({ queryKey: TURMAS_KEY });
      toast.success(`Turma ${turma.nome} criada.`);
    },
    onError: () => toast.error("Não foi possível criar a turma."),
  });
}

export function useUpdateTurma() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<TurmaInput>;
    }): Promise<Turma> => {
      const { data } = await api.patch<Turma>(`/turmas/${id}/`, patch);
      return data;
    },
    onSuccess: (turma) => {
      qc.invalidateQueries({ queryKey: TURMAS_KEY });
      toast.success(`Turma ${turma.nome} atualizada.`);
    },
    onError: () => toast.error("Não foi possível atualizar a turma."),
  });
}

export function useDeleteTurma() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/turmas/${id}/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TURMAS_KEY });
      toast.success("Turma excluída.");
    },
    onError: () => toast.error("Não foi possível excluir a turma."),
  });
}
