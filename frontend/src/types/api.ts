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
  // Toggle comercial: marca escolas que contrataram o pacote de
  // import/export em massa. Sem isso, o backend devolve 403 pras 3
  // actions (import/export/template). Operação é exclusiva do admin
  // global — esse field só é editável via /admin/ do Django.
  importacao_em_lote_habilitada: boolean;
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

// Estado computado server-side. Hoje sempre "vazio" (nenhuma Avaliacao
// existe ainda — frente em construção). Nos próximos PRs vai virar
// "em_uso" quando houver avaliações apontando pro período, e "fechado"
// quando a média final for lançada.
export type PeriodoEstado = "vazio" | "em_uso" | "fechado";

export interface PeriodoAvaliativo {
  id: number;
  escola: number;
  nome: string;
  ordem: number;
  ano_letivo: number;
  // ISO "YYYY-MM-DD".
  data_inicio: string;
  data_fim: string;
  ativo: boolean;
  estado: PeriodoEstado;
  criado_em: string;
  atualizado_em: string;
}

// `escola` opcional pelo mesmo motivo de Disciplina (AutoEscopoEscolaMixin
// auto-preenche). `ativo` opcional — default true no model.
export type PeriodoAvaliativoInput = Omit<
  PeriodoAvaliativo,
  "id" | "escola" | "ativo" | "estado" | "criado_em" | "atualizado_em"
> & { escola?: number; ativo?: boolean };

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
  // Dias da semana com aula (0=segunda ... 6=domingo); base da agenda do diário.
  dias_semana: number[];
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

// Diário de aula (app `aulas`).
export type RegistroAulaStatus = "rascunho" | "lancado" | "conferido";

export interface RegistroAula {
  id: number;
  escola: number;
  turma: number;
  disciplina: number;
  professor: number;
  data: string;
  conteudo: string;
  status: RegistroAulaStatus;
  status_display: string;
  conferido_por: number | null;
  conferido_por_nome: string | null;
  conferido_em: string | null;
  criado_em: string;
  atualizado_em: string;
}

// `escola` opcional — backend auto-preenche (`AutoEscopoEscolaMixin`).
// `status` aceita só rascunho/lancado no payload; conferido é via action.
export type RegistroAulaInput = {
  escola?: number;
  turma: number;
  disciplina: number;
  professor: number;
  data: string;
  conteudo: string;
  status: Exclude<RegistroAulaStatus, "conferido">;
};

// Slot projetado pela action `agenda` (não é linha no banco).
export interface AgendaSlot {
  data: string;
  dia_semana: number;
  status: RegistroAulaStatus | "vazio";
  registro_id: number | null;
  futuro: boolean;
}

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

// ====================================================================
// Avaliacao + NotaAvaliacao
// (substituiu Tarefa/EntregaTarefa no PR #72; cleanup final no PR #77)
// ====================================================================

export type AvaliacaoTipo =
  | "prova"
  | "trabalho"
  | "atividade"
  | "participacao";

export interface Avaliacao {
  id: number;
  escola: number;
  turma: number;
  turma_nome: string;
  disciplina: number;
  disciplina_nome: string;
  professor: number | null;
  periodo: number | null;
  periodo_nome: string | null;
  titulo: string;
  descricao: string;
  tipo: AvaliacaoTipo;
  tipo_display: string;
  data: string; // ISO YYYY-MM-DD
  nota_maxima: string; // DecimalField → string
  peso: string;
  ativo: boolean;
  total_alunos: number;
  notas_lancadas: number;
  criado_em: string;
  atualizado_em: string;
}

// `escola` opcional pelo mesmo motivo dos outros. `periodo` é read-only
// (server aloca pela data). `ativo` opcional (default true).
export type AvaliacaoInput = Omit<
  Avaliacao,
  | "id"
  | "escola"
  | "turma_nome"
  | "disciplina_nome"
  | "periodo"
  | "periodo_nome"
  | "tipo_display"
  | "ativo"
  | "total_alunos"
  | "notas_lancadas"
  | "criado_em"
  | "atualizado_em"
> & { escola?: number; ativo?: boolean };

export interface NotaAvaliacaoUltimaEdicao {
  por: string | null;
  em: string | null; // ISO
}

export interface NotaAvaliacao {
  id: number;
  avaliacao: number;
  aluno: number;
  aluno_nome: string;
  aluno_matricula: string;
  nota: string | null; // null = ainda não lançada
  observacao: string;
  ultima_edicao: NotaAvaliacaoUltimaEdicao | null;
  criado_em: string;
  atualizado_em: string;
}

export interface LancarNotaItem {
  aluno_id: number;
  nota: string | null;
  observacao?: string;
}

export interface LancarNotasResponse {
  atualizadas: number;
  falhas: Array<{ aluno_id: number; motivo: string }>;
}

// Tipo "+"/"~"/"-" do simple_history.
export type HistoricoTipo = "+" | "~" | "-";

export interface NotaAvaliacaoHistoricoEvento {
  nota: string | null;
  observacao: string;
  por: string | null;
  em: string | null;
  tipo: HistoricoTipo;
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

// Avaliação individual (prova/trabalho/atividade) dentro de uma
// disciplina do boletim. Substituiu `BoletimTarefaItem` no refator
// da frente de avaliação.
export interface BoletimAvaliacaoItem {
  avaliacao_id: number;
  titulo: string;
  tipo: AvaliacaoTipo;
  tipo_display: string;
  data: string;
  nota_maxima: string;
  peso: string;
  nota_obtida: string;
  periodo_nome: string | null;
}

// Média final por período (digitada pelo professor) dentro de uma
// disciplina. `observacao` não vem aqui — é nota interna, fora do
// boletim do responsável.
export interface BoletimNotaFinalPeriodo {
  periodo_id: number;
  periodo_nome: string;
  nota_final: string;
}

export interface BoletimDisciplina {
  disciplina: { id: number; nome: string };
  avaliacoes: BoletimAvaliacaoItem[];
  notas_finais_por_periodo: BoletimNotaFinalPeriodo[];
}

export interface Boletim {
  aluno: {
    id: number;
    nome_completo: string;
    matricula: string;
    ativo: boolean;
  };
  turma: { id: number | null; nome: string | null; ano_letivo: number | null };
  escola: { id: number | null; nome: string | null };
  periodo: {
    data_inicio: string | null;
    data_fim: string | null;
    id: number | null;
    nome: string | null;
    ano_letivo: number | null;
  };
  frequencia: BoletimFrequencia;
  notas_por_disciplina: BoletimDisciplina[];
  ocorrencias: BoletimOcorrencias;
}

// ====================================================================
// NotaPeriodo — media final por aluno × disciplina × periodo
// ====================================================================

export interface NotaPeriodo {
  id: number;
  escola: number;
  aluno: number;
  aluno_nome: string;
  aluno_matricula: string;
  disciplina: number;
  disciplina_nome: string;
  periodo: number;
  periodo_nome: string;
  nota_final: string | null; // null = ainda nao lancada
  observacao: string;
  ultima_edicao: NotaAvaliacaoUltimaEdicao | null;
  criado_em: string;
  atualizado_em: string;
}

export interface LancarNotaFinalItem {
  aluno_id: number;
  nota_final: string | null;
  observacao?: string;
}

export interface LancarNotasFinaisResponse {
  atualizadas: number;
  falhas: Array<{ aluno_id: number; motivo: string }>;
}

export interface NotaPeriodoHistoricoEvento {
  nota_final: string | null;
  observacao: string;
  por: string | null;
  em: string | null;
  tipo: HistoricoTipo;
}
