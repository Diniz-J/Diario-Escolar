import { useAuth } from "./useAuth";

// Centraliza as regras de permissão de UI por perfil. O backend é a
// fonte de verdade real (cada ViewSet tem suas permissions); aqui só
// alinhamos a UI pra evitar mostrar botões que vão falhar com 403.
//
// Decisão de design (espelhada em apps/common/permissions.py):
// - `secretaria` opera como `diretor` (faz cadastros, gerencia usuários).
// - `inspetor` opera como `professor` (lança ocorrência e chamada).
// A distinção entre eles é só rótulo de UX (sidebar/Dashboard mostram
// "Secretaria"/"Inspetor" via PERFIL_LABEL). Quando crescer pra rede
// grande e fizer sentido separar, refina as listas abaixo.

const PERFIS_NIVEL_DIRETOR = ["admin", "diretor", "secretaria"] as const;

export function usePermissoes() {
  const { user } = useAuth();
  const perfil = user?.perfil;

  const podeModificarCadastros =
    perfil != null &&
    (PERFIS_NIVEL_DIRETOR as readonly string[]).includes(perfil);

  return {
    podeModificarCadastros,
  };
}
