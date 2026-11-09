import { AuthProvider } from "@/features/auth/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import { AppRoutes } from "@/routes";

/**
 * Árvore da área administrativa.
 *
 * Extraída do `App.tsx` pra virar um chunk separado do portal do
 * responsável (ver `PORTAL.md`, seção 4.5): o pai não baixa a UI de
 * gestão, e o funcionário não baixa a do portal.
 */
export default function StaffApp() {
  return (
    <AuthProvider>
      <AppRoutes />
      {/* Mora aqui, e não no `App.tsx`, porque só o staff dispara toast:
          os 117 `toast.success` e `toast.error` do projeto estão todos
          nos `hooks.ts` das features da área administrativa, e nada na
          árvore do portal importa `sonner`. Montado na raiz comum, ele
          levava o sonner pro chunk `index` que o responsável também
          baixa: 10,1 kB gzip de máquina de toast pra um portal que não
          tem nenhum. `bottom-right` evita que o toast sobreponha botões
          de ação no canto superior direito das páginas (ex.: Resolver e
          Arquivar em ocorrências). */}
      <Toaster richColors position="bottom-right" />
    </AuthProvider>
  );
}
