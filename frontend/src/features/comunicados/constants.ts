import type {
  ComunicadoDestinatarioStatus,
  ComunicadoDestino,
  ComunicadoStatus,
} from "@/types/api";

export const STATUS_OPTIONS: { value: ComunicadoStatus; label: string }[] = [
  { value: "rascunho", label: "Rascunho" },
  { value: "enviando", label: "Enviando" },
  { value: "enviado", label: "Enviado" },
  { value: "falhou", label: "Falhou" },
];

export const STATUS_LABEL = Object.fromEntries(
  STATUS_OPTIONS.map((s) => [s.value, s.label]),
) as Record<ComunicadoStatus, string>;

// Prioridade de listagem: rascunho primeiro (é o que pede ação do
// diretor), falha logo depois (pede atenção), enviado por último.
export const STATUS_ORDEM: Record<ComunicadoStatus, number> = {
  rascunho: 0,
  falhou: 1,
  enviando: 2,
  enviado: 3,
};

// Badges na paleta da marca (DESIGN.md §6.1).
// - rascunho → muted neutro (ainda não saiu, sem urgência visual)
// - enviando → mostarda pastel (em curso)
// - enviado  → olive pastel (positivo, alinhado à primária)
// - falhou   → terracota + destructive (chama atenção)
export const STATUS_BADGE: Record<ComunicadoStatus, string> = {
  rascunho: "text-muted-foreground bg-muted",
  enviando: "bg-[#FCE7BC] text-[#854D0E]",
  enviado: "text-olive bg-olive/10",
  falhou: "text-destructive bg-destructive/15",
};

export const DESTINO_OPTIONS: {
  value: ComunicadoDestino;
  label: string;
}[] = [
  { value: "escola", label: "Toda a escola" },
  { value: "turmas", label: "Turmas selecionadas" },
];

export const DEST_STATUS_LABEL: Record<
  ComunicadoDestinatarioStatus,
  string
> = {
  pendente: "Pendente",
  enviando: "Não confirmado",
  enviado: "Enviado",
  falhou: "Falhou",
  sem_email: "Sem email",
};

// `pendente` usa o mesmo tratamento de "em curso" do comunicado; linhas
// que ficam pendentes depois do disparo indicam envio interrompido.
export const DEST_STATUS_BADGE: Record<
  ComunicadoDestinatarioStatus,
  string
> = {
  pendente: "bg-[#FCE7BC] text-[#854D0E]",
  // Indeterminado: nem sucesso nem falha — mostarda, igual ao "em curso".
  enviando: "bg-[#FCE7BC] text-[#854D0E]",
  enviado: "text-olive bg-olive/10",
  falhou: "text-destructive bg-destructive/15",
  sem_email: "text-muted-foreground bg-muted",
};
