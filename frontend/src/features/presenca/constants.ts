import type { PresencaStatus } from "@/types/api";

// Ordem dos botões na chamada — ciclo lógico do mais comum (Presente)
// pro mais excepcional (Retardatário).
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
      "bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-900 dark:text-green-200 dark:hover:bg-green-800",
  },
  {
    value: "A",
    label: "A",
    full: "Ausente",
    className:
      "bg-red-100 text-red-800 hover:bg-red-200 dark:bg-red-900 dark:text-red-200 dark:hover:bg-red-800",
  },
  {
    value: "J",
    label: "J",
    full: "Justificado",
    className:
      "bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-900 dark:text-amber-200 dark:hover:bg-amber-800",
  },
  {
    value: "R",
    label: "R",
    full: "Retardatário",
    className:
      "bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:hover:bg-blue-800",
  },
];

export const STATUS_FULL: Record<PresencaStatus, string> = Object.fromEntries(
  STATUS_PRESENCA.map((s) => [s.value, s.full]),
) as Record<PresencaStatus, string>;
