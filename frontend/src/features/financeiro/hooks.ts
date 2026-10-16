import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type {
  Fatura,
  FaturaInput,
  FaturaItem,
  FaturaStatus,
  FichaFinanceira,
  Pagamento,
  PagamentoInput,
  Paginated,
  PlanoCobranca,
  PlanoCobrancaInput,
} from "@/types/api";

const FATURAS_KEY = ["faturas"] as const;
const PLANOS_KEY = ["planos-cobranca"] as const;

// Faturas e pagamentos são paginados sempre no backend
// (`PaginacaoCompulsoria`) — 300 alunos por 12 meses são 3.600 linhas por
// ano letivo. Planos e itens usam a paginação opt-in.

interface FaturasFilter {
  status?: FaturaStatus;
  turma?: number;
  aluno?: number;
  competencia?: string;
  search?: string;
}

export function useFaturasPaginated(
  filter: FaturasFilter,
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...FATURAS_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<Fatura>> => {
      const { data } = await api.get<Paginated<Fatura> | Fatura[]>("/faturas/", {
        params: { ...filter, ...pagination },
      });
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
  });
}

// Itens e pagamentos de UMA fatura, pro dialog de detalhe. `enabled`
// evita a requisição enquanto o dialog está fechado.
export function useFaturaItens(faturaId: number | null) {
  return useQuery({
    queryKey: [...FATURAS_KEY, faturaId, "itens"],
    queryFn: async (): Promise<FaturaItem[]> => {
      const { data } = await api.get<Paginated<FaturaItem> | FaturaItem[]>(
        "/fatura-itens/",
        { params: { fatura: faturaId } },
      );
      return normalizarPaginado(data).results;
    },
    enabled: faturaId != null,
  });
}

export function usePagamentosDaFatura(faturaId: number | null) {
  return useQuery({
    queryKey: [...FATURAS_KEY, faturaId, "pagamentos"],
    queryFn: async (): Promise<Pagamento[]> => {
      // `page_size=all` é o opt-out da paginação compulsória: os
      // pagamentos de uma fatura são poucos e o dialog mostra todos.
      const { data } = await api.get<Paginated<Pagamento> | Pagamento[]>(
        "/pagamentos/",
        { params: { fatura: faturaId, page_size: "all" } },
      );
      return normalizarPaginado(data).results;
    },
    enabled: faturaId != null,
  });
}

// Ficha do aluno: uma requisição só, porque a tela mostra totais e os
// três históricos juntos — quatro chamadas paralelas renderizariam a
// ficha em pedaços. A chave entra em FATURAS_KEY pra que registrar ou
// estornar pagamento invalide a ficha também.
export function useFichaFinanceira(alunoId: number | null) {
  return useQuery({
    queryKey: [...FATURAS_KEY, "ficha", alunoId],
    queryFn: async (): Promise<FichaFinanceira> => {
      const { data } = await api.get<FichaFinanceira>(
        `/financeiro/alunos/${alunoId}/`,
      );
      return data;
    },
    enabled: alunoId != null,
  });
}

function invalidarFinanceiro(qc: ReturnType<typeof useQueryClient>) {
  // Pagamento mexe no status e no saldo da fatura, e a geração mexe na
  // listagem: invalidar os dois grupos mantém a tela coerente sem reload.
  qc.invalidateQueries({ queryKey: FATURAS_KEY });
  qc.invalidateQueries({ queryKey: PLANOS_KEY });
}

export function useCreateFatura() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: FaturaInput): Promise<Fatura> => {
      const { data } = await api.post<Fatura>("/faturas/", input);
      return data;
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Fatura criada.");
    },
    // Sem toast de erro: o dialog mostra a mensagem do backend (ex.: aluno
    // já tem fatura nesta competência).
  });
}

export function useUpdateFatura() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<FaturaInput>;
    }): Promise<Fatura> => {
      const { data } = await api.patch<Fatura>(`/faturas/${id}/`, patch);
      return data;
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Fatura atualizada.");
    },
  });
}

// `DELETE` na fatura cancela (status=cancelado), não apaga: fatura é
// documento financeiro. Recusa com 400 quando já tem pagamento — o
// caminho é estornar primeiro.
export function useCancelarFatura() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/faturas/${id}/`);
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Fatura cancelada.");
    },
  });
}

export function useRegistrarPagamento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: PagamentoInput): Promise<Pagamento> => {
      const { data } = await api.post<Pagamento>("/pagamentos/", input);
      return data;
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Pagamento registrado.");
    },
  });
}

// `DELETE` no pagamento é estorno: apaga e reconcilia a fatura de volta.
export function useEstornarPagamento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/pagamentos/${id}/`);
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Pagamento estornado.");
    },
    onError: () => toast.error("Não foi possível estornar o pagamento."),
  });
}

interface PlanosFilter {
  aluno?: number;
  ativo?: boolean;
  search?: string;
}

export function usePlanosCobrancaPaginated(
  filter: PlanosFilter,
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...PLANOS_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<PlanoCobranca>> => {
      const { data } = await api.get<
        Paginated<PlanoCobranca> | PlanoCobranca[]
      >("/planos-cobranca/", { params: { ...filter, ...pagination } });
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
  });
}

// Planos ativos pra popular o select do dialog de fatura. Sem `page`:
// a paginação do endpoint é opt-in, então vem a lista inteira.
export function usePlanosAtivos(enabled = true) {
  return useQuery({
    queryKey: [...PLANOS_KEY, "ativos"],
    queryFn: async (): Promise<PlanoCobranca[]> => {
      const { data } = await api.get<
        Paginated<PlanoCobranca> | PlanoCobranca[]
      >("/planos-cobranca/", { params: { ativo: true } });
      return normalizarPaginado(data).results;
    },
    enabled,
  });
}

export function useCreatePlanoCobranca() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: PlanoCobrancaInput): Promise<PlanoCobranca> => {
      const { data } = await api.post<PlanoCobranca>(
        "/planos-cobranca/",
        input,
      );
      return data;
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Plano de cobrança criado.");
    },
  });
}

export function useUpdatePlanoCobranca() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<PlanoCobrancaInput>;
    }): Promise<PlanoCobranca> => {
      const { data } = await api.patch<PlanoCobranca>(
        `/planos-cobranca/${id}/`,
        patch,
      );
      return data;
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Plano de cobrança atualizado.");
    },
  });
}

// `DELETE` desativa (soft delete). As faturas já emitidas continuam.
export function useDesativarPlanoCobranca() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/planos-cobranca/${id}/`);
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Plano encerrado.");
    },
    onError: () => toast.error("Não foi possível encerrar o plano."),
  });
}

export function useReativarPlanoCobranca() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<PlanoCobranca> => {
      const { data } = await api.patch<PlanoCobranca>(
        `/planos-cobranca/${id}/`,
        { ativo: true },
      );
      return data;
    },
    onSuccess: () => {
      invalidarFinanceiro(qc);
      toast.success("Plano reativado.");
    },
    // O backend recusa (400) quando a reativação sobrepõe a vigência de
    // outro plano ativo do mesmo aluno.
    onError: () =>
      toast.error(
        "Não foi possível reativar. Verifique se o aluno já tem outro plano ativo no período.",
      ),
  });
}
