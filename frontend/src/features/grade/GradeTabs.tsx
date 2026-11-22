import { NavLink } from "react-router-dom";

// A grade tem duas telas (a semana da turma e o catálogo de horários) e um
// item só na sidebar — mesmo arranjo do financeiro: o catálogo de tempos é
// cadastro que se faz uma vez por ano e não disputa espaço com a tela de
// uso corrente.
const TABS = [
  { to: "/grade", label: "Grade da turma" },
  { to: "/grade/tempos", label: "Tempos de aula" },
];

export function GradeTabs() {
  return (
    <nav className="flex gap-1 border-b border-border">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          // `end` no índice: sem isso "/grade" acenderia junto em
          // "/grade/tempos".
          end={tab.to === "/grade"}
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
