import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type {
  Comunicado,
  ComunicadoDestinatario,
  ComunicadoDestinatarioStatus,
  ComunicadoInput,
  ComunicadoPrevia,
  ComunicadoStatus,
  Paginated,
} from "@/types/api";

interface ComunicadosFilter {
  status?: ComunicadoStatus;
  destino?: string;
  turma?: number;
  data_inicio?: string;
  data_fim?: string;
}

const COMUNICADOS_BASE_KEY = ["comunicados"] as const;

// Em produção o disparo roda em background e a resposta do `enviar` volta
// com `status="enviando"` e `total_enviados=0`. Sem re-busca, a tela ficava
// parada nesse estado até o usuário recarregar à mão — justamente na janela
// em que ele mais quer saber se o comunicado saiu. Enquanto houver algo em
// `enviando`, busca de novo neste intervalo; em estado final, desliga.
const POLL_ENVIANDO_MS = 5_000;

export function useComunicadosPaginated(
  filter: ComunicadosFilter = {},
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...COMUNICADOS_BASE_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<Comunicado>> => {
      const { data } = await api.get<Paginated<Comunicado> | Comunicado[]>(
        "/comunicados/",
        { params: { ...filter, ...pagination } },
      );
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
    // Idem no detalhe: se alguma linha da página está em `enviando`, os
    // contadores dela ainda vão mudar.
    refetchInterval: (query) =>
      query.state.data?.results.some((c) => c.status === "enviando")
        ? POLL_ENVIANDO_MS
        : false,
  });
}

export function useComunicado(id: number | undefined) {
  return useQuery({
    queryKey: [...COMUNICADOS_BASE_KEY, "detail", id],
    queryFn: async (): Promise<Comunicado> => {
      const { data } = await api.get<Comunicado>(`/comunicados/${id}/`);
      return data;
    },
    enabled: id != null && Number.isFinite(id),
    // Acompanha o lote até ele terminar; para de buscar em estado final.
    refetchInterval: (query) =>
      query.state.data?.status === "enviando" ? POLL_ENVIANDO_MS : false,
  });
}

/**
 * Alcance do comunicado sem enviar nada — alimenta o diálogo de
 * confirmação.
 *
 * `enabled` é controlado pelo chamador porque só faz sentido buscar
 * quando o diálogo abre: a contagem varre os alunos do público e não
 * precisa rodar junto com a listagem.
 *
 * `staleTime: 0` de propósito: o número tem que refletir o cadastro
 * AGORA (um aluno matriculado há um minuto entra no público), e é o
 * número que o diretor lê antes de disparar.
 */
export function useComunicadoPrevia(
  id: number | undefined,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: [...COMUNICADOS_BASE_KEY, "previa", id],
    queryFn: async (): Promise<ComunicadoPrevia> => {
      const { data } = await api.get<ComunicadoPrevia>(
        `/comunicados/${id}/previa/`,
      );
      return data;
    },
    enabled:
      (options.enabled ?? true) && id != null && Number.isFinite(id),
    staleTime: 0,
  });
}

/** Log de entrega por aluno. `?status=` responde "quem não recebeu". */
export function useComunicadoDestinatarios(
  id: number | undefined,
  filter: { status?: ComunicadoDestinatarioStatus } = {},
  // `poll`: o chamador liga enquanto o comunicado está em `enviando` — as
  // linhas vão mudando de `pendente` pra `enviado`/`falhou` durante o lote.
  options: { enabled?: boolean; poll?: boolean } = {},
) {
  return useQuery({
    queryKey: [...COMUNICADOS_BASE_KEY, "destinatarios", id, filter],
    queryFn: async (): Promise<ComunicadoDestinatario[]> => {
      const { data } = await api.get<ComunicadoDestinatario[]>(
        `/comunicados/${id}/destinatarios/`,
        { params: filter },
      );
      return data;
    },
    enabled:
      (options.enabled ?? true) && id != null && Number.isFinite(id),
    refetchInterval: options.poll ? POLL_ENVIANDO_MS : false,
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: COMUNICADOS_BASE_KEY });
}

export function useCreateComunicado() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: ComunicadoInput): Promise<Comunicado> => {
      const { data } = await api.post<Comunicado>("/comunicados/", input);
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      // Deixa explícito que salvar NÃO envia — o usuário precisa saber
      // que falta um passo.
      toast.success("Rascunho salvo. Nenhum email foi enviado ainda.");
    },
    onError: () => toast.error("Não foi possível salvar o comunicado."),
  });
}

export function useUpdateComunicado() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<ComunicadoInput>;
    }): Promise<Comunicado> => {
      const { data } = await api.patch<Comunicado>(
        `/comunicados/${id}/`,
        patch,
      );
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Rascunho atualizado.");
    },
    onError: () => toast.error("Não foi possível atualizar o comunicado."),
  });
}

export function useDeleteComunicado() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/comunicados/${id}/`);
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Comunicado excluído.");
    },
    onError: () => toast.error("Não foi possível excluir o comunicado."),
  });
}

/**
 * Dispara o comunicado. Ação irreversível — o chamador SEMPRE confirma
 * antes (ver `EnviarComunicadoDialog`).
 *
 * O backend responde 202: em produção o lote continua em background, e
 * por isso o status pode voltar como `enviando`. Invalidar as queries
 * faz a tela buscar o estado final.
 *
 * 409 significa que o comunicado não estava mais em rascunho (duplo
 * clique, ou outra pessoa disparou antes) — a mensagem diferencia esse
 * caso de uma falha real, senão o diretor tentaria de novo.
 */
export function useEnviarComunicado() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<Comunicado> => {
      const { data } = await api.post<Comunicado>(
        `/comunicados/${id}/enviar/`,
        {},
      );
      return data;
    },
    onSuccess: (comunicado) => {
      invalidateAll(qc);
      if (comunicado.status === "falhou") {
        toast.error(
          "O disparo terminou sem nenhum envio concluído. Verifique o log de entrega.",
        );
        return;
      }
      if (comunicado.status === "enviando") {
        toast.success("Envio iniciado. Acompanhe o log de entrega.");
        return;
      }
      toast.success(
        `Comunicado enviado para ${comunicado.total_enviados} ` +
          `${comunicado.total_enviados === 1 ? "responsável" : "responsáveis"}.`,
      );
    },
    onError: (err: unknown) => {
      const status = (
        err as { response?: { status?: number } } | undefined
      )?.response?.status;
      if (status === 409) {
        toast.error(
          "Este comunicado já foi disparado — nenhum email duplicado foi enviado.",
        );
        qc.invalidateQueries({ queryKey: COMUNICADOS_BASE_KEY });
        return;
      }
      toast.error("Não foi possível enviar o comunicado.");
    },
  });
}
