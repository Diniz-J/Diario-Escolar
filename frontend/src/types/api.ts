// Tipos que casam com os serializers do backend.

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

// Payload de criação/edição. `id`, `criado_em`, `atualizado_em` são
// devolvidos pelo backend, não enviados.
export type AlunoInput = Omit<
  Aluno,
  "id" | "criado_em" | "atualizado_em"
>;
