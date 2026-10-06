import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Usuario, UsuarioInput } from "@/types/api";

import { isAxiosError } from "axios";

// Hooks de Usuario. Por enquanto só o create é exposto — usado pela
// criação de Professor (cria-se o Usuario primeiro, depois o Professor
// que aponta pra ele). Quando uma tela de "Usuários" aparecer no
// roadmap, adicionar useUsuarios/useUpdateUsuario etc aqui.

export function useCreateUsuario() {
  return useMutation({
    mutationFn: async (input: UsuarioInput): Promise<Usuario> => {
      const { data } = await api.post<Usuario>("/usuarios/", input);
      return data;
    },
  });
}

export function useUpdateUsuario() {
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<UsuarioInput>;
    }): Promise<Usuario> => {
      const { data } = await api.patch<Usuario>(`/usuarios/${id}/`, patch);
      return data;
    },
  });
}

// Dispara o envio de um link de redefinição de senha pro email do usuário
// alvo. Restrito no backend a admin/diretor/secretaria/coordenador — o
// botão na UI também é gated por `podeModificarCadastros`.
export function useEnviarResetSenha() {
  return useMutation({
    mutationFn: async (
      usuarioId: number,
    ): Promise<{ detail: string; email: string }> => {
      const { data } = await api.post<{ detail: string; email: string }>(
        `/usuarios/${usuarioId}/enviar-reset-senha/`,
      );
      return data;
    },
    onSuccess: (data) => {
      toast.success(`Link de redefinição enviado para ${data.email}.`);
    },
    onError: (err) => {
      if (isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        if (err.response?.status === 422 && detail) {
          toast.error(detail);
          return;
        }
        if (err.response?.status === 403) {
          toast.error("Sem permissão pra disparar reset de senha.");
          return;
        }
      }
      toast.error("Não foi possível enviar o link de redefinição.");
    },
  });
}
