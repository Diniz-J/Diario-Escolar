import { AuthProvider } from "@/features/auth/AuthContext";
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
    </AuthProvider>
  );
}
