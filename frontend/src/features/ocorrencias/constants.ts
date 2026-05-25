import type { OcorrenciaStatus } from "@/types/api";

// Labels e ordem de exibição dos status — fonte única pra UI.
export const STATUS_OPTIONS: { value: OcorrenciaStatus; label: string }[] = [
  { value: "aberta", label: "Aberta" },
  { value: "em_andamento", label: "Em andamento" },
  { value: "resolvida", label: "Resolvida" },
  { value: "arquivada", label: "Arquivada" },
];

// Prioridade de listagem: as urgentes (abertas) primeiro, as fechadas
// (arquivadas) por último. Dentro do mesmo status, a ordem secundária
// é por data desc (mais recente primeiro).
export const STATUS_ORDEM: Record<OcorrenciaStatus, number> = {
  aberta: 0,
  em_andamento: 1,
  resolvida: 2,
  arquivada: 3,
};

export const STATUS_LABEL: Record<OcorrenciaStatus, string> = Object.fromEntries(
  STATUS_OPTIONS.map((s) => [s.value, s.label]),
) as Record<OcorrenciaStatus, string>;

// Cores Tailwind por status — usadas na lista. Tons sólidos pra ficar
// legível tanto em light quanto dark mode.
export const STATUS_BADGE: Record<OcorrenciaStatus, string> = {
  aberta:
    "text-amber-700 bg-amber-50 dark:bg-amber-950 dark:text-amber-300",
  em_andamento:
    "text-blue-700 bg-blue-50 dark:bg-blue-950 dark:text-blue-300",
  resolvida:
    "text-green-700 bg-green-50 dark:bg-green-950 dark:text-green-300",
  arquivada:
    "text-muted-foreground bg-muted",
};
