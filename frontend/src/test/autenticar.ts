import { setTokens } from "@/features/auth/tokenStorage";
import type { JwtPayload, Perfil } from "@/features/auth/types";

// Semeia uma sessão no localStorage pra telas que dependem de perfil.
//
// O `AuthProvider` hidrata de forma síncrona a partir do token
// (localStorage + decode + checagem de `exp`), então basta gravar um token
// com os claims certos antes de renderizar — sem mock de contexto.
//
// A assinatura é lixo de propósito: o frontend **nunca** valida assinatura
// (ver features/auth/jwt.ts), isso é do backend. O `jwt-decode` só lê o
// payload, então um token forjado aqui é indistinguível de um real pra
// quem consome `useAuth`.
export function autenticarComo(
  perfil: Perfil,
  escolaId: number | null = 1,
): void {
  const payload: JwtPayload = {
    escola_id: escolaId,
    perfil,
    username: `teste.${perfil}`,
    first_name: "Teste",
    last_name: perfil,
    user_id: 1,
    // Uma hora à frente: `isTokenExpired` compara com o relógio, e token
    // vencido faria o provider descartar a sessão em silêncio.
    exp: Math.floor(Date.now() / 1000) + 3600,
    iat: Math.floor(Date.now() / 1000),
    jti: "teste",
    token_type: "access",
  };
  const base64url = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const token = `${base64url({ alg: "HS256", typ: "JWT" })}.${base64url(payload)}.assinatura-de-teste`;
  setTokens({ access: token, refresh: token });
}
