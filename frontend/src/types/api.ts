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

export interface Professor {
  id: number;
  escola: number;
  usuario: number;
  nome_completo: string;
  disciplinas: number[];
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
}

export type OcorrenciaStatus =
  | "aberta"
  | "em_andamento"
  | "resolvida"
  | "arquivada";

export interface Ocorrencia {
  id: number;
  escola: number;
  turma: number;
  aluno: number;
  professor: number | null;
  descricao: string;
  data_ocorrencia: string;
  status: OcorrenciaStatus;
  status_display: string;
  criado_em: string;
  atualizado_em: string;
}

export type OcorrenciaInput = Omit<
  Ocorrencia,
  "id" | "status_display" | "criado_em" | "atualizado_em"
>;

// P=Presente, A=Ausente, J=Justificado, R=Retardatário
export type PresencaStatus = "P" | "A" | "J" | "R";

export interface RegistroPresenca {
  id: number;
  escola: number;
  turma: number;
  data: string;
  professor: number | null;
  observacao: string;
  criado_em: string;
  atualizado_em: string;
}

export type RegistroPresencaInput = Omit<
  RegistroPresenca,
  "id" | "criado_em" | "atualizado_em"
>;

export interface ItemPresenca {
  id: number;
  registro: number;
  aluno: number;
  status: PresencaStatus;
  status_display: string;
  observacao: string;
  criado_em: string;
  atualizado_em: string;
}
