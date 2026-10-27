import { createContext, useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { portalApi } from "./api";
import {
  clearPortalTokens,
  getPortalAccessToken,
  setPortalTokens,
} from "./tokenStorage";

export interface Responsavel {
  id: number;
  nome: string;
  email: string;
  escola_id: number;
}

interface PortalAuthValue {
  responsavel: Responsavel | null;
  carregando: boolean;
  entrar: (email: string, password: string) => Promise<void>;
  sair: () => Promise<void>;
}

export const PortalAuthContext = createContext<PortalAuthValue | null>(null);

// Chave do cache da identidade. Namespace `portal` separa do staff, que
// compartilha o mesmo `QueryClient` (ver comentário no `App.tsx`).
const CHAVE_ME = ["portal", "me"] as const;

/**
 * Sessão do responsável.
 *
 * Diferente do `AuthContext` do staff, que decodifica o JWT pra montar o
 * usuário: aqui a identidade vem de `GET /portal/me/`. O token do portal
 * carrega só `responsavel_id`, `tipo` e a impressão da senha — nome e
 * email não estão nele de propósito, pra não vazar dado de terceiro em
 * token que trafega em log e histórico de navegador.
 *
 * Como efeito colateral útil, o `/me/` valida a sessão de verdade no
 * boot: token revogado por troca de senha ou conta desativada cai aqui,
 * não na primeira tela.
 *
 * O `/me/` é uma **query do TanStack**, não um `useEffect` com estado
 * local. Buscar no mount por efeito era o que sobrava de
 * `react-hooks/set-state-in-effect` no projeto, e a regra recusa isso por
 * desenho — ela marca qualquer chamada assíncrona que termine em
 * `setState` dentro de efeito, mesmo com o `await` na frente. O TanStack
 * já é a ferramenta de dado remoto em todo o resto do app, então aqui ele
 * também cuida de cache, estado de carregamento e deduplicação.
 */
export function PortalAuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const queryClient = useQueryClient();
  // Presença de token: é o que liga e desliga a query. Estado, porque
  // `entrar` e `sair` mudam isso. Lido uma vez, não a cada render.
  const [temToken, setTemToken] = useState(
    () => getPortalAccessToken() != null,
  );

  const meQuery = useQuery({
    queryKey: CHAVE_ME,
    queryFn: async () => {
      try {
        const { data } = await portalApi.get<Responsavel>("/me/");
        return data;
      } catch (err) {
        // O interceptor já tentou o refresh. Chegando aqui, a sessão
        // morreu: limpa o token antes de propagar, senão o próximo boot
        // tentaria validar de novo um token que já sabemos inútil.
        clearPortalTokens();
        throw err;
      }
    },
    // Sem token não há sessão pra validar, e o boot resolve no primeiro
    // render: query desabilitada não busca e não fica em `isLoading`.
    enabled: temToken,
    // A identidade não muda durante a sessão, e o `/me/` já serviu de
    // validação no boot — refetch por foco de janela seria só tráfego.
    // Mantém o comportamento do efeito antigo, que rodava uma vez.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    // O 401 já passou pelo refresh no interceptor; repetir não ajuda.
    retry: false,
  });

  const responsavel = meQuery.data ?? null;
  const carregando = meQuery.isLoading;

  const entrar = useCallback(
    async (email: string, password: string) => {
      const { data } = await portalApi.post<{
        access: string;
        refresh: string;
      }>("/auth/login/", { email, password });
      setPortalTokens(data);
      const { data: eu } = await portalApi.get<Responsavel>("/me/");
      // Semeia o cache em vez de deixar a query buscar de novo — o
      // `/me/` acabou de responder.
      queryClient.setQueryData(CHAVE_ME, eu);
      setTemToken(true);
    },
    [queryClient],
  );

  const sair = useCallback(async () => {
    const refresh = localStorage.getItem("portal_refresh_token");
    try {
      if (refresh) {
        // Invalida o refresh no servidor; sem isso ele seguiria válido
        // pelos 7 dias de validade mesmo depois do logout.
        await portalApi.post("/auth/logout/", { refresh });
      }
    } catch {
      // Logout é melhor-esforço: o que importa pro usuário é sair daqui.
    } finally {
      clearPortalTokens();
      setTemToken(false);
      // Remove em vez de invalidar: invalidar dispararia um `/me/` novo,
      // agora sem token.
      queryClient.removeQueries({ queryKey: CHAVE_ME });
    }
  }, [queryClient]);

  return (
    <PortalAuthContext.Provider
      value={{ responsavel, carregando, entrar, sair }}
    >
      {children}
    </PortalAuthContext.Provider>
  );
}
