import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { useAvaliacoes } from "@/features/avaliacoes/hooks";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import {
  useInicializarNotasPeriodo,
  useLancarNotasFinais,
} from "@/features/notas-finais/hooks";
import { usePeriodosAvaliativos } from "@/features/periodos-avaliativos/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { cn } from "@/lib/utils";
import type { LancarNotaFinalItem, NotaPeriodo } from "@/types/api";

// Estado controlado por linha. String pra suportar input vazio e
// edição parcial (vírgula decimal etc.).
interface LinhaEstado {
  nota_final: string;
  observacao: string;
}

function formatarTimestamp(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Página de lançamento de notas finais por (Turma × Disciplina × Período).
// Acessível pela sidebar; layout tipo chamada com 3 selects no topo.
//
// Quando os 3 selects estão preenchidos, dispara `inicializar` no
// backend (idempotente — cria NotaPeriodo vazia pra cada aluno ativo
// que ainda não tem). A tabela aparece pronta pra digitar.
//
// Mostra também as `NotaAvaliacao` daquela combinação (provas/trabalhos
// já lançados naquele período pra aquela disciplina/turma) como
// **referência** — escola vê 7/8/9 e decide a média final. Sistema não
// calcula.
export function NotasFinaisPage() {
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();
  const periodosQuery = usePeriodosAvaliativos({ ativo: true });
  const inicializarMutation = useInicializarNotasPeriodo();
  const lancarMutation = useLancarNotasFinais();

  const [turmaId, setTurmaId] = useState("");
  const [disciplinaId, setDisciplinaId] = useState("");
  const [periodoId, setPeriodoId] = useState("");
  const [notas, setNotas] = useState<NotaPeriodo[]>([]);
  const [linhas, setLinhas] = useState<Record<number, LinhaEstado>>({});
  const [erroSubmit, setErroSubmit] = useState<string | null>(null);

  const filtroCompleto =
    turmaId !== "" && disciplinaId !== "" && periodoId !== "";

  // Carrega/inicializa notas sempre que os 3 selects estão preenchidos.
  useEffect(() => {
    if (!filtroCompleto) {
      setNotas([]);
      setLinhas({});
      return;
    }
    inicializarMutation.mutate(
      {
        turma: parseInt(turmaId, 10),
        disciplina: parseInt(disciplinaId, 10),
        periodo: parseInt(periodoId, 10),
      },
      {
        onSuccess: (dados) => {
          setNotas(dados);
          const novo: Record<number, LinhaEstado> = {};
          for (const n of dados) {
            novo[n.id] = {
              nota_final: n.nota_final ?? "",
              observacao: n.observacao,
            };
          }
          setLinhas(novo);
        },
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turmaId, disciplinaId, periodoId]);

  // Avaliações daquela combinação — mostra notas individuais como
  // referência ao lado de cada aluno.
  const avaliacoesQuery = useAvaliacoes(
    filtroCompleto
      ? {
          turma: parseInt(turmaId, 10),
          disciplina: parseInt(disciplinaId, 10),
          periodo: parseInt(periodoId, 10),
          ativo: true,
        }
      : undefined,
  );

  // Itens "sujos" — só envia o que mudou.
  const itensSujos: LancarNotaFinalItem[] = useMemo(() => {
    const sujos: LancarNotaFinalItem[] = [];
    for (const n of notas) {
      const atual = linhas[n.id];
      if (!atual) continue;
      const notaBackend = n.nota_final ?? "";
      const obsBackend = n.observacao;
      if (
        atual.nota_final !== notaBackend ||
        atual.observacao !== obsBackend
      ) {
        sujos.push({
          aluno_id: n.aluno,
          nota_final: atual.nota_final === "" ? null : atual.nota_final,
          observacao: atual.observacao,
        });
      }
    }
    return sujos;
  }, [linhas, notas]);

  function atualizarLinha(notaId: number, patch: Partial<LinhaEstado>) {
    setLinhas((prev) => ({ ...prev, [notaId]: { ...prev[notaId], ...patch } }));
  }

  async function handleSalvar() {
    if (itensSujos.length === 0) return;
    setErroSubmit(null);
    try {
      const resp = await lancarMutation.mutateAsync({
        turma: parseInt(turmaId, 10),
        disciplina: parseInt(disciplinaId, 10),
        periodo: parseInt(periodoId, 10),
        itens: itensSujos,
      });
      if (resp.falhas.length > 0) {
        setErroSubmit(
          `${resp.falhas.length} linha${resp.falhas.length > 1 ? "s" : ""} falharam. Nada foi salvo.`,
        );
      } else {
        // Refaz inicializar pra carregar `ultima_edicao` atualizada.
        inicializarMutation.mutate(
          {
            turma: parseInt(turmaId, 10),
            disciplina: parseInt(disciplinaId, 10),
            periodo: parseInt(periodoId, 10),
          },
          {
            onSuccess: (dados) => {
              setNotas(dados);
              const novo: Record<number, LinhaEstado> = {};
              for (const n of dados) {
                novo[n.id] = {
                  nota_final: n.nota_final ?? "",
                  observacao: n.observacao,
                };
              }
              setLinhas(novo);
            },
          },
        );
      }
    } catch (err) {
      console.error(err);
      setErroSubmit("Falha ao salvar. Tente novamente.");
    }
  }

  // Nota: pra mostrar as notas individuais de cada aluno como
  // referência (ex.: "Ana: 7,0; 8,5; 9,0"), precisaria de endpoint
  // agregado que retorne NotaAvaliacao por aluno × período. Hoje
  // mostramos só o COUNT de avaliações lançadas no header da seção
  // — escola consulta as notas individuais entrando na avaliação
  // específica. Frente futura: endpoint agregado.

  // Turmas ativas só (reduz ruído no select).
  const turmasAtivas = (turmasQuery.data ?? []).filter((t) => t.ativa);
  const disciplinasAtivas = (disciplinasQuery.data ?? []).filter(
    (d) => d.ativa,
  );

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="space-y-3">
        <p className="text-[11px] uppercase tracking-[0.2em] text-sepia">
          Avaliação
        </p>
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          Notas finais
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
        <p className="text-sm text-sepia max-w-2xl">
          Média final de cada aluno por disciplina e período. O sistema
          armazena — a regra da média (peso, recuperação, conselho)
          continua com a escola.
        </p>
      </header>

      {/* Selects: turma + disciplina + período */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="space-y-2">
          <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
            Turma
          </Label>
          <Select value={turmaId} onValueChange={setTurmaId}>
            <SelectTrigger className="bg-paper border-border">
              <SelectValue placeholder="Selecione a turma" />
            </SelectTrigger>
            <SelectContent>
              {turmasAtivas.map((t) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.nome} — {t.ano_letivo}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
            Disciplina
          </Label>
          <Select value={disciplinaId} onValueChange={setDisciplinaId}>
            <SelectTrigger className="bg-paper border-border">
              <SelectValue placeholder="Selecione a disciplina" />
            </SelectTrigger>
            <SelectContent>
              {disciplinasAtivas.map((d) => (
                <SelectItem key={d.id} value={String(d.id)}>
                  {d.nome}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
            Período
          </Label>
          <Select value={periodoId} onValueChange={setPeriodoId}>
            <SelectTrigger className="bg-paper border-border">
              <SelectValue placeholder="Selecione o período" />
            </SelectTrigger>
            <SelectContent>
              {(periodosQuery.data ?? []).map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.nome} ({p.ano_letivo})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </section>

      {!filtroCompleto ? (
        <div className="rounded-lg border border-border bg-paper p-6 text-sepia">
          Selecione turma, disciplina e período pra começar a lançar as
          notas finais.
        </div>
      ) : (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-heading text-xl text-tinta">
              Alunos da turma
            </h2>
            <Button
              onClick={handleSalvar}
              disabled={
                itensSujos.length === 0 || lancarMutation.isPending
              }
            >
              {lancarMutation.isPending
                ? "Salvando..."
                : itensSujos.length === 0
                  ? "Sem alterações"
                  : `Salvar ${itensSujos.length} ${itensSujos.length === 1 ? "nota" : "notas"}`}
            </Button>
          </div>

          {erroSubmit && (
            <p className="text-sm text-destructive">{erroSubmit}</p>
          )}

          <p className="text-[11px] text-sepia/70">
            Toda mudança fica registrada com quem fez e quando — coluna
            "Última edição".
            {avaliacoesQuery.data && avaliacoesQuery.data.length > 0 && (
              <>
                {" "}
                Este período tem{" "}
                <strong>{avaliacoesQuery.data.length}</strong> avaliação
                {avaliacoesQuery.data.length > 1 ? "ões" : ""} lançada
                {avaliacoesQuery.data.length > 1 ? "s" : ""} (
                {avaliacoesQuery.data
                  .map((a) => a.titulo)
                  .slice(0, 3)
                  .join(", ")}
                {avaliacoesQuery.data.length > 3 ? "..." : ""}
                ).
              </>
            )}
          </p>

          <div className="rounded-lg border border-border bg-paper overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Aluno
                  </TableHead>
                  <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal w-28">
                    Nota final
                  </TableHead>
                  <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal hidden md:table-cell">
                    Observação
                  </TableHead>
                  <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal hidden lg:table-cell w-48">
                    Última edição
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {inicializarMutation.isPending ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell>
                        <Skeleton className="h-4 w-32" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-8 w-20" />
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <Skeleton className="h-8 w-full" />
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        <Skeleton className="h-4 w-24" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : notas.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className="text-center text-muted-foreground py-8"
                    >
                      Nenhum aluno ativo nesta turma.
                    </TableCell>
                  </TableRow>
                ) : (
                  notas.map((n) => {
                    const linha = linhas[n.id] ?? {
                      nota_final: "",
                      observacao: "",
                    };
                    return (
                      <TableRow key={n.id}>
                        <TableCell>
                          <div className="text-tinta">{n.aluno_nome}</div>
                          <div className="text-[10px] text-sepia font-mono">
                            {n.aluno_matricula}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Input
                            type="text"
                            inputMode="decimal"
                            value={linha.nota_final}
                            onChange={(e) =>
                              atualizarLinha(n.id, {
                                nota_final: e.target.value,
                              })
                            }
                            placeholder="—"
                            className={cn(
                              "w-24 text-center tabular-nums",
                            )}
                          />
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          <Input
                            type="text"
                            value={linha.observacao}
                            onChange={(e) =>
                              atualizarLinha(n.id, {
                                observacao: e.target.value,
                              })
                            }
                            placeholder="(opcional — não vai pro boletim)"
                            className="w-full"
                          />
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-[11px] text-sepia">
                          {n.ultima_edicao && n.ultima_edicao.em ? (
                            <>
                              <span className="text-tinta">
                                {n.ultima_edicao.por ?? "—"}
                              </span>
                              <br />
                              <span className="font-mono tabular-nums">
                                {formatarTimestamp(n.ultima_edicao.em)}
                              </span>
                            </>
                          ) : (
                            <span className="text-sepia/60">nunca</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </section>
      )}
    </div>
  );
}
