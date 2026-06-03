import { Link, useParams } from "react-router-dom";

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
import { useBoletim } from "@/features/boletins/hooks";

// Página /boletim/:alunoId — visão consolidada do aluno (frequência,
// notas por disciplina e ocorrências). Botão "Imprimir" dispara
// `window.print()`; as classes `print:*` no JSX e o CSS print no
// index.css escondem a sidebar e os botões durante a impressão.
export function BoletimPage() {
  const params = useParams<{ alunoId: string }>();
  const alunoId = params.alunoId ? parseInt(params.alunoId, 10) : undefined;
  const boletimQuery = useBoletim(alunoId);

  const boletim = boletimQuery.data;

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-4xl mx-auto print:p-0 print:max-w-none">
      <header className="space-y-3 print:hidden">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/alunos">← Voltar</Link>
        </Button>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="space-y-3">
            <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
              Boletim
            </h1>
            <div className="h-px w-10 bg-ferrugem" />
          </div>
          <Button variant="outline" onClick={() => window.print()}>
            Imprimir
          </Button>
        </div>
      </header>

      {/* Cabeçalho que aparece SÓ na impressão — tipografia plana, sem
          paleta da marca, pra economizar tinta e ficar serio em papel. */}
      <header className="hidden print:block space-y-1 mb-6">
        <h1 className="text-2xl font-semibold">Boletim escolar</h1>
        <p className="text-sm">
          Emitido em {new Date().toLocaleDateString("pt-BR")}
        </p>
      </header>

      {boletimQuery.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-40 w-full" />
          </CardContent>
        </Card>
      ) : boletimQuery.isError || !boletim ? (
        <Card>
          <CardContent className="pt-6 text-destructive">
            Não foi possível carregar o boletim.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Aluno
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Nome
                </dt>
                <dd>{boletim.aluno.nome_completo}</dd>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Matrícula
                </dt>
                <dd className="font-mono">{boletim.aluno.matricula}</dd>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Turma
                </dt>
                <dd>{boletim.turma.nome ?? "—"}</dd>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Situação
                </dt>
                <dd>{boletim.aluno.ativo ? "Ativo" : "Inativo"}</dd>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Frequência
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <Indicador label="Presenças" valor={boletim.frequencia.presentes} />
                <Indicador
                  label="Retardatários"
                  valor={boletim.frequencia.retardatarios}
                />
                <Indicador
                  label="Justificadas"
                  valor={boletim.frequencia.justificados}
                />
                <Indicador label="Faltas" valor={boletim.frequencia.ausentes} />
              </div>
              <div className="border-t border-border pt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                    Total de chamadas
                  </p>
                  <p className="font-heading text-3xl tabular-nums text-tinta">
                    {boletim.frequencia.total}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                    Frequência
                  </p>
                  <p className="font-heading text-3xl tabular-nums text-tinta">
                    {boletim.frequencia.percentual_presenca}%
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Notas por disciplina
              </CardTitle>
            </CardHeader>
            <CardContent>
              {boletim.notas_por_disciplina.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  Nenhuma nota lançada até o momento.
                </p>
              ) : (
                <div className="space-y-6">
                  {boletim.notas_por_disciplina.map((d) => (
                    <div key={d.disciplina.id} className="space-y-2">
                      <div className="flex items-baseline justify-between">
                        <h3 className="font-heading text-base tracking-tight">
                          {d.disciplina.nome}
                        </h3>
                        <span className="text-sm">
                          <span className="text-sepia">Média ponderada:</span>{" "}
                          <strong className="tabular-nums">
                            {d.media_ponderada}
                          </strong>
                        </span>
                      </div>
                      <div className="rounded-lg border border-border bg-paper overflow-hidden print:bg-white">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                Tarefa
                              </TableHead>
                              <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                Nota
                              </TableHead>
                              <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                Máxima
                              </TableHead>
                              <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                Peso
                              </TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {d.tarefas.map((t) => (
                              <TableRow key={t.tarefa_id}>
                                <TableCell>{t.titulo}</TableCell>
                                <TableCell className="text-right tabular-nums">
                                  {t.nota}
                                </TableCell>
                                <TableCell className="text-right tabular-nums text-muted-foreground">
                                  {t.nota_maxima ?? "—"}
                                </TableCell>
                                <TableCell className="text-right tabular-nums text-muted-foreground">
                                  {t.peso}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Ocorrências
              </CardTitle>
            </CardHeader>
            <CardContent>
              {boletim.ocorrencias.total === 0 ? (
                <p className="text-sm text-muted-foreground py-2">
                  Sem ocorrências registradas.
                </p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  <Indicador
                    label="Abertas"
                    valor={boletim.ocorrencias.abertas}
                  />
                  <Indicador
                    label="Em andamento"
                    valor={boletim.ocorrencias.em_andamento}
                  />
                  <Indicador
                    label="Resolvidas"
                    valor={boletim.ocorrencias.resolvidas}
                  />
                  <Indicador
                    label="Arquivadas"
                    valor={boletim.ocorrencias.arquivadas}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function Indicador({ label, valor }: { label: string; valor: number }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
        {label}
      </p>
      <p className="font-heading text-3xl tabular-nums text-tinta">{valor}</p>
    </div>
  );
}
