import { useAuth } from "./useAuth";

// Centraliza as regras de permissão de UI por perfil. O backend é a
// fonte de verdade real (cada ViewSet tem suas permissions); aqui só
// alinhamos a UI pra evitar mostrar botões que vão falhar com 403.
//
// Hoje só temos a regra "pode mexer em cadastros de domínio" (Alunos,
// Turmas, Disciplinas, Professores, Lecionamentos) — restrita a admin
// e diretor. Quando novos casos aparecerem (ex.: secretaria/inspetor
// poder X), adicione propriedades novas a esse hook em vez de espalhar
// `user?.perfil === "..."` pelas pages.
export function usePermissoes() {
  const { user } = useAuth();
  const perfil = user?.perfil;

  const podeModificarCadastros = perfil === "admin" || perfil === "diretor";

  return {
    podeModificarCadastros,
  };
}
