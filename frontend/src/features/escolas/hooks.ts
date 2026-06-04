import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Escola } from "@/types/api";

// Listagem read-only. Admin vê todas; usuários comuns recebem apenas a
// sua escola via EscopoEscolaMixin do backend.
const ESCOLAS_KEY = ["escolas"] as const;
const ESCOLAS_IMPORT_KEY = ["escolas", "importacao-em-lote"] as const;

export function useEscolas() {
  return useQuery({
    queryKey: ESCOLAS_KEY,
    queryFn: async (): Promise<Escola[]> => {
      const { data } = await api.get<Escola[]>("/escolas/");
      return data;
    },
  });
}

// Escolas elegíveis à feature de import/export — só as que têm o flag
// comercial ligado (`importacao_em_lote_habilitada=true`). Backend
// devolve 403 nas actions de import/export pra qualquer outra, então
// listar só as habilitadas evita ruído na tela /import.
export function useEscolasElegiveisImportacao() {
  return useQuery({
    queryKey: ESCOLAS_IMPORT_KEY,
    queryFn: async (): Promise<Escola[]> => {
      const { data } = await api.get<Escola[]>(
        "/escolas/?importacao_em_lote_habilitada=true",
      );
      return data;
    },
  });
}
