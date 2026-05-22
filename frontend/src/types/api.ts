// Tipos que casam com os serializers do backend.

export interface Escola {
  id: number;
  nome: string;
  cnpj: string | null;
  ativa: boolean;
  criado_em: string;
  atualizado_em: string;
}

export type Turno = "matutino" | "vespertino" | "noturno" | "integral";

export interface Turma {
  id: number;
  escola: number;
  nome: string;
  turno: Turno;
  turno_display: string;
  ano_letivo: number;
  ativa: boolean;
  criado_em: string;
  atualizado_em: string;
}

export type TurmaInput = Omit<
  Turma,
  "id" | "turno_display" | "criado_em" | "atualizado_em"
>;

export interface Aluno {
  id: number;
  escola: number;
  matricula: string;
  nome_completo: string;
  data_nascimento: string | null;
  turma: number;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
}

export type AlunoInput = Omit<
  Aluno,
  "id" | "criado_em" | "atualizado_em"
>;
