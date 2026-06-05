import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type {
  Avaliacao,
  AvaliacaoInput,
  AvaliacaoTipo,
  LancarNotaItem,
  LancarNotasResponse,
  NotaAvaliacao,
  NotaAvaliacaoHistoricoEvento,
} from "@/types/api";

// Filtros aceitos pelo backend (DjangoFilterBackend) + SearchFilter.
interface AvaliacoesFiltro {
  turma?: number;
  disciplina?: number;
  professor?: number;
  periodo?: number;
  tipo?: AvaliacaoTipo;
  ativo?: boolean;
  search?: string;
}

const AVALIACOES_KEY = ["avaliacoes"] as const;
const NOTAS_KEY = ["notas-avaliacao"] as const;

// --------------------------------------------------------------------
// Avaliacao
// --------------------------------------------------------------------

export function useAvaliacoes(filtro?: AvaliacoesFiltro) {
  return useQuery({
    queryKey: [...AVALIACOES_KEY, filtro ?? {}],
    queryFn: async (): Promise<Avaliacao[]> => {
      const { data } = await api.get<Avaliacao[]>("/avaliacoes/", {
        params: filtro,
      });
      return data;
    },
  });
}

export function useAvaliacao(id: number | null | undefined) {
  return useQuery({
    queryKey: [...AVALIACOES_KEY, id],
    queryFn: async (): Promise<Avaliacao> => {
      const { data } = await api.get<Avaliacao>(`/avaliacoes/${id}/`);
      return data;
    },
    enabled: id != null,
  });
}

export function useCreateAvaliacao() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: AvaliacaoInput): Promise<Avaliacao> => {
      const { data } = await api.post<Avaliacao>("/avaliacoes/", input);
      return data;
    },
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: AVALIACOES_KEY });
      toast.success(`Avaliação "${a.titulo}" criada.`);
    },
    onError: () =>
      toast.error("Não foi possível criar a avaliação."),
  });
}

export function useUpdateAvaliacao() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<AvaliacaoInput>;
    }): Promise<Avaliacao> => {
      const { data } = await api.patch<Avaliacao>(`/avaliacoes/${id}/`, patch);
      return data;
    },
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: AVALIACOES_KEY });
      toast.success(`Avaliação "${a.titulo}" atualizada.`);
    },
    onError: () => toast.error("Não foi possível atualizar a avaliação."),
  });
}

export function useDeactivateAvaliacao() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/avaliacoes/${id}/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: AVALIACOES_KEY });
      toast.success("Avaliação desativada.");
    },
    onError: () => toast.error("Não foi possível desativar a avaliação."),
  });
}

// --------------------------------------------------------------------
// NotaAvaliacao — leitura + lançamento em lote + histórico
// --------------------------------------------------------------------

export function useNotasDaAvaliacao(avaliacaoId: number | null | undefined) {
  return useQuery({
    queryKey: [...NOTAS_KEY, "avaliacao", avaliacaoId],
    queryFn: async (): Promise<NotaAvaliacao[]> => {
      const { data } = await api.get<NotaAvaliacao[]>(`/notas-avaliacao/`, {
        params: { avaliacao: avaliacaoId },
      });
      return data;
    },
    enabled: avaliacaoId != null,
  });
}

// Lançamento em lote: chama POST /avaliacoes/{id}/lancar-notas/ e
// invalida a lista da avaliacao + a propria avaliacao (pra atualizar
// total_alunos/notas_lancadas no card de lista).
export function useLancarNotas(avaliacaoId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (
      itens: LancarNotaItem[],
    ): Promise<LancarNotasResponse> => {
      const { data } = await api.post<LancarNotasResponse>(
        `/avaliacoes/${avaliacaoId}/lancar-notas/`,
        { itens },
      );
      return data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: [...NOTAS_KEY, "avaliacao", avaliacaoId] });
      qc.invalidateQueries({ queryKey: AVALIACOES_KEY });
      if (data.atualizadas > 0) {
        toast.success(
          `${data.atualizadas} nota${data.atualizadas > 1 ? "s" : ""} lançada${data.atualizadas > 1 ? "s" : ""}.`,
        );
      }
    },
    onError: () =>
      toast.error("Não foi possível lançar as notas. Tente novamente."),
  });
}

export function useHistoricoNota(notaId: number | null | undefined) {
  return useQuery({
    queryKey: [...NOTAS_KEY, "historico", notaId],
    queryFn: async (): Promise<NotaAvaliacaoHistoricoEvento[]> => {
      const { data } = await api.get<{
        eventos: NotaAvaliacaoHistoricoEvento[];
      }>(`/notas-avaliacao/${notaId}/historico/`);
      return data.eventos;
    },
    enabled: notaId != null,
  });
}
