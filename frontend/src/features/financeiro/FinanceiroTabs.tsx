import { NavLink } from "react-router-dom";

// O financeiro tem duas telas (faturas e planos) e um item só na sidebar.
// Estas abas são a navegação entre elas — a sidebar já tem 12 itens mais
// dois condicionais, e plano de cobrança é cadastro raro: não merece
// disputar espaço com a tela de uso diário.
const TABS = [
  { to: "/financeiro", label: "Faturas" },
  { to: "/financeiro/planos", label: "Planos de cobrança" },
];

export function FinanceiroTabs() {
  return (
    <nav className="flex gap-1 border-b border-border">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          // `end` no índice: sem isso "/financeiro" ficaria ativo também
          // em "/financeiro/planos", e as duas abas acenderiam juntas.
          end={tab.to === "/financeiro"}
          className={({ isActive }) =>
            [
              "px-3 py-2 text-[11px] uppercase tracking-[0.18em] transition",
              isActive
                ? "text-tinta border-b-2 border-ferrugem"
                : "text-sepia hover:text-tinta border-b-2 border-transparent",
            ].join(" ")
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
