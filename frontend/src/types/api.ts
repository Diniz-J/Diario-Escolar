// Tipos que casam com os serializers do backend.

export interface Escola {
  id: number;
  nome: string;
  cnpj: string | null;
  ativa: boolean;
  criado_em: string;
  atualizado_em: string;
}

export interface Disciplina {
  id: number;
  escola: number;
  nome: string;
  ativa: boolean;
  criado_em: string;
  atualizado_em: string;
}

export type DisciplinaInput = Omit<
  Disciplina,
  "id" | "criado_em" | "atualizado_em"
>;

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

// Status calculado no backend (serializer) — read-only no frontend.
export type EntregaStatus =
  | "pendente"
  | "atrasada"
  | "entregue_no_prazo"
  | "entregue_com_atraso";

export interface Tarefa {
  id: number;
  escola: number;
  turma: number;
  disciplina: number;
  professor: number | null;
  titulo: string;
  descricao: string;
  data_lancamento: string;
  prazo: string | null;
  vale_nota: boolean;
  nota_maxima: string | null; // DecimalField → string
  peso: string;
  criado_em: string;
  atualizado_em: string;
}

export type TarefaInput = Omit<
  Tarefa,
  "id" | "criado_em" | "atualizado_em"
>;

export interface EntregaTarefa {
  id: number;
  tarefa: number;
  aluno: number;
  entregue: boolean;
  data_entrega: string | null;
  nota: string | null;
  observacao: string;
  status: EntregaStatus;
  criado_em: string;
  atualizado_em: string;
}

// Boletim do aluno — agregação calculada pelo backend (sem persistência).
// Decimal serializado como string.
export interface BoletimFrequencia {
  total: number;
  presentes: number;
  ausentes: number;
  justificados: number;
  retardatarios: number;
  presencas_efetivas: number;
  percentual_presenca: string;
}

export interface BoletimOcorrencias {
  total: number;
  abertas: number;
  em_andamento: number;
  resolvidas: number;
  arquivadas: number;
}

export interface BoletimTarefaItem {
  tarefa_id: number;
  titulo: string;
  nota: string;
  nota_maxima: string | null;
  peso: string;
  data_lancamento: string;
}

export interface BoletimDisciplina {
  disciplina: { id: number; nome: string };
  tarefas: BoletimTarefaItem[];
  media_ponderada: string;
}

export interface Boletim {
  aluno: {
    id: number;
    nome_completo: string;
    matricula: string;
    ativo: boolean;
  };
  turma: { id: number | null; nome: string | null };
  periodo: { data_inicio: string | null; data_fim: string | null };
  frequencia: BoletimFrequencia;
  notas_por_disciplina: BoletimDisciplina[];
  ocorrencias: BoletimOcorrencias;
}
