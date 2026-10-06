// Tipos do portal, espelhando `apps/portal/serializers.py`.
//
// Separados de `types/api.ts` (do staff) porque o contrato é outro: o
// serializer do portal escolhe os campos a dedo, sem autoria de
// comunicado, sem id interno de professor e sem nada agregado da turma.
// Reaproveitar o tipo do staff daria autocomplete pra campo que a API do
// portal não manda.

export interface PortalFilho {
  id: number;
  nome_completo: string;
  matricula: string;
  turma: string | null;
  ano_letivo: number | null;
  ativo: boolean;
}

export interface PortalPeriodo {
  id: number;
  nome: string;
  ano_letivo: number;
  data_inicio: string;
  data_fim: string;
}

export interface PortalOcorrencia {
  id: number;
  data_ocorrencia: string;
  descricao: string;
  status: string;
  status_display: string;
  professor: string | null;
}

export interface PortalMaterial {
  id: number;
  titulo: string;
  descricao: string;
  link: string;
  disciplina: string;
  professor: string | null;
  publicado_em: string;
}

export interface PortalComunicado {
  id: number;
  titulo: string;
  mensagem: string;
  enviado_em: string | null;
  // Quais filhos DESTE responsável o comunicado alcançou.
  alunos: { id: number; nome_completo: string }[];
}

export interface Paginado<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
