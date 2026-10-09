import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { isAxiosError } from "axios";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type {
  Paginated,
  ResponsavelCriacaoInput,
  ResponsavelSituacao,
  ResponsavelStaff,
  VinculoResponsavel,
  VinculoResponsavelInput,
} from "@/types/api";

const RESPONSAVEIS_KEY = ["responsaveis"] as const;

interface ResponsaveisFilter {
  situacao?: ResponsavelSituacao;
  search?: string;
}

// Paginado sempre: um responsável por família, centenas numa escola.
export function useResponsaveisPaginated(
  filter: ResponsaveisFilter,
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...RESPONSAVEIS_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<ResponsavelStaff>> => {
      const { data } = await api.get<
        Paginated<ResponsavelStaff> | ResponsavelStaff[]
      >("/responsaveis/", { params: { ...filter, ...pagination } });
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
  });
}

/**
 * Dispara o convite de primeira ativação.
 *
 * O backend valida o que a UI não deve adivinhar: conta inativa e conta que
 * já ativou o acesso devolvem 400 com mensagem própria (pra essa, o caminho
 * é o "esqueci a senha" do próprio responsável), e 502 quando o email não
 * saiu. As três chegam ao usuário como estão — a secretaria precisa saber
 * qual é o caso.
 */
export function useConvidarResponsavel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<{ detail: string }> => {
      const { data } = await api.post<{ detail: string }>(
        `/responsaveis/${id}/convidar/`,
      );
      return data;
    },
    onSuccess: (data) => {
      // Invalida a listagem: a situação da linha muda pra "convidado".
      qc.invalidateQueries({ queryKey: RESPONSAVEIS_KEY });
      toast.success(data.detail);
    },
    onError: (err) => {
      if (isAxiosError(err)) {
        // O 429 vem ANTES do `detail`: o throttle do DRF responde
        // `{"detail": "Request was throttled. Expected available in N
        // seconds."}`, em inglês. Na ordem inversa, essa frase é que
        // chegava na tela da secretaria.
        if (err.response?.status === 429) {
          toast.error(
            "Muitos convites em pouco tempo. Aguarde alguns minutos.",
          );
          return;
        }
        const detail = err.response?.data?.detail;
        if (typeof detail === "string") {
          toast.error(detail);
          return;
        }
      }
      toast.error("Não foi possível enviar o convite.");
    },
  });
}

const VINCULOS_KEY = ["vinculos-responsavel"] as const;

/**
 * Vínculos de UM responsável.
 *
 * Sempre escopado: o backend recusa (400) a listagem sem `?responsavel=`
 * ou `?aluno=` — mesma escolha dos endpoints matriz, porque a tela só
 * pede os filhos de uma família e paginar isso seria ruído. Por isso a
 * query só dispara com id definido.
 */
export function useVinculosDoResponsavel(responsavelId: number | null) {
  return useQuery({
    queryKey: [...VINCULOS_KEY, responsavelId],
    enabled: responsavelId != null,
    queryFn: async (): Promise<VinculoResponsavel[]> => {
      const { data } = await api.get<VinculoResponsavel[]>(
        "/vinculos-responsavel/",
        { params: { responsavel: responsavelId } },
      );
      return data;
    },
  });
}

// Mensagem de erro do backend, que aqui vem por campo
// (`{responsavel: [...]}`, `{aluno: [...]}`) e não como `detail`: as duas
// camadas de guard de escola reportam no campo que falhou, e a secretaria
// precisa ler qual lado está errado.
function primeiraMensagem(err: unknown, fallback: string): string {
  if (isAxiosError(err) && err.response?.data) {
    const data = err.response.data as Record<string, unknown>;
    if (typeof data.detail === "string") return data.detail;
    const msg = Object.values(data)
      .flat()
      .find((v): v is string => typeof v === "string");
    if (msg) return msg;
  }
  return fallback;
}

export function useCriarVinculo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (
      input: VinculoResponsavelInput,
    ): Promise<VinculoResponsavel> => {
      const { data } = await api.post<VinculoResponsavel>(
        "/vinculos-responsavel/",
        input,
      );
      return data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: VINCULOS_KEY });
      // A listagem de responsáveis mostra os filhos de cada linha.
      qc.invalidateQueries({ queryKey: RESPONSAVEIS_KEY });
      toast.success(`${data.aluno_nome} vinculado.`);
    },
    onError: (err) => {
      toast.error(primeiraMensagem(err, "Não foi possível vincular."));
    },
  });
}

export function useRemoverVinculo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/vinculos-responsavel/${id}/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: VINCULOS_KEY });
      qc.invalidateQueries({ queryKey: RESPONSAVEIS_KEY });
      toast.success("Vínculo removido.");
    },
    onError: (err) => {
      toast.error(primeiraMensagem(err, "Não foi possível remover o vínculo."));
    },
  });
}

/**
 * Cria a conta de responsável.
 *
 * Entrou na fatia 4 revertendo a somente-leitura da 6b: a semeadura faz
 * uma conta por família, então sem isto o segundo responsável só nasceria
 * no `/admin/`. A conta nasce sem senha utilizável — criar não dá acesso,
 * quem dá é o convite.
 */
export function useCriarResponsavel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (
      input: ResponsavelCriacaoInput,
    ): Promise<ResponsavelStaff> => {
      const { data } = await api.post<ResponsavelStaff>(
        "/responsaveis/",
        input,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: RESPONSAVEIS_KEY });
    },
  });
}
