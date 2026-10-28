import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Usuario, UsuarioInput } from "@/types/api";

import { isAxiosError } from "axios";

// Hooks de Usuario. Nasceram só com o `create`, pra criação de Professor
// (cria-se o Usuario primeiro, depois o Professor que aponta pra ele); a
// `UsuariosPage` acrescentou a listagem e a (des)ativação.
//
// A lista não pagina de propósito. O `UsuarioViewSet` é escopado pela
// escola do autor, e uma escola tem dezenas de contas, não milhares —
// paginar custaria o filtro e a busca irem pro servidor sem nada em
// troca. Se um dia uma rede grande entrar, o lugar de mudar é aqui mais
// o `?page` do backend, que já existe.

const USUARIOS_KEY = ["usuarios"] as const;

export function useUsuarios() {
  return useQuery({
    queryKey: USUARIOS_KEY,
    queryFn: async (): Promise<Usuario[]> => {
      const { data } = await api.get<Usuario[] | { results: Usuario[] }>(
        "/usuarios/",
      );
      return Array.isArray(data) ? data : data.results;
    },
  });
}

// (Des)ativa a conta. É um PATCH de `is_active` como qualquer outro, mas
// ganha hook próprio porque o backend recusa desativar a própria conta
// (400) e a mensagem dele é o que explica o porquê — jogar isso num
// "erro ao salvar" genérico esconderia a única informação útil.
export function useAtivacaoUsuario() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ativo,
    }: {
      id: number;
      ativo: boolean;
    }): Promise<Usuario> => {
      const { data } = await api.patch<Usuario>(`/usuarios/${id}/`, {
        is_active: ativo,
      });
      return data;
    },
    onSuccess: (_data, { ativo }) => {
      queryClient.invalidateQueries({ queryKey: USUARIOS_KEY });
      toast.success(ativo ? "Usuário reativado." : "Usuário desativado.");
    },
    onError: (err) => {
      toast.error(mensagemDeErro(err, "Não foi possível alterar o acesso."));
    },
  });
}

// O texto do DRF é a UI aqui, como nos dialogs do financeiro: é ele que
// diz "Você não pode desativar a sua própria conta" ou "Apenas um
// administrador pode alterar este campo", e nenhuma frase genérica
// substitui isso.
export function mensagemDeErro(err: unknown, fallback: string): string {
    if (!isAxiosError(err)) return fallback;
    const data = err.response?.data;
    if (typeof data?.detail === "string") return data.detail;
    if (data && typeof data === "object") {
      for (const valor of Object.values(data)) {
        if (typeof valor === "string") return valor;
        if (Array.isArray(valor) && typeof valor[0] === "string") {
          return valor[0];
        }
      }
    }
    return fallback;
}

export function useCreateUsuario() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: UsuarioInput): Promise<Usuario> => {
      const { data } = await api.post<Usuario>("/usuarios/", input);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USUARIOS_KEY });
    },
  });
}

export function useUpdateUsuario() {
  const queryClient = useQueryClient();
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USUARIOS_KEY });
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
