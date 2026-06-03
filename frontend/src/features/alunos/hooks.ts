import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type { Aluno, AlunoInput, Paginated } from "@/types/api";

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

// Variante paginada — só dispara quando `pagination.page` for definido.
// O backend (apps.common.pagination.PaginacaoPadrao) só pagina quando
// `page` ou `page_size` aparecem nos query params; sem eles, devolve
// array cru — por isso o `useAlunos` acima segue funcionando intocado.
// `placeholderData: keepPrevious` evita o flicker entre páginas.
export function useAlunosPaginated(
  filter: AlunosFilter = {},
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...ALUNOS_BASE_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<Aluno>> => {
      const { data } = await api.get<Paginated<Aluno> | Aluno[]>(
        "/alunos/",
        { params: { ...filter, ...pagination } },
      );
      // Defesa contra backend ainda na versão sem paginação (preview do
      // frontend rodando contra Render antigo) — normaliza array cru pro
      // envelope DRF esperado pela UI.
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
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
