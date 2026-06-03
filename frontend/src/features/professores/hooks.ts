import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Paginated, Professor, ProfessorInput } from "@/types/api";

const PROFESSORES_KEY = ["professores"] as const;

export function useProfessores() {
  return useQuery({
    queryKey: PROFESSORES_KEY,
    queryFn: async (): Promise<Professor[]> => {
      const { data } = await api.get<Professor[]>("/professores/");
      return data;
    },
  });
}

// Ver `useAlunosPaginated` em features/alunos/hooks.ts pra justificativa.
export function useProfessoresPaginated(pagination: {
  page: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: [...PROFESSORES_KEY, "paginated", pagination],
    queryFn: async (): Promise<Paginated<Professor>> => {
      const { data } = await api.get<Paginated<Professor>>("/professores/", {
        params: pagination,
      });
      return data;
    },
    placeholderData: (previous) => previous,
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: PROFESSORES_KEY });
}

export function useCreateProfessor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProfessorInput): Promise<Professor> => {
      const { data } = await api.post<Professor>("/professores/", input);
      return data;
    },
    onSuccess: (p) => {
      invalidateAll(qc);
      toast.success(`Professor ${p.nome_completo || ""} criado.`.trim());
    },
    onError: () => toast.error("Não foi possível criar o professor."),
  });
}

export function useUpdateProfessor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<ProfessorInput>;
    }): Promise<Professor> => {
      const { data } = await api.patch<Professor>(
        `/professores/${id}/`,
        patch,
      );
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Professor atualizado.");
    },
    onError: () => toast.error("Não foi possível atualizar o professor."),
  });
}

// "Excluir" professor é soft delete: marca `ativo=False` em vez de DELETE
// real, porque Tarefa/Ocorrencia/PlanoEnsino apontam pro Professor com
// `on_delete=PROTECT` e o histórico precisa ser preservado. Mesmo padrão
// adotado em Aluno (task #19).
export function useDeactivateProfessor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<Professor> => {
      const { data } = await api.patch<Professor>(`/professores/${id}/`, {
        ativo: false,
      });
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Professor desativado.");
    },
    onError: () => toast.error("Não foi possível desativar o professor."),
  });
}
