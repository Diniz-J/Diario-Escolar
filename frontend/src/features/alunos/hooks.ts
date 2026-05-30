import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Aluno, AlunoInput } from "@/types/api";

// `params` opcionais entram tanto na queryKey quanto na URL — assim
// /alunos/?turma=3 e /alunos/ têm caches independentes.
interface AlunosFilter {
  turma?: number;
  ativo?: boolean;
}

const ALUNOS_BASE_KEY = ["alunos"] as const;

export function useAlunos(filter: AlunosFilter = {}) {
  return useQuery({
    queryKey: [...ALUNOS_BASE_KEY, filter],
    queryFn: async (): Promise<Aluno[]> => {
      const { data } = await api.get<Aluno[]>("/alunos/", { params: filter });
      return data;
    },
  });
}

// Invalida o prefixo inteiro de alunos — refetch de todas as variantes
// filtradas que estiverem montadas.
function invalidateAlunos(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ALUNOS_BASE_KEY });
}

export function useCreateAluno() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: AlunoInput): Promise<Aluno> => {
      const { data } = await api.post<Aluno>("/alunos/", input);
      return data;
    },
    onSuccess: (aluno) => {
      invalidateAlunos(qc);
      toast.success(`Aluno ${aluno.nome_completo} criado.`);
    },
    onError: () => toast.error("Não foi possível criar o aluno."),
  });
}

export function useUpdateAluno() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<AlunoInput>;
    }): Promise<Aluno> => {
      const { data } = await api.patch<Aluno>(`/alunos/${id}/`, patch);
      return data;
    },
    onSuccess: (aluno) => {
      invalidateAlunos(qc);
      toast.success(`Aluno ${aluno.nome_completo} atualizado.`);
    },
    onError: () => toast.error("Não foi possível atualizar o aluno."),
  });
}

// O DELETE do backend faz soft delete (marca `ativo=False`). O nome
// segue `useDeleteAluno` por consistência com os outros recursos, mas
// o efeito é "inativar" — o aluno e seu histórico permanecem no banco.
export function useDeleteAluno() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/alunos/${id}/`);
    },
    onSuccess: () => {
      invalidateAlunos(qc);
      toast.success("Aluno inativado.");
    },
    onError: () => toast.error("Não foi possível inativar o aluno."),
  });
}
