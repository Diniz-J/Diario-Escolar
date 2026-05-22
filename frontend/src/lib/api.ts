import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "@/features/auth/tokenStorage";
import type { TokenPair } from "@/features/auth/types";

// Cliente HTTP único do app. Toda chamada à API passa por aqui.
//
// `baseURL` vem da variável de ambiente VITE_API_URL (definida em .env).
// `withCredentials=false` é o default — não enviamos cookies; auth é via
// header Bearer.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: { "Content-Type": "application/json" },
});

// =========================================================================
// Request interceptor: anexa o access token em todo request autenticado.
//
// Endpoints públicos (/auth/token/, /auth/token/refresh/) não devem
// receber o header — se receberem, o backend ainda funciona, mas é mais
// limpo evitar. Por isso, checamos a URL antes de adicionar.
// =========================================================================
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const url = config.url ?? "";
  const isAuthEndpoint = url.includes("/auth/token");
  const token = getAccessToken();
  if (token && !isAuthEndpoint) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// =========================================================================
// Response interceptor: refresh automático em 401.
//
// Fluxo:
// 1. Request original retorna 401.
// 2. Se NÃO for retry e tiver refresh token, chamamos /auth/token/refresh/.
// 3. Se refresh OK: salvamos o novo access, refazemos o request original
//    com o novo header, devolvemos o resultado pro chamador. Tudo
//    transparente — quem chamou nem percebe.
// 4. Se refresh falhar (refresh expirado, revogado, etc.): limpamos tokens
//    e propagamos o erro. Quem ouve via AuthContext detecta o storage
//    vazio e redireciona pra /login.
//
// `_retry` previne loop infinito: se mesmo após refresh der 401, não tenta
// de novo.
// =========================================================================

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

// Promise compartilhada de refresh em andamento. Se 5 requests caírem em
// 401 simultaneamente (cenário comum quando access expira no meio de uma
// página com várias queries), todos esperam o MESMO refresh em vez de
// disparar 5 refreshes paralelos.
let refreshPromise: Promise<string> | null = null;

async function executarRefresh(): Promise<string> {
  const refresh = getRefreshToken();
  if (!refresh) {
    throw new Error("Sem refresh token disponível.");
  }
  // Usa o axios puro (sem interceptor) pra evitar recursão.
  const resp = await axios.post<TokenPair>(
    `${import.meta.env.VITE_API_URL}/auth/token/refresh/`,
    { refresh },
  );
  // O endpoint de refresh devolve só `access`; mantemos o refresh anterior.
  const novoAccess = resp.data.access;
  setTokens({ access: novoAccess, refresh });
  return novoAccess;
}

api.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const original = error.config as RetryableConfig | undefined;
    const status = error.response?.status;
    const url = original?.url ?? "";

    // Não tenta refresh se: status diferente de 401, request já retentado,
    // ou se o próprio request que falhou foi o refresh (refresh expirado).
    const isRefreshCall = url.includes("/auth/token/refresh");
    if (status !== 401 || !original || original._retry || isRefreshCall) {
      return Promise.reject(error);
    }

    original._retry = true;

    try {
      if (!refreshPromise) {
        refreshPromise = executarRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const novoAccess = await refreshPromise;
      original.headers.Authorization = `Bearer ${novoAccess}`;
      return api(original);
    } catch (refreshError) {
      // Refresh falhou: limpa tudo. O AuthProvider vai detectar e mandar
      // o usuário pra /login na próxima renderização.
      clearTokens();
      return Promise.reject(refreshError);
    }
  },
);
