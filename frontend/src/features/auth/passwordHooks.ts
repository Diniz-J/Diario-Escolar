import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";

// Resposta dos endpoints de password reset/change — só o `detail` é
// usado pelo frontend (vai pro toast). `email` aparece no /change/ pra
// confirmar pra qual endereço o link foi enviado.
interface PasswordResponse {
  detail: string;
  email?: string;
}

// `useRequestPasswordReset` — POST /auth/password/reset/request/.
// Público. Recebe `username`; backend resolve o email cadastrado e
// envia o link. Resposta sempre 200 (anti-enumeração).
export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: async (username: string): Promise<PasswordResponse> => {
      const { data } = await api.post<PasswordResponse>(
        "/auth/password/reset/request/",
        { username },
      );
      return data;
    },
  });
}

// `useConfirmPasswordReset` — POST /auth/password/reset/confirm/.
// Público. Recebe token + nova senha; backend valida e troca.
// 400 quando o token é inválido/expirado — o componente trata.
export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: async (input: {
      token: string;
      new_password: string;
    }): Promise<PasswordResponse> => {
      const { data } = await api.post<PasswordResponse>(
        "/auth/password/reset/confirm/",
        input,
      );
      return data;
    },
  });
}

// `useRequestOwnPasswordChange` — POST /auth/password/change/.
// Protegido (JWT). Sem corpo — usa o email do usuário autenticado.
// Mesmo fluxo de token single-use; só elimina o "digite seu username".
export function useRequestOwnPasswordChange() {
  return useMutation({
    mutationFn: async (): Promise<PasswordResponse> => {
      const { data } = await api.post<PasswordResponse>(
        "/auth/password/change/",
        {},
      );
      return data;
    },
  });
}
