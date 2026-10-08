import type { ResponsavelSituacao } from "@/types/api";

export const SITUACAO_OPTIONS: {
  value: ResponsavelSituacao;
  label: string;
}[] = [
  { value: "sem_convite", label: "Sem convite" },
  { value: "convidado", label: "Convite enviado" },
  { value: "convite_expirado", label: "Convite expirado" },
  { value: "ativo", label: "Acesso ativo" },
  { value: "inativo", label: "Inativo" },
];

// Badges na paleta da marca (DESIGN.md), pela lógica de "o que pede ação":
// - sem_convite       → mostarda: é o que a secretaria tem pra fazer
// - convite_expirado  → terracota: pedia ação e passou do prazo
// - convidado         → petrol pastel: em curso, nada a fazer
// - ativo             → olive: positivo, resolvido
// - inativo           → muted: fora de operação
export const SITUACAO_BADGE: Record<ResponsavelSituacao, string> = {
  sem_convite: "bg-[#FCE7BC] text-[#854D0E]",
  convite_expirado: "text-destructive bg-destructive/15",
  convidado: "bg-[#DCE7EA] text-[#2F5D68]",
  ativo: "text-olive bg-olive/10",
  inativo: "text-muted-foreground bg-muted",
};

// Situações em que o botão Convidar faz sentido. O backend recusa as
// outras (400), então mostrar o botão seria prometer o que não acontece.
export const PODE_CONVIDAR: ResponsavelSituacao[] = [
  "sem_convite",
  "convidado",
  "convite_expirado",
];
