import { useAuth } from "./useAuth";

// Centraliza as regras de permissão de UI por perfil. O backend é a
// fonte de verdade real (cada ViewSet tem suas permissions); aqui só
// alinhamos a UI pra evitar mostrar botões que vão falhar com 403.
//
// Decisão de design (espelhada em apps/common/permissions.py):
// - `secretaria` e `coordenador` operam como `diretor` (fazem cadastros,
//   gerenciam usuários).
// - `inspetor` opera como `professor` (lança ocorrência e chamada).
// A distinção entre eles é só rótulo de UX (sidebar/Dashboard mostram
// "Secretaria"/"Coordenador"/"Inspetor" via PERFIL_LABEL). Quando crescer
// pra rede grande e fizer sentido separar, refina as listas abaixo.

const PERFIS_NIVEL_DIRETOR = [
  "admin",
  "diretor",
  "secretaria",
  "coordenador",
] as const;

export function usePermissoes() {
  const { user } = useAuth();
  const perfil = user?.perfil;

  const podeModificarCadastros =
    perfil != null &&
    (PERFIS_NIVEL_DIRETOR as readonly string[]).includes(perfil);

  // Import em massa é admin-only no backend (ver ImportExportViewSetMixin
  // com `WRITE_PERMISSION`). Diretor pode exportar mas não importar
  // — esconder o item da sidebar pra perfis não-admin evita 403 visível.
  const podeImportar = perfil === "admin";

  // Admin global = perfil `admin`. **Estritamente** este perfil, não
  // qualquer usuário sem `escola_id`. Decisão crítica de produto:
  // nenhum outro perfil pode ver UI que dependa de escolher escola
  // (ex.: select de Escola nos forms). Se algum dia surgir um usuário
  // não-admin com `escola_id=null` por bug, ele NÃO deve ver essa UI.
  const ehAdminGlobal = perfil === "admin";

  return {
    podeModificarCadastros,
    podeImportar,
    ehAdminGlobal,
  };
}
