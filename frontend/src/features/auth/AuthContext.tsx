import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "@/lib/api";

import { decodeToken, isTokenExpired } from "./jwt";
import {
  clearTokens,
  getAccessToken,
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
  logout: () => void;
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
  const [user, setUser] = useState<JwtPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Ao montar, tenta ler o token persistido. Se existir e não estiver
  // expirado, hidrata o estado — mantém o usuário logado entre reloads.
  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      const payload = decodeToken(token);
      if (payload && !isTokenExpired(payload)) {
        setUser(payload);
      } else {
        // Token corrompido ou expirado: limpa pra evitar usar.
        clearTokens();
      }
    }
    setIsLoading(false);
  }, []);

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

  const logout = useCallback(() => {
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
