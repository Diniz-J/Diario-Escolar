import { jwtDecode } from "jwt-decode";

import type { JwtPayload } from "./types";

// Helpers para inspecionar o JWT no cliente. Importante: nunca validamos
// assinatura no frontend — isso é responsabilidade do backend, que rejeita
// tokens inválidos com 401. Aqui só lemos os claims.

export function decodeToken(token: string): JwtPayload | null {
  try {
    return jwtDecode<JwtPayload>(token);
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
