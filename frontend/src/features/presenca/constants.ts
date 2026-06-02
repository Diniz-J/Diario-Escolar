import type { PresencaStatus } from "@/types/api";

// Ordem dos botões na chamada — ciclo lógico do mais comum (Presente)
// pro mais excepcional (Retardatário).
//
// Paleta dos status alinhada com a identidade Diário Diniz: tons
// pastel terrosos em vez do green/red/amber/blue genérico do Tailwind
// (que ficava berrante no fundo linho). Cada status mantém significado
// visual claro:
//   P (Presente)     → olive claro    — "tudo ok, está aqui"
//   A (Ausente)      → terracota      — "atenção, faltou"
//   J (Justificado)  → mostarda       — "ausente com razão"
//   R (Retardatário) → petrol pastel  — "chegou atrasado"
//
// As cores são valores arbitrários Tailwind (em vez de tokens) pra ficar
// explícito o caso específico — esta paleta é deliberadamente diferente
// dos badges de ocorrência (que cobrem outro conjunto de status).
export const STATUS_PRESENCA: {
  value: PresencaStatus;
  label: string;
  full: string;
  className: string;
}[] = [
  {
    value: "P",
    label: "P",
    full: "Presente",
    className:
      "bg-[#CFD4B8] text-[#3A4524] hover:bg-[#BFC6A6]",
  },
  {
    value: "A",
    label: "A",
    full: "Ausente",
    className:
      "bg-[#EFD2C8] text-[#7C2D1A] hover:bg-[#E5BFB1]",
  },
  {
    value: "J",
    label: "J",
    full: "Justificado",
    className:
      "bg-[#F8DBAE] text-[#854D0E] hover:bg-[#F2CB8E]",
  },
  {
    value: "R",
    label: "R",
    full: "Retardatário",
    className:
      "bg-[#BCCDCB] text-[#1F3A37] hover:bg-[#A8BEBB]",
  },
];

export const STATUS_FULL: Record<PresencaStatus, string> = Object.fromEntries(
  STATUS_PRESENCA.map((s) => [s.value, s.full]),
) as Record<PresencaStatus, string>;
