import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { STATUS_BADGE } from "@/features/ocorrencias/constants";
import { useTimelineAluno } from "@/features/timeline/hooks";
import { formatarDataPura, hojeISO, isoDiasAtras } from "@/lib/datas";
import type { OcorrenciaStatus, TimelineEvento } from "@/types/api";

const EYEBROW = "text-[11px] uppercase tracking-[0.18em] text-sepia";

const MESES = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

// Janelas oferecidas na tela. "Tudo" não manda parâmetro nenhum — o
// backend devolve o histórico inteiro até o teto, e é o default porque a
// pergunta da timeline costuma ser retrospectiva ("o que já houve com
// este aluno"), não do mês corrente.
const JANELAS = [
  { id: "tudo", label: "Todo o histórico" },
  { id: "30", label: "Últimos 30 dias" },
  { id: "90", label: "Últimos 90 dias" },
] as const;

type JanelaId = (typeof JANELAS)[number]["id"];

function paramsDaJanela(janela: JanelaId) {
  if (janela === "tudo") return {};
  return { data_inicio: isoDiasAtras(Number(janela)), data_fim: hojeISO() };
}

// Cor da tira à esquerda do evento, por tipo. Ocorrência puxa ferrugem
// (a cor de atenção da marca), presença fica em sepia e cadastro em
// borda neutra — é o que separa "aconteceu com o aluno" de "mudou o
// registro dele". O status da ocorrência ganha badge próprio reusando
// `STATUS_BADGE` de ocorrências, em vez de uma segunda paleta aqui.
const TIRA_POR_TIPO: Record<TimelineEvento["tipo"], string> = {
  ocorrencia: "bg-ferrugem",
  presenca: "bg-sepia",
  cadastro: "bg-border",
};

// Eyebrow de tipo. Ocorrência fica de fora de propósito: o título do
// bloco já é "Ocorrência", e os dois juntos repetiam a palavra na mesma
// linha de leitura — lá o badge de status é que carrega a informação.
const ROTULO_POR_TIPO: Partial<Record<TimelineEvento["tipo"], string>> = {
  presenca: "Chamada",
  cadastro: "Cadastro",
};

// Agrupa por mês (YYYY-MM) preservando a ordem que o backend entrega
// (mais recente primeiro). Mesmo padrão do diário na ficha do professor.
function agruparPorMes(eventos: TimelineEvento[]) {
  const grupos: { chave: string; label: string; eventos: TimelineEvento[] }[] =
    [];
  const indice = new Map<string, number>();
  for (const evento of eventos) {
    const chave = evento.data.slice(0, 7);
    let idx = indice.get(chave);
    if (idx === undefined) {
      const [ano, mes] = chave.split("-");
      idx =
        grupos.push({
          chave,
          label: `${MESES[Number(mes) - 1]} ${ano}`,
          eventos: [],
        }) - 1;
      indice.set(chave, idx);
    }
    grupos[idx].eventos.push(evento);
  }
  return grupos;
}

function destinoDoEvento(evento: TimelineEvento): string | null {
  if (evento.referencia_id == null) return null;
  if (evento.tipo === "ocorrencia") {
    return `/ocorrencias/${evento.referencia_id}`;
  }
  if (evento.tipo === "presenca") {
    return `/presenca/${evento.referencia_id}`;
  }
  return null;
}

function EventoBloco({ evento }: { evento: TimelineEvento }) {
  const destino = destinoDoEvento(evento);
  const corpo = (
    <div className="flex gap-4">
      <div
        className={`w-[3px] shrink-0 rounded-full ${TIRA_POR_TIPO[evento.tipo]}`}
        aria-hidden
      />
      <div className="flex-1 space-y-1.5 py-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className={EYEBROW}>{formatarDataPura(evento.data)}</span>
          {ROTULO_POR_TIPO[evento.tipo] && (
            <span className="text-[11px] uppercase tracking-[0.18em] text-sepia/60">
              {ROTULO_POR_TIPO[evento.tipo]}
            </span>
          )}
          {evento.tipo === "ocorrencia" && evento.status && (
            <span
              className={`text-[11px] px-2 py-0.5 rounded ${
                STATUS_BADGE[evento.status as OcorrenciaStatus]
              }`}
            >
              {evento.status_label}
            </span>
          )}
        </div>
        <p className="font-heading text-lg text-tinta leading-snug">
          {evento.titulo}
        </p>
        {evento.detalhe && (
          <p className="text-sm text-muted-foreground whitespace-pre-line">
            {evento.detalhe}
          </p>
        )}
        {(evento.turma || evento.autor) && (
          <p className="text-xs text-sepia">
            {[evento.turma, evento.autor].filter(Boolean).join(" · ")}
          </p>
        )}
      </div>
    </div>
  );

  if (destino) {
    return (
      <Link
        to={destino}
        className="block bg-paper rounded-lg border border-border p-4 transition-all hover:shadow-sm hover:border-ferrugem/40"
      >
        {corpo}
      </Link>
    );
  }
  return (
    <div className="bg-paper rounded-lg border border-border p-4">{corpo}</div>
  );
}

// Timeline do aluno (item 13 do roadmap) — centraliza num lugar só o que
// está espalhado por três telas: ocorrências, chamada e as mudanças de
// cadastro que o audit log guarda.
//
// Leitura, sem escrita: cada bloco linka pra tela onde o registro é
// editado. É a resposta pra pergunta do conselho de classe ("o que houve
// com este aluno"), que até agora exigia abrir Ocorrências, filtrar por
// aluno, abrir Presença, e cruzar as duas de cabeça.
export function AlunoTimelinePage() {
  const params = useParams<{ id: string }>();
  const alunoId = params.id ? parseInt(params.id, 10) : undefined;
  // Guarda contra URL malformada (/alunos/abc/timeline -> NaN): sem isso
  // a query chamaria o endpoint com um id inválido.
  const idValido = alunoId != null && Number.isFinite(alunoId);

  const [janela, setJanela] = useState<JanelaId>("tudo");
  const timelineQuery = useTimelineAluno(
    idValido ? alunoId : undefined,
    paramsDaJanela(janela),
  );

  if (!idValido) {
    return (
      <div className="p-4 md:p-8 space-y-4">
        <p className="text-sm text-muted-foreground">Aluno inválido.</p>
        <Link to="/alunos" className="text-sm text-ferrugem underline">
          Voltar para alunos
        </Link>
      </div>
    );
  }

  if (timelineQuery.isLoading) {
    return (
      <div className="p-4 md:p-8 space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    );
  }

  if (timelineQuery.isError || !timelineQuery.data) {
    return (
      <div className="p-4 md:p-8 space-y-4">
        <p className="text-sm text-destructive">
          Não foi possível carregar a timeline deste aluno.
        </p>
        <Link to="/alunos" className="text-sm text-ferrugem underline">
          Voltar para alunos
        </Link>
      </div>
    );
  }

  const { aluno, eventos, total_eventos, truncado, limite } =
    timelineQuery.data;
  const grupos = agruparPorMes(eventos);

  return (
    <div className="p-4 md:p-8 space-y-8">
      <header className="space-y-3">
        <Link to="/alunos" className={`${EYEBROW} hover:text-tinta`}>
          ← Alunos
        </Link>
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          {aluno.nome_completo}
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
        <p className="text-sm text-muted-foreground">
          Matrícula {aluno.matricula} · {aluno.turma}
          {!aluno.ativo && " · aluno inativo"}
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <Label htmlFor="janela" className={EYEBROW}>
          Período
        </Label>
        <Select
          value={janela}
          onValueChange={(valor) => setJanela(valor as JanelaId)}
        >
          <SelectTrigger id="janela" className="w-[220px] bg-paper border-border">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {JANELAS.map((opcao) => (
              <SelectItem key={opcao.id} value={opcao.id}>
                {opcao.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs text-sepia">
          {total_eventos} evento{total_eventos === 1 ? "" : "s"}
        </span>
      </div>

      {truncado && (
        <p className="text-sm text-destructive">
          Mostrando os {limite} eventos mais recentes de {total_eventos}.
          Escolha um período menor para ver o resto.
        </p>
      )}

      {grupos.length === 0 ? (
        <div className="bg-paper rounded-lg border border-border p-6">
          <p className="font-heading text-lg text-tinta mb-1">
            Nenhum evento no período
          </p>
          <p className="text-sm text-sepia">
            Ocorrências, faltas e mudanças de cadastro aparecem aqui em
            ordem cronológica.
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {grupos.map((grupo) => (
            <section key={grupo.chave} className="space-y-3">
              <h2 className={EYEBROW}>{grupo.label}</h2>
              <div className="space-y-3">
                {grupo.eventos.map((evento, indice) => (
                  <EventoBloco
                    // Sem id estável no evento (a timeline é agregada de
                    // três origens, e o id só existe em duas): a chave
                    // combina tipo, data e posição no grupo.
                    key={`${evento.tipo}-${evento.data}-${indice}`}
                    evento={evento}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
