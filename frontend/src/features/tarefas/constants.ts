import type { EntregaStatus } from "@/types/api";

// Labels e cores por status — fonte única para badges na UI.
export const STATUS_LABEL: Record<EntregaStatus, string> = {
  pendente: "Pendente",
  atrasada: "Atrasada",
  entregue_no_prazo: "Entregue",
  entregue_com_atraso: "Entregue com atraso",
};

// Badges por status na paleta da marca (DESIGN.md §6.1).
// - pendente            → mostarda pastel (aguardando ação)
// - atrasada            → terracota + texto destructive (urgência)
// - entregue_no_prazo   → olive pastel (positivo, alinhado à primária)
// - entregue_com_atraso → petrol pastel (entregue, mas com ressalva)
export const STATUS_BADGE: Record<EntregaStatus, string> = {
  pendente:
    "bg-[#FCE7BC] text-[#854D0E]",
  atrasada:
    "text-destructive bg-destructive/15",
  entregue_no_prazo:
    "text-olive bg-olive/10",
  entregue_com_atraso:
    "bg-[#C4D4D2] text-[#1F3A37]",
};

// Ordem de prioridade na listagem (atrasadas / pendentes em cima).
export const STATUS_ORDEM: Record<EntregaStatus, number> = {
  atrasada: 0,
  pendente: 1,
  entregue_com_atraso: 2,
  entregue_no_prazo: 3,
};
