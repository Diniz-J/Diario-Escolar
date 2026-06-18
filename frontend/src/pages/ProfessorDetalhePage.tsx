import { useMemo } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DIAS_SEMANA_CURTO, STATUS_AULA } from "@/features/aulas/constants";
import { useConferirAula, useRegistrosAula } from "@/features/aulas/hooks";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useLecionamentos } from "@/features/lecionamentos/hooks";
import { STATUS_BADGE, STATUS_LABEL } from "@/features/ocorrencias/constants";
import { useOcorrencias } from "@/features/ocorrencias/hooks";
import { useProfessor } from "@/features/professores/hooks";
import { useTurmas } from "@/features/turmas/hooks";

// Ficha 360º do professor (visão da direção). Tabs:
//   Diário — lista cronológica das aulas + visto da direção (conferir).
//   Lecionamentos — vínculos turma × disciplina × grade horária.
//   Ocorrências — ocorrências registradas pelo professor.
//   Dados — cadastro do professor.
// A tab fica na querystring (?tab=) pra sobreviver a refresh e ao voltar
// do navegador. Diário é o default — é o motivo de a página existir.

const TABS = [
  { id: "diario", label: "Diário" },
  { id: "lecionamentos", label: "Lecionamentos" },
  { id: "ocorrencias", label: "Ocorrências" },
  { id: "dados", label: "Dados" },
] as const;

type TabId = (typeof TABS)[number]["id"];

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

export function ProfessorDetalhePage() {
  const params = useParams<{ id: string }>();
  const professorId = params.id ? parseInt(params.id, 10) : undefined;

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

  const professorQuery = useProfessor(professorId);
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();

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

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="space-y-3">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/professores">← Voltar</Link>
        </Button>
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          {professorQuery.isLoading ? (
            <Skeleton className="h-8 w-64" />
          ) : professorQuery.data ? (
            professorQuery.data.nome_completo || "Professor"
          ) : (
            "Professor não encontrado"
          )}
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
      </header>

      {/* Switcher de tabs — leve, sem dependência de radix. Filete ferrugem
          marca a tab ativa, no mesmo espírito da sidebar. */}
      <nav className="flex gap-1 border-b border-border" role="tablist">
        {TABS.map((t) => {
          const ativo = t.id === tab;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={ativo}
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

      {tab === "diario" && (
        <DiarioTab
          professorId={professorId}
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
        />
      )}
    </div>
  );
}

interface MapsProps {
  professorId: number | undefined;
  turmasPorId: Map<number, string>;
  disciplinasPorId: Map<number, string>;
}

function DiarioTab({
  professorId,
  turmasPorId,
  disciplinasPorId,
  podeConferir,
}: MapsProps & { podeConferir: boolean }) {
  const aulasQuery = useRegistrosAula(
    professorId ? { professor: professorId } : {},
  );
  const conferir = useConferirAula();

  if (aulasQuery.isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }
  if (aulasQuery.isError) {
    return (
      <p className="text-sm text-destructive">Erro ao carregar o diário.</p>
    );
  }
  const aulas = aulasQuery.data ?? [];
  if (aulas.length === 0) {
    return (
      <p className="text-sm text-sepia">
        Nenhuma aula registrada por este professor.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {aulas.map((aula) => {
        const estilo = STATUS_AULA[aula.status];
        return (
          <li
            key={aula.id}
            className="rounded-md border border-border bg-paper px-4 py-3"
          >
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
                  disabled={conferir.isPending}
                  onClick={() => conferir.mutate(aula.id)}
                >
                  Conferir
                </Button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
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
                  {l.dias_semana.length === 0 ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : (
                    l.dias_semana.map((d) => (
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

function DadosTab({
  carregando,
  professor,
}: {
  carregando: boolean;
  professor:
    | {
        nome_completo: string;
        ativo: boolean;
      }
    | undefined;
}) {
  if (carregando) {
    return <Skeleton className="h-32 w-full" />;
  }
  if (!professor) {
    return (
      <p className="text-sm text-sepia">Professor não encontrado.</p>
    );
  }

  return (
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
  );
}
