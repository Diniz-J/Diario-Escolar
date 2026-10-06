import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { usePortalAuth } from "@/features/portal/usePortalAuth";

// Shell do portal — mobile-first, porque o pai acessa pelo celular.
// Barra olive-dark no topo (mesma identidade da sidebar do staff, ver
// DESIGN.md) e navegação em duas entradas só: não há mais o que navegar,
// e menu grande numa tela de leitura é ruído.
const ITENS = [
  { to: "/portal", label: "Início", fim: true },
  { to: "/portal/comunicados", label: "Comunicados", fim: false },
];

export function PortalLayout() {
  const { responsavel, sair } = usePortalAuth();
  const navigate = useNavigate();

  async function handleSair() {
    await sair();
    navigate("/portal/entrar", { replace: true });
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="bg-sidebar text-sidebar-foreground">
        <div className="mx-auto max-w-3xl px-4 py-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <span className="font-heading text-[17px] tracking-tight block truncate">
              Diário Diniz
            </span>
            <span className="text-[10px] uppercase tracking-[0.18em] opacity-70 block truncate">
              {responsavel?.nome ?? "Responsável"}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleSair}
            className="text-creme hover:bg-white/10 hover:text-creme shrink-0"
          >
            Sair
          </Button>
        </div>
        <nav className="mx-auto max-w-3xl px-4 flex gap-1">
          {ITENS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.fim}
              className={({ isActive }) =>
                [
                  "px-3 py-2 text-sm border-b-2 transition",
                  isActive
                    ? "border-ferrugem text-creme"
                    : "border-transparent opacity-70 hover:opacity-100",
                ].join(" ")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6 space-y-6">
        <Outlet />
      </main>
    </div>
  );
}
