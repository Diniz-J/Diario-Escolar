import type { Perfil } from "@/features/auth/types";

export const PERFIL_LABEL: Record<string, string> = {
  admin: "Administrador",
  diretor: "Diretor",
  professor: "Professor",
  secretaria: "Secretaria",
  coordenador: "Coordenador",
  inspetor: "Inspetor",
};

// Badge de perfil no molde de ocorrência (DESIGN.md §6.1.1), não nos
// pastels de presença: perfil é estado de documento. Nível-direção em
// olive, docente em muted neutro, admin em destructive — não por ser
// erro, mas por ser a única conta que alcança as outras escolas, e a
// tela tem que fazer isso saltar.
export const PERFIL_BADGE: Record<string, string> = {
  admin: "bg-destructive/15 text-destructive",
  diretor: "bg-olive/10 text-olive",
  secretaria: "bg-olive/10 text-olive",
  coordenador: "bg-olive/10 text-olive",
  professor: "bg-muted text-muted-foreground",
  inspetor: "bg-muted text-muted-foreground",
};

const PERFIS_BASE: { value: Perfil; label: string }[] = [
  { value: "diretor", label: "Diretor" },
  { value: "secretaria", label: "Secretaria" },
  { value: "coordenador", label: "Coordenador" },
  { value: "professor", label: "Professor" },
  { value: "inspetor", label: "Inspetor" },
];

/**
 * Perfis que o select oferece.
 *
 * `admin` só pra admin global: o backend recusa com 400 quem tenta criar
 * ou promover a ele (`_validar_perfil_alvo`), e oferecer opção que só
 * devolve erro é pior que não oferecer.
 *
 * Mora aqui, e não dentro do dialog, pelo mesmo motivo de
 * `podeEmitirCobranca` em `financeiro/constants.ts`: é a regra que
 * espelha uma invariante do backend, e regra enterrada em JSX não se
 * testa direto — o Radix só renderiza as opções com o select aberto, e
 * abrir select em jsdom é frágil.
 */
export function opcoesDePerfil(
  ehAdminGlobal: boolean,
): { value: Perfil; label: string }[] {
  if (!ehAdminGlobal) return PERFIS_BASE;
  return [...PERFIS_BASE, { value: "admin" as Perfil, label: "Administrador" }];
}
