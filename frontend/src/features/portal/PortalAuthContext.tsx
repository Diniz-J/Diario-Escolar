import { createContext, useCallback, useEffect, useState } from "react";

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
 */
export function PortalAuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [responsavel, setResponsavel] = useState<Responsavel | null>(null);
  const [carregando, setCarregando] = useState(true);

  const carregar = useCallback(async () => {
    if (!getPortalAccessToken()) {
      setResponsavel(null);
      setCarregando(false);
      return;
    }
    try {
      const { data } = await portalApi.get<Responsavel>("/me/");
      setResponsavel(data);
    } catch {
      // O interceptor já tentou o refresh. Chegando aqui, a sessão morreu.
      clearPortalTokens();
      setResponsavel(null);
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const entrar = useCallback(
    async (email: string, password: string) => {
      const { data } = await portalApi.post<{
        access: string;
        refresh: string;
      }>("/auth/login/", { email, password });
      setPortalTokens(data);
      const { data: eu } = await portalApi.get<Responsavel>("/me/");
      setResponsavel(eu);
    },
    [],
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
      setResponsavel(null);
    }
  }, []);

  return (
    <PortalAuthContext.Provider
      value={{ responsavel, carregando, entrar, sair }}
    >
      {children}
    </PortalAuthContext.Provider>
  );
}
