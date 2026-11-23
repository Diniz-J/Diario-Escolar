import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type {
  AulaGrade,
  AulaGradeInput,
  ClonagemResultado,
  TempoAula,
  TempoAulaInput,
  Turno,
} from "@/types/api";

const TEMPOS_KEY = ["tempos-aula"] as const;
const GRADE_KEY = ["grade-aulas"] as const;

interface TemposFilter {
  turno?: Turno;
  ativo?: boolean;
}

interface GradeFilter {
  turma?: number;
  dia_semana?: number;
  ativo?: boolean;
}

export function useTemposAula(filter: TemposFilter = {}) {
  return useQuery({
    queryKey: [...TEMPOS_KEY, filter],
    queryFn: async (): Promise<TempoAula[]> => {
      const { data } = await api.get<TempoAula[]>("/tempos-aula/", {
        params: filter,
      });
      return data;
    },
  });
}

// `enabled` desligado enquanto nenhuma turma está escolhida: sem ele a
// tela buscaria a grade da escola inteira só pra descartar.
export function useGradeAulas(filter: GradeFilter, enabled = true) {
  return useQuery({
    queryKey: [...GRADE_KEY, filter],
    queryFn: async (): Promise<AulaGrade[]> => {
      const { data } = await api.get<AulaGrade[]>("/grade-aulas/", {
        params: filter,
      });
      return data;
    },
    enabled,
  });
}

function invalidarTempos(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: TEMPOS_KEY });
  // A matriz da grade exibe horário por tempo: mexer no catálogo muda o
  // que ela mostra, mesmo sem nenhum slot ter mudado.
  qc.invalidateQueries({ queryKey: GRADE_KEY });
}

function invalidarGrade(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: GRADE_KEY });
}

export function useCreateTempoAula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: TempoAulaInput): Promise<TempoAula> => {
      const { data } = await api.post<TempoAula>("/tempos-aula/", input);
      return data;
    },
    onSuccess: () => {
      invalidarTempos(qc);
      toast.success("Tempo cadastrado.");
    },
    // Sem toast de erro: o dialog mostra a mensagem do backend.
  });
}

export function useUpdateTempoAula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<TempoAulaInput>;
    }): Promise<TempoAula> => {
      const { data } = await api.patch<TempoAula>(`/tempos-aula/${id}/`, patch);
      return data;
    },
    onSuccess: () => {
      invalidarTempos(qc);
      toast.success("Tempo atualizado.");
    },
  });
}

export function useDeleteTempoAula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/tempos-aula/${id}/`);
    },
    onSuccess: () => {
      invalidarTempos(qc);
      toast.success("Tempo desativado.");
    },
    onError: () => {
      // O backend usa PROTECT no tempo referenciado por slot: o erro aqui
      // é "ainda está na grade de alguma turma", e o usuário está na
      // listagem, sem dialog onde a frase caberia.
      toast.error("Não foi possível desativar. O tempo pode estar em uso na grade.");
    },
  });
}

export function useCreateSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: AulaGradeInput): Promise<AulaGrade> => {
      const { data } = await api.post<AulaGrade>("/grade-aulas/", input);
      return data;
    },
    onSuccess: () => invalidarGrade(qc),
  });
}

export function useDeleteSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/grade-aulas/${id}/`);
    },
    onSuccess: () => {
      invalidarGrade(qc);
      toast.success("Horário removido.");
    },
  });
}

export function useClonarGrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      turma_origem: number;
      turma_destino: number;
    }): Promise<ClonagemResultado> => {
      const { data } = await api.post<ClonagemResultado>(
        "/grade-aulas/clonar/",
        input,
      );
      return data;
    },
    onSuccess: () => invalidarGrade(qc),
    // Sem toast: o dialog precisa mostrar quantos slots entraram e quais
    // foram ignorados, o que não cabe num toast.
  });
}
