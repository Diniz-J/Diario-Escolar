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

// Badges por status na paleta da marca (DESIGN.md §6.1).
// - aberta       → terracota clarinho + texto destructive (chama atenção)
// - em_andamento → mostarda pastel (em curso, sem urgência)
// - resolvida    → olive pastel (positivo, alinhado à primária)
// - arquivada    → muted neutro (fundo de histórico)
export const STATUS_BADGE: Record<OcorrenciaStatus, string> = {
  aberta:
    "text-destructive bg-destructive/15",
  em_andamento:
    "bg-[#FCE7BC] text-[#854D0E]",
  resolvida:
    "text-olive bg-olive/10",
  arquivada:
    "text-muted-foreground bg-muted",
};
