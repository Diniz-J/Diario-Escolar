import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { isAxiosError } from "axios";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type {
  Paginated,
  ResponsavelSituacao,
  ResponsavelStaff,
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
