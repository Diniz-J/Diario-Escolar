import { createContext, useCallback, useMemo, useState, type ReactNode } from "react";

import { api } from "@/lib/api";

import { decodeToken, isTokenExpired } from "./jwt";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "./tokenStorage";
import type { JwtPayload, LoginInput, TokenPair } from "./types";

// Estado exposto a qualquer componente via useAuth().
//
// `user` é o payload do JWT (escola_id, perfil, user_id, etc.). É null
// quando o usuário não está logado. Componentes podem usar pra UI
// condicional (ex.: esconder botão "criar turma" pra perfis sem
// permissão).
export interface AuthState {
  user: JwtPayload | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<void>;
  logout: () => Promise<void>;
}

// Context = "carrinho" compartilhado. Componentes leem via useAuth.
// `undefined` como default força o hook a checar que está dentro do
// Provider — se algum componente chamar useAuth sem AuthProvider acima,
// o hook lança erro explícito.
export const AuthContext = createContext<AuthState | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

// Provider: cuida da lógica de login/logout/refresh e expõe via Context.
export function AuthProvider({ children }: AuthProviderProps) {
  // Hidrata do token persistido já no primeiro render — mantém o usuário
  // logado entre reloads. A leitura é síncrona (localStorage + decode do
  // JWT), então um `useEffect` só serviria pra disparar um segundo render,
  // que é o que a regra `react-hooks/set-state-in-effect` acusa. O
  // `clearTokens()` aqui é idempotente, então o duplo-render do StrictMode
  // em dev não causa efeito colateral.
  const [user, setUser] = useState<JwtPayload | null>(() => {
    const token = getAccessToken();
    if (!token) return null;
    const payload = decodeToken(token);
    if (payload && !isTokenExpired(payload)) return payload;
    // Token corrompido ou expirado: limpa pra evitar usar.
    clearTokens();
    return null;
  });
  // Com a hidratação acima no primeiro render, nunca há fase de carregamento:
  // `user` já vem correto antes do primeiro paint. A flag fica na API porque
  // é a emenda pra quando o boot virar assíncrono (ex.: refresh no start) —
  // e o `ProtectedRoute` já sabe esperá-la.
  const [isLoading] = useState(false);

  const login = useCallback(async (input: LoginInput) => {
    // POST /api/v1/auth/token/ — devolve { access, refresh }.
    const resp = await api.post<TokenPair>("/auth/token/", input);
    setTokens(resp.data);
    const payload = decodeToken(resp.data.access);
    if (!payload) {
      throw new Error("Token recebido do servidor é inválido.");
    }
    setUser(payload);
  }, []);

  const logout = useCallback(async () => {
    // Tenta invalidar o refresh no backend (blacklist) antes de limpar local.
    // Falha de rede ou token expirado não bloqueia o logout — sessão local
    // sai do mesmo jeito; o pior caso é o refresh seguir válido até expirar.
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        await api.post("/auth/logout/", { refresh });
      } catch {
        // Backend pode estar fora ou token já inválido — segue o jogo.
      }
    }
    clearTokens();
    setUser(null);
  }, []);

  // `useMemo` evita re-render desnecessário dos consumidores quando o
  // Provider renderiza por outro motivo — só recria o objeto se as
  // dependências mudarem.
  const value = useMemo<AuthState>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      logout,
    }),
    [user, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
