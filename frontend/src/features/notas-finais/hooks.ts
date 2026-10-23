import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type {
  LancarNotaFinalItem,
  LancarNotasFinaisResponse,
  NotaPeriodo,
  NotaPeriodoHistoricoEvento,
} from "@/types/api";

interface NotasPeriodoFiltro {
  turma: number;
  disciplina: number;
  periodo: number;
}

const NOTAS_PERIODO_KEY = ["notas-periodo"] as const;

// `inicializar` é POST que garante a existência de NotaPeriodo vazia
// pra cada aluno ativo da turma. Idempotente — chamar duas vezes não
// duplica. Devolve a lista pronta pra montar a tabela.
//
// **Query, apesar de ser POST.** O verbo é POST porque o endpoint pode
// criar linha, mas o significado é "busca-ou-cria": a tela não tem o que
// mostrar antes dele, e o resultado é o mesmo em toda chamada. Como
// mutation ele precisava de um efeito pra disparar quando os três
// selects fechassem — que é o `set-state-in-effect` que o lint acusava,
// e a cascata de render que ele previne. Como query, quem dispara é a
// mudança da `queryKey`, que é justamente o trio.
//
// Consequência de ser query: o refetch no foco da janela também refaz o
// POST. É inofensivo pela idempotência e desejável pela coluna "última
// edição", que fica fresca quando outra pessoa lançou no meio.
export function useNotasPeriodoInicializadas(
  filtro: NotasPeriodoFiltro | null,
) {
  return useQuery({
    queryKey: [...NOTAS_PERIODO_KEY, "inicializadas", filtro ?? {}],
    enabled: filtro !== null,
    queryFn: async (): Promise<NotaPeriodo[]> => {
      const { data } = await api.post<NotaPeriodo[]>(
        "/notas-periodo/inicializar/",
        filtro,
      );
      return data;
    },
  });
}

// GET com filtros. Usado depois do `inicializar` quando o usuário vai
// retornar à tela (cache atualizado).
export function useNotasPeriodo(
  filtro: NotasPeriodoFiltro | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: [...NOTAS_PERIODO_KEY, filtro ?? {}],
    queryFn: async (): Promise<NotaPeriodo[]> => {
      const { data } = await api.get<NotaPeriodo[]>("/notas-periodo/", {
        params: filtro ?? {},
      });
      return data;
    },
    enabled: enabled && filtro != null,
  });
}

export function useLancarNotasFinais() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (params: {
      turma: number;
      disciplina: number;
      periodo: number;
      itens: LancarNotaFinalItem[];
    }): Promise<LancarNotasFinaisResponse> => {
      const { data } = await api.post<LancarNotasFinaisResponse>(
        "/notas-periodo/lancar-em-lote/",
        params,
      );
      return data;
    },
    onSuccess: (data, vars) => {
      // Invalida cache da combinação alvo pra próxima leitura buscar
      // do servidor (ultima_edicao atualizada).
      qc.invalidateQueries({
        queryKey: [
          ...NOTAS_PERIODO_KEY,
          { turma: vars.turma, disciplina: vars.disciplina, periodo: vars.periodo },
        ],
      });
      if (data.atualizadas > 0) {
        toast.success(
          `${data.atualizadas} nota${data.atualizadas > 1 ? "s" : ""} final${data.atualizadas > 1 ? "is" : ""} salva${data.atualizadas > 1 ? "s" : ""}.`,
        );
      }
    },
    onError: () =>
      toast.error("Não foi possível salvar as notas finais."),
  });
}

export function useHistoricoNotaPeriodo(notaId: number | null | undefined) {
  return useQuery({
    queryKey: [...NOTAS_PERIODO_KEY, "historico", notaId],
    queryFn: async (): Promise<NotaPeriodoHistoricoEvento[]> => {
      const { data } = await api.get<{
        eventos: NotaPeriodoHistoricoEvento[];
      }>(`/notas-periodo/${notaId}/historico/`);
      return data.eventos;
    },
    enabled: notaId != null,
  });
}
