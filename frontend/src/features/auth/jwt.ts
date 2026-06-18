import { jwtDecode } from "jwt-decode";

import type { JwtPayload } from "./types";

// Helpers para inspecionar o JWT no cliente. Importante: nunca validamos
// assinatura no frontend — isso é responsabilidade do backend, que rejeita
// tokens inválidos com 401. Aqui só lemos os claims.

export function decodeToken(token: string): JwtPayload | null {
  try {
    const payload = jwtDecode<JwtPayload>(token);
    // O SimpleJWT serializa `user_id` como string no claim. Normalizamos
    // pra number aqui — casa com o tipo declarado (JwtPayload.user_id) e
    // com `Professor.usuario` (FK numérica vinda da API). Sem isso,
    // comparações estritas falham com `9 === "9"` => false (ex.: achar o
    // Professor do usuário logado no Diário de Aula).
    return { ...payload, user_id: Number(payload.user_id) };
  } catch {
    // Token corrompido ou malformado — tratado como inválido.
    return null;
  }
}

export function isTokenExpired(payload: JwtPayload): boolean {
  // `exp` é unix em segundos; Date.now() é ms.
  const agora = Math.floor(Date.now() / 1000);
  return payload.exp <= agora;
}
