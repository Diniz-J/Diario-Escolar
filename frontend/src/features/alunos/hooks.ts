import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Aluno, AlunoInput } from "@/types/api";

const ALUNOS_KEY = ["alunos"] as const;

export function useAlunos() {
  return useQuery({
    queryKey: ALUNOS_KEY,
    queryFn: async (): Promise<Aluno[]> => {
      const { data } = await api.get<Aluno[]>("/alunos/");
      return data;
    },
  });
}

export function useCreateAluno() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: AlunoInput): Promise<Aluno> => {
      const { data } = await api.post<Aluno>("/alunos/", input);
      return data;
    },
    onSuccess: (aluno) => {
      qc.invalidateQueries({ queryKey: ALUNOS_KEY });
      toast.success(`Aluno ${aluno.nome_completo} criado.`);
    },
    onError: () => {
      // Mensagem específica já é exibida inline no form; toast aqui
      // serve só pra reforçar visualmente. Componente que chama
      // `mutateAsync` ainda pode tratar o erro localmente.
      toast.error("Não foi possível criar o aluno.");
    },
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
      qc.invalidateQueries({ queryKey: ALUNOS_KEY });
      toast.success(`Aluno ${aluno.nome_completo} atualizado.`);
    },
    onError: () => {
      toast.error("Não foi possível atualizar o aluno.");
    },
  });
}

export function useDeleteAluno() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/alunos/${id}/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ALUNOS_KEY });
      toast.success("Aluno excluído.");
    },
    onError: () => {
      // Pode falhar com 400/409 (ex.: aluno tem ocorrências ligadas e
      // backend usa PROTECT). Sinaliza pro usuário sem detalhe técnico.
      toast.error("Não foi possível excluir o aluno.");
    },
  });
}
