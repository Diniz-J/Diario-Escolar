// Tipos que casam com os serializers do backend.

import type { Perfil } from "@/features/auth/types";

// Envelope de paginação do DRF (apps.common.pagination.PaginacaoPadrao).
// `next` e `previous` são URLs absolutas; o frontend só precisa do `count`
// pra calcular o total de páginas e dos `results` pra renderizar.
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Usuario {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  perfil: Perfil;
  escola: number | null;
  is_active: boolean;
}

// Input pra criação de Usuario. `password` é write-only (não vem de
// volta nas respostas). `escola` é obrigatório porque o validate cruzado
// do Professor exige que o usuário pertença à mesma escola.
export type UsuarioInput = {
  username: string;
  email?: string;
  first_name: string;
  last_name: string;
  perfil: Perfil;
  escola: number;
  is_active?: boolean;
  password?: string;
};

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

// `ativa` é opcional porque o backend tem default=True no modelo e o
// form da UI deixou de expor o campo — disciplina nasce ativa.
//
// `escola` é opcional: o backend (`AutoEscopoEscolaMixin`) auto-preenche
// com a escola do usuário autenticado quando o campo é omitido. Admin
// global (sem `escola` no perfil) precisa enviar explicitamente.
export type DisciplinaInput = Omit<
  Disciplina,
  "id" | "escola" | "ativa" | "criado_em" | "atualizado_em"
> & { escola?: number; ativa?: boolean };

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

// `escola` opcional — backend auto-preenche pelo usuário autenticado
// quando ausente (`AutoEscopoEscolaMixin`).
export type TurmaInput = Omit<
  Turma,
  "id" | "escola" | "turno_display" | "criado_em" | "atualizado_em"
> & { escola?: number };

export interface Aluno {
  id: number;
  escola: number;
  matricula: string;
  nome_completo: string;
  data_nascimento: string | null;
  turma: number;
  ativo: boolean;
  nome_responsavel: string;
  email_responsavel: string;
  criado_em: string;
  atualizado_em: string;
}

// `escola` opcional — backend auto-preenche pelo usuário autenticado
// (`AutoEscopoEscolaMixin`); o form deriva da turma escolhida quando
// admin precisa especificar.
export type AlunoInput = Omit<
  Aluno,
  "id" | "escola" | "criado_em" | "atualizado_em"
> & { escola?: number };

export interface Professor {
  id: number;
  escola: number;
  usuario: number;
  nome_completo: string;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
}

// `usuario` é obrigatório pra criar (FK existente); na edição em geral
// não muda (você edita o Usuario por baixo, não a vinculação).
//
// `escola` opcional — backend auto-preenche (`AutoEscopoEscolaMixin`).
export type ProfessorInput = {
  escola?: number;
  usuario: number;
  ativo?: boolean;
};

// Lecionamento liga professor × turma × disciplina. `ano_letivo` vem
// derivado da turma (read-only no serializer).
export interface Lecionamento {
  id: number;
  escola: number;
  professor: number;
  turma: number;
  disciplina: number;
  ano_letivo: number;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
}

// `escola` opcional — backend auto-preenche (`AutoEscopoEscolaMixin`).
export type LecionamentoInput = {
  escola?: number;
  professor: number;
  turma: number;
  disciplina: number;
  ativo?: boolean;
};

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

// `escola` opcional — backend auto-preenche (`AutoEscopoEscolaMixin`).
export type OcorrenciaInput = Omit<
  Ocorrencia,
  "id" | "escola" | "status_display" | "criado_em" | "atualizado_em"
> & { escola?: number };

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

// `escola` opcional — backend auto-preenche (`AutoEscopoEscolaMixin`).
export type RegistroPresencaInput = Omit<
  RegistroPresenca,
  "id" | "escola" | "criado_em" | "atualizado_em"
> & { escola?: number };

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

// `escola` opcional — backend auto-preenche (`AutoEscopoEscolaMixin`).
export type TarefaInput = Omit<
  Tarefa,
  "id" | "escola" | "criado_em" | "atualizado_em"
> & { escola?: number };

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

// Plano de ensino anual — documento programático por turma+disciplina+ano.
// Todos os campos textuais começam vazios; preenchimento é livre.
export interface PlanoEnsino {
  id: number;
  escola: number;
  turma: number;
  disciplina: number;
  professor: number | null;
  ano_letivo: number;
  ementa: string;
  conteudo_programatico: string;
  objetivos_gerais: string;
  objetivos_especificos: string;
  habilidades_bncc: string;
  carga_horaria: number | null;
  metodologia: string;
  recursos: string;
  avaliacao: string;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
}

// `escola` opcional — backend auto-preenche (`AutoEscopoEscolaMixin`).
export type PlanoEnsinoInput = Omit<
  PlanoEnsino,
  "id" | "escola" | "criado_em" | "atualizado_em"
> & { escola?: number };

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
