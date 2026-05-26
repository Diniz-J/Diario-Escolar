import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Usuario, UsuarioInput } from "@/types/api";

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
