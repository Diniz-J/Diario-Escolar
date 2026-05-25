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
    <div className="p-8 space-y-6 max-w-4xl mx-auto print:p-0 print:max-w-none">
      <header className="space-y-2 print:hidden">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/alunos">← Voltar</Link>
        </Button>
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-semibold">Boletim</h1>
          <Button variant="outline" onClick={() => window.print()}>
            Imprimir
          </Button>
        </div>
      </header>

      {/* Cabeçalho que aparece SÓ na impressão. */}
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
              <CardTitle>Aluno</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Nome</dt>
                <dd>{boletim.aluno.nome_completo}</dd>
                <dt className="text-muted-foreground">Matrícula</dt>
                <dd className="font-mono">{boletim.aluno.matricula}</dd>
                <dt className="text-muted-foreground">Turma</dt>
                <dd>{boletim.turma.nome ?? "—"}</dd>
                <dt className="text-muted-foreground">Situação</dt>
                <dd>{boletim.aluno.ativo ? "Ativo" : "Inativo"}</dd>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Frequência</CardTitle>
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
              <div className="border-t pt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground text-xs uppercase">
                    Total de chamadas
                  </p>
                  <p className="text-2xl font-semibold tabular-nums">
                    {boletim.frequencia.total}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs uppercase">
                    Frequência
                  </p>
                  <p className="text-2xl font-semibold tabular-nums">
                    {boletim.frequencia.percentual_presenca}%
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notas por disciplina</CardTitle>
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
                        <h3 className="font-medium">{d.disciplina.nome}</h3>
                        <span className="text-sm">
                          <span className="text-muted-foreground">
                            Média ponderada:
                          </span>{" "}
                          <strong className="tabular-nums">
                            {d.media_ponderada}
                          </strong>
                        </span>
                      </div>
                      <div className="rounded-md border">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Tarefa</TableHead>
                              <TableHead className="text-right">Nota</TableHead>
                              <TableHead className="text-right">
                                Máxima
                              </TableHead>
                              <TableHead className="text-right">Peso</TableHead>
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
              <CardTitle>Ocorrências</CardTitle>
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
      <p className="text-muted-foreground text-xs uppercase">{label}</p>
      <p className="text-2xl font-semibold tabular-nums">{valor}</p>
    </div>
  );
}
