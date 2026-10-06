import { useMemo, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { NomeArquivoDialog } from "@/features/boletins/NomeArquivoDialog";
import { DIAS_SEMANA_CURTO, STATUS_AULA } from "@/features/aulas/constants";
import {
  useBaixarDiarioPDF,
  useConferirAula,
  useRegistrosAula,
} from "@/features/aulas/hooks";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useLecionamentos } from "@/features/lecionamentos/hooks";
import { STATUS_BADGE, STATUS_LABEL } from "@/features/ocorrencias/constants";
import { useOcorrencias } from "@/features/ocorrencias/hooks";
import { useProfessor } from "@/features/professores/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { useEnviarResetSenha } from "@/features/usuarios/hooks";
import type { Lecionamento, RegistroAula, RegistroAulaStatus } from "@/types/api";

// Ficha 360º do professor (visão da direção). Tabs:
//   Diário — lista cronológica das aulas (filtros + agrupada por mês) +
//     visto da direção (conferir).
//   Lecionamentos — vínculos turma × disciplina × grade horária.
//   Ocorrências — ocorrências registradas pelo professor.
//   Dados — cadastro + contadores do diário.
// A tab fica na querystring (?tab=) pra sobreviver a refresh e ao voltar
// do navegador. Diário é o default — é o motivo de a página existir.

const TABS = [
  { id: "diario", label: "Diário" },
  { id: "lecionamentos", label: "Lecionamentos" },
  { id: "ocorrencias", label: "Ocorrências" },
  { id: "dados", label: "Dados" },
] as const;

type TabId = (typeof TABS)[number]["id"];

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

// "2026-06-16" -> "16/06/2026"
function formatarData(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("pt-BR");
}

// ISO datetime -> "16/06/2026 14:30"
function formatarDataHora(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Agrupa as aulas por mês (YYYY-MM) preservando a ordem cronológica que o
// backend já entrega (-data). Cada grupo vira uma seção com cabeçalho.
function agruparPorMes(aulas: RegistroAula[]) {
  const grupos: { chave: string; label: string; aulas: RegistroAula[] }[] = [];
  const indice = new Map<string, number>();
  for (const aula of aulas) {
    const chave = aula.data.slice(0, 7);
    let idx = indice.get(chave);
    if (idx === undefined) {
      const [ano, mes] = chave.split("-");
      idx =
        grupos.push({
          chave,
          label: `${MESES[Number(mes) - 1]} ${ano}`,
          aulas: [],
        }) - 1;
      indice.set(chave, idx);
    }
    grupos[idx].aulas.push(aula);
  }
  return grupos;
}

export function ProfessorDetalhePage() {
  const params = useParams<{ id: string }>();
  const professorId = params.id ? parseInt(params.id, 10) : undefined;
  // Guarda contra URL malformada (/professores/abc -> NaN): sem isso as
  // queries cairiam no filtro vazio e buscariam a escola inteira.
  const idValido = professorId != null && Number.isFinite(professorId);

  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tab: TabId = TABS.some((t) => t.id === tabParam)
    ? (tabParam as TabId)
    : "diario";

  function selecionarTab(id: TabId) {
    // `replace` evita empilhar uma entrada de histórico por clique de tab.
    setSearchParams(id === "diario" ? {} : { tab: id }, { replace: true });
  }

  const { podeModificarCadastros } = usePermissoes();
  const enviarResetSenha = useEnviarResetSenha();

  const professorQuery = useProfessor(professorId);
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();

  // Visão geral SEM filtro — alimenta o badge de pendência no topo e os
  // contadores da aba Dados. Independe dos filtros aplicados no Diário.
  const resumoAulasQuery = useRegistrosAula(
    idValido ? { professor: professorId } : {},
    idValido,
  );
  const lecionamentosResumoQuery = useLecionamentos(
    idValido ? { professor: professorId } : {},
    idValido,
  );

  const turmasPorId = useMemo(() => {
    const m = new Map<number, string>();
    turmasQuery.data?.forEach((t) => m.set(t.id, t.nome));
    return m;
  }, [turmasQuery.data]);

  const disciplinasPorId = useMemo(() => {
    const m = new Map<number, string>();
    disciplinasQuery.data?.forEach((d) => m.set(d.id, d.nome));
    return m;
  }, [disciplinasQuery.data]);

  const pendentes = useMemo(
    () =>
      (resumoAulasQuery.data ?? []).filter((a) => a.status === "lancado")
        .length,
    [resumoAulasQuery.data],
  );

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="space-y-3">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/professores">← Voltar</Link>
        </Button>
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          {!idValido ? (
            "Professor não encontrado"
          ) : professorQuery.isLoading ? (
            <Skeleton className="h-8 w-64" />
          ) : professorQuery.data ? (
            professorQuery.data.nome_completo || "Professor"
          ) : (
            "Professor não encontrado"
          )}
        </h1>
        <div className="h-px w-10 bg-ferrugem" />

        {idValido && podeModificarCadastros && (
          <div className="flex flex-wrap items-center gap-3 pt-1">
            {/* Pendência de visto — só quando há o que conferir. */}
            {pendentes > 0 && (
              <button
                type="button"
                onClick={() => selecionarTab("diario")}
                className="inline-flex items-center gap-2 rounded-full bg-ferrugem/10 px-3 py-1 text-xs font-medium text-ferrugem"
              >
                {pendentes}{" "}
                {pendentes === 1
                  ? "aula aguardando seu visto"
                  : "aulas aguardando seu visto"}
              </button>
            )}
            {/* Envia link de reset de senha pro Usuario do professor.
                Mesmo fluxo do "Esqueci senha" — usado pra destravar
                acesso sem compartilhar senha. */}
            {professorQuery.data?.usuario && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  enviarResetSenha.mutate(professorQuery.data!.usuario)
                }
                disabled={enviarResetSenha.isPending}
              >
                Enviar link de reset de senha
              </Button>
            )}
          </div>
        )}
      </header>

      {!idValido ? (
        <p className="text-sm text-sepia">
          Verifique o endereço — o identificador do professor é inválido.
        </p>
      ) : (
        <>
          {/* Switcher de tabs — leve, sem dependência de radix. Filete
              ferrugem marca a tab ativa, no mesmo espírito da sidebar. */}
          <nav className="flex gap-1 border-b border-border" role="tablist">
            {TABS.map((t) => {
              const ativo = t.id === tab;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  id={`tab-${t.id}`}
                  aria-selected={ativo}
                  aria-controls={`panel-${t.id}`}
                  onClick={() => selecionarTab(t.id)}
                  className={`relative px-3 py-2 text-sm transition-colors ${
                    ativo
                      ? "text-tinta font-medium"
                      : "text-sepia hover:text-tinta"
                  }`}
                >
                  {t.label}
                  {ativo && (
                    <span className="absolute inset-x-0 -bottom-px h-0.5 bg-ferrugem" />
                  )}
                </button>
              );
            })}
          </nav>

          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === "diario" && (
              <DiarioTab
                professorId={professorId}
                professorNome={professorQuery.data?.nome_completo}
                turmasPorId={turmasPorId}
                disciplinasPorId={disciplinasPorId}
                podeConferir={podeModificarCadastros}
              />
            )}
            {tab === "lecionamentos" && (
              <LecionamentosTab
                professorId={professorId}
                turmasPorId={turmasPorId}
                disciplinasPorId={disciplinasPorId}
              />
            )}
            {tab === "ocorrencias" && (
              <OcorrenciasTab
                professorId={professorId}
                turmasPorId={turmasPorId}
              />
            )}
            {tab === "dados" && (
              <DadosTab
                carregando={professorQuery.isLoading}
                professor={professorQuery.data}
                aulas={resumoAulasQuery.data ?? []}
                lecionamentos={lecionamentosResumoQuery.data ?? []}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}

interface MapsProps {
  professorId: number | undefined;
  turmasPorId: Map<number, string>;
  disciplinasPorId: Map<number, string>;
}

// Sentinela do select de status — shadcn Select não aceita value vazio.
const STATUS_TODOS = "todos";
const STATUS_OPCOES: RegistroAulaStatus[] = ["rascunho", "lancado", "conferido"];

function DiarioTab({
  professorId,
  professorNome,
  turmasPorId,
  disciplinasPorId,
  podeConferir,
}: MapsProps & { podeConferir: boolean; professorNome?: string }) {
  const [status, setStatus] = useState<string>(STATUS_TODOS);
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [pdfDialogAberto, setPdfDialogAberto] = useState(false);

  const temFiltro = status !== STATUS_TODOS || !!dataInicio || !!dataFim;

  const aulasQuery = useRegistrosAula(
    professorId
      ? {
          professor: professorId,
          ...(status !== STATUS_TODOS ? { status } : {}),
          ...(dataInicio ? { data_inicio: dataInicio } : {}),
          ...(dataFim ? { data_fim: dataFim } : {}),
        }
      : {},
  );
  const conferir = useConferirAula();
  const baixarPdf = useBaixarDiarioPDF();

  // Nome default do arquivo: diario_<professor> (sem extensão).
  const nomePdfDefault = `diario_${(professorNome || "aula")
    .toLowerCase()
    .replace(/\s+/g, "_")}`;

  function exportarPdf(nome: string) {
    if (!professorId) return;
    baixarPdf.mutate(
      {
        professor: professorId,
        ...(status !== STATUS_TODOS ? { status } : {}),
        ...(dataInicio ? { data_inicio: dataInicio } : {}),
        ...(dataFim ? { data_fim: dataFim } : {}),
        nome,
      },
      { onSuccess: () => setPdfDialogAberto(false) },
    );
  }

  function limparFiltros() {
    setStatus(STATUS_TODOS);
    setDataInicio("");
    setDataFim("");
  }

  const grupos = useMemo(
    () => agruparPorMes(aulasQuery.data ?? []),
    [aulasQuery.data],
  );

  return (
    <div className="space-y-5">
      {/* Barra de filtros — período + status. O backend já recorta via
          RegistroAulaFilter (data_inicio/data_fim/status). */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="space-y-1">
          <label className="text-[11px] uppercase tracking-[0.15em] text-sepia">
            Status
          </label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-full sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={STATUS_TODOS}>Todos</SelectItem>
              {STATUS_OPCOES.map((s) => (
                <SelectItem key={s} value={s}>
                  {STATUS_AULA[s].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] uppercase tracking-[0.15em] text-sepia">
            De
          </label>
          <Input
            type="date"
            value={dataInicio}
            max={dataFim || undefined}
            onChange={(e) => setDataInicio(e.target.value)}
            className="w-full sm:w-40"
          />
        </div>

        <div className="space-y-1">
          <label className="text-[11px] uppercase tracking-[0.15em] text-sepia">
            Até
          </label>
          <Input
            type="date"
            value={dataFim}
            min={dataInicio || undefined}
            onChange={(e) => setDataFim(e.target.value)}
            className="w-full sm:w-40"
          />
        </div>

        {temFiltro && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={limparFiltros}
          >
            Limpar
          </Button>
        )}

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="sm:ml-auto"
          disabled={(aulasQuery.data?.length ?? 0) === 0}
          onClick={() => setPdfDialogAberto(true)}
        >
          Exportar PDF
        </Button>
      </div>

      {aulasQuery.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : aulasQuery.isError ? (
        <p className="text-sm text-destructive">Erro ao carregar o diário.</p>
      ) : grupos.length === 0 ? (
        <p className="text-sm text-sepia">
          {temFiltro
            ? "Nenhuma aula no filtro selecionado."
            : "Nenhuma aula registrada por este professor."}
        </p>
      ) : (
        <div className="space-y-6">
          {grupos.map((grupo) => (
            <section key={grupo.chave} className="space-y-2">
              <h2 className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                {grupo.label}
              </h2>
              <ul className="space-y-3">
                {grupo.aulas.map((aula) => (
                  <AulaItem
                    key={aula.id}
                    aula={aula}
                    turmasPorId={turmasPorId}
                    disciplinasPorId={disciplinasPorId}
                    podeConferir={podeConferir}
                    conferindo={
                      conferir.isPending && conferir.variables === aula.id
                    }
                    onConferir={() => conferir.mutate(aula.id)}
                  />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      <NomeArquivoDialog
        open={pdfDialogAberto}
        onOpenChange={setPdfDialogAberto}
        nomeDefault={nomePdfDefault}
        extensao=".pdf"
        titulo="Exportar diário em PDF"
        descricao="O PDF sai com o recorte atual (status e período) e espaço de assinatura."
        enviando={baixarPdf.isPending}
        onConfirmar={exportarPdf}
      />
    </div>
  );
}

function AulaItem({
  aula,
  turmasPorId,
  disciplinasPorId,
  podeConferir,
  conferindo,
  onConferir,
}: {
  aula: RegistroAula;
  turmasPorId: Map<number, string>;
  disciplinasPorId: Map<number, string>;
  podeConferir: boolean;
  conferindo: boolean;
  onConferir: () => void;
}) {
  const estilo = STATUS_AULA[aula.status];
  return (
    <li className="rounded-md border border-border bg-paper px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-sm font-medium text-tinta tabular-nums">
          {formatarData(aula.data)}
        </span>
        <span className="text-sm text-sepia">
          {turmasPorId.get(aula.turma) ?? `Turma #${aula.turma}`}
          {" · "}
          {disciplinasPorId.get(aula.disciplina) ??
            `Disciplina #${aula.disciplina}`}
        </span>
        <span
          className={`ml-auto shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${estilo.classe}`}
        >
          {estilo.label}
        </span>
      </div>

      {aula.conteudo && (
        <p className="mt-2 text-sm text-tinta whitespace-pre-wrap">
          {aula.conteudo}
        </p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-3">
        {aula.status === "conferido" && aula.conferido_em && (
          <span className="text-[11px] text-sepia">
            Conferido por {aula.conferido_por_nome ?? "—"} em{" "}
            {formatarDataHora(aula.conferido_em)}
          </span>
        )}
        {podeConferir && aula.status === "lancado" && (
          <Button
            type="button"
            size="sm"
            className="ml-auto"
            disabled={conferindo}
            onClick={onConferir}
          >
            Conferir
          </Button>
        )}
      </div>
    </li>
  );
}

function LecionamentosTab({
  professorId,
  turmasPorId,
  disciplinasPorId,
}: MapsProps) {
  const lecionamentosQuery = useLecionamentos(
    professorId ? { professor: professorId } : {},
  );

  if (lecionamentosQuery.isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }
  if (lecionamentosQuery.isError) {
    return (
      <p className="text-sm text-destructive">
        Erro ao carregar lecionamentos.
      </p>
    );
  }
  const lecionamentos = lecionamentosQuery.data ?? [];
  if (lecionamentos.length === 0) {
    return (
      <p className="text-sm text-sepia">
        Este professor não tem vínculos de turma/disciplina.
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-paper overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
              Turma
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
              Disciplina
            </TableHead>
            <TableHead className="hidden md:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
              Dias
            </TableHead>
            <TableHead className="hidden sm:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
              Status
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lecionamentos.map((l) => (
            <TableRow key={l.id}>
              <TableCell>{turmasPorId.get(l.turma) ?? `#${l.turma}`}</TableCell>
              <TableCell>
                {disciplinasPorId.get(l.disciplina) ?? `#${l.disciplina}`}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                <div className="flex flex-wrap gap-1">
                  {/* `dias_semana` pode vir ausente de backends antigos
                      (campo só foi exposto no serializer junto desta tela);
                      defaulta pra lista vazia pra não quebrar a aba. */}
                  {(l.dias_semana ?? []).length === 0 ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : (
                    (l.dias_semana ?? []).map((d) => (
                      <span
                        key={d}
                        className="text-xs bg-muted px-1.5 py-0.5 rounded"
                      >
                        {DIAS_SEMANA_CURTO[d]}
                      </span>
                    ))
                  )}
                </div>
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                {l.ativo ? (
                  <span className="text-[10px] uppercase tracking-wide text-olive bg-olive/10 px-1.5 py-0.5 rounded">
                    Ativo
                  </span>
                ) : (
                  <span className="text-[10px] uppercase tracking-wide text-sepia">
                    Inativo
                  </span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function OcorrenciasTab({
  professorId,
  turmasPorId,
}: {
  professorId: number | undefined;
  turmasPorId: Map<number, string>;
}) {
  const navigate = useNavigate();
  const ocorrenciasQuery = useOcorrencias(
    professorId ? { professor: professorId } : {},
  );

  if (ocorrenciasQuery.isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }
  if (ocorrenciasQuery.isError) {
    return (
      <p className="text-sm text-destructive">Erro ao carregar ocorrências.</p>
    );
  }
  const ocorrencias = ocorrenciasQuery.data ?? [];
  if (ocorrencias.length === 0) {
    return (
      <p className="text-sm text-sepia">
        Nenhuma ocorrência registrada por este professor.
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-paper overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
              Data
            </TableHead>
            <TableHead className="hidden md:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
              Turma
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
              Descrição
            </TableHead>
            <TableHead className="hidden sm:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
              Status
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {ocorrencias.map((o) => (
            <TableRow
              key={o.id}
              className="cursor-pointer"
              onClick={() => navigate(`/ocorrencias/${o.id}`)}
            >
              <TableCell className="tabular-nums whitespace-nowrap">
                {formatarData(o.data_ocorrencia)}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                {turmasPorId.get(o.turma) ?? `#${o.turma}`}
              </TableCell>
              <TableCell className="max-w-xs truncate">{o.descricao}</TableCell>
              <TableCell className="hidden sm:table-cell">
                <span
                  className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[o.status]}`}
                >
                  {STATUS_LABEL[o.status]}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ContadorAula({ valor, label }: { valor: number; label: string }) {
  return (
    <div className="rounded-md border border-border bg-paper px-4 py-3">
      <div className="font-heading text-2xl leading-none text-tinta tabular-nums">
        {valor}
      </div>
      <div className="mt-1 text-[11px] uppercase tracking-[0.12em] text-sepia">
        {label}
      </div>
    </div>
  );
}

function DadosTab({
  carregando,
  professor,
  aulas,
  lecionamentos,
}: {
  carregando: boolean;
  professor:
    | {
        nome_completo: string;
        ativo: boolean;
      }
    | undefined;
  aulas: RegistroAula[];
  lecionamentos: Lecionamento[];
}) {
  if (carregando) {
    return <Skeleton className="h-32 w-full" />;
  }
  if (!professor) {
    return <p className="text-sm text-sepia">Professor não encontrado.</p>;
  }

  const conferidas = aulas.filter((a) => a.status === "conferido").length;
  const aguardando = aulas.filter((a) => a.status === "lancado").length;
  const rascunhos = aulas.filter((a) => a.status === "rascunho").length;
  const vinculosAtivos = lecionamentos.filter((l) => l.ativo).length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <ContadorAula valor={aulas.length} label="Aulas no total" />
        <ContadorAula valor={rascunhos} label="Rascunhos" />
        <ContadorAula valor={aguardando} label="Aguardando visto" />
        <ContadorAula valor={conferidas} label="Conferidas" />
        <ContadorAula valor={vinculosAtivos} label="Vínculos ativos" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg tracking-tight">
            Dados do professor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
              Nome
            </dt>
            <dd>{professor.nome_completo || "—"}</dd>
            <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
              Status
            </dt>
            <dd>{professor.ativo ? "Ativo" : "Inativo"}</dd>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
