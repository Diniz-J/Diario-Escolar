import type { EntregaStatus } from "@/types/api";

// Labels e cores por status — fonte única para badges na UI.
export const STATUS_LABEL: Record<EntregaStatus, string> = {
  pendente: "Pendente",
  atrasada: "Atrasada",
  entregue_no_prazo: "Entregue",
  entregue_com_atraso: "Entregue com atraso",
};

export const STATUS_BADGE: Record<EntregaStatus, string> = {
  pendente:
    "text-amber-700 bg-amber-50 dark:bg-amber-950 dark:text-amber-300",
  atrasada:
    "text-red-700 bg-red-50 dark:bg-red-950 dark:text-red-300",
  entregue_no_prazo:
    "text-green-700 bg-green-50 dark:bg-green-950 dark:text-green-300",
  entregue_com_atraso:
    "text-blue-700 bg-blue-50 dark:bg-blue-950 dark:text-blue-300",
};

// Ordem de prioridade na listagem (atrasadas / pendentes em cima).
export const STATUS_ORDEM: Record<EntregaStatus, number> = {
  atrasada: 0,
  pendente: 1,
  entregue_com_atraso: 2,
  entregue_no_prazo: 3,
};
