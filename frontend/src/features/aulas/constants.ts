import type { RegistroAulaStatus } from "@/types/api";

// Rótulos de dia da semana alinhados com `date.weekday()` do backend
// (0=segunda ... 6=domingo).
export const DIAS_SEMANA_LABEL = [
  "Segunda",
  "Terça",
  "Quarta",
  "Quinta",
  "Sexta",
  "Sábado",
  "Domingo",
] as const;

export const DIAS_SEMANA_CURTO = [
  "Seg",
  "Ter",
  "Qua",
  "Qui",
  "Sex",
  "Sáb",
  "Dom",
] as const;

type StatusSlot = RegistroAulaStatus | "vazio";

// Estilo dos badges de status na paleta da marca (sem cores genéricas do
// Tailwind), no mesmo espírito dos badges de ocorrência (constants.ts).
// `mostarda` não é utility do tema — usa-se o mesmo hex pastel do badge
// "em andamento" das ocorrências.
export const STATUS_AULA: Record<
  StatusSlot,
  { label: string; classe: string }
> = {
  vazio: {
    label: "A preencher",
    classe: "text-muted-foreground bg-muted",
  },
  rascunho: {
    label: "Rascunho",
    classe: "bg-[#FCE7BC] text-[#854D0E]",
  },
  lancado: {
    label: "Lançado",
    classe: "text-ferrugem bg-ferrugem/10",
  },
  conferido: {
    label: "Conferido",
    classe: "text-olive bg-olive/10",
  },
};
