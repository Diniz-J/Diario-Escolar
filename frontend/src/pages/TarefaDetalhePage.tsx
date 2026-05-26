import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlunos } from "@/features/alunos/hooks";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { TarefaDeleteDialog } from "@/features/tarefas/TarefaDeleteDialog";
import { TarefaFormDialog } from "@/features/tarefas/TarefaFormDialog";
import {
  STATUS_BADGE,
  STATUS_LABEL,
  STATUS_ORDEM,
} from "@/features/tarefas/constants";
import {
  useEntregasDaTarefa,
  useTarefa,
  useUpdateEntrega,
} from "@/features/tarefas/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { cn } from "@/lib/utils";

export function TarefaDetalhePage() {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = params.id ? parseInt(params.id, 10) : undefined;

  const tarefaQuery = useTarefa(id);
  const entregasQuery = useEntregasDaTarefa(id);
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();
  const alunosQuery = useAlunos();
  const updateEntrega = useUpdateEntrega();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteAlvo, setDeleteAlvo] = useState(false);

  const tarefa = tarefaQuery.data;
  const turma = tarefa
    ? turmasQuery.data?.find((t) => t.id === tarefa.turma)
    : undefined;
  const disciplina = tarefa
    ? disciplinasQuery.data?.find((d) => d.id === tarefa.disciplina)
    : undefined;

  const alunosPorId = useMemo(() => {
    const map = new Map<
      number,
      { nome_completo: string; matricula: string }
    >();
    alunosQuery.data?.forEach((a) =>
      map.set(a.id, { nome_completo: a.nome_completo, matricula: a.matricula }),
    );
    return map;
  }, [alunosQuery.data]);

  // Ordena entregas por prioridade de status (atrasadas/pendentes em
  // cima) e depois alfabeticamente.
  const entregasOrdenadas = useMemo(() => {
    if (!entregasQuery.data) return [];
    return [...entregasQuery.data].sort((a, b) => {
      const diff = STATUS_ORDEM[a.status] - STATUS_ORDEM[b.status];
      if (diff !== 0) return diff;
      const nomeA = alunosPorId.get(a.aluno)?.nome_completo ?? "";
      const nomeB = alunosPorId.get(b.aluno)?.nome_completo ?? "";
      return nomeA.localeCompare(nomeB);
    });
  }, [entregasQuery.data, alunosPorId]);

  // Resumo: contagem por status.
  const resumo = useMemo(() => {
    const r = { pendente: 0, atrasada: 0, entregue_no_prazo: 0, entregue_com_atraso: 0 };
    entregasQuery.data?.forEach((e) => {
      r[e.status]++;
    });
    return r;
  }, [entregasQuery.data]);

  function toggleEntregue(entregaId: number, atual: boolean) {
    updateEntrega.mutate({
      id: entregaId,
      patch: { entregue: !atual },
    });
  }

  function setNota(entregaId: number, valor: string) {
    updateEntrega.mutate({
      id: entregaId,
      patch: { nota: valor || null },
    });
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="space-y-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/tarefas">← Voltar</Link>
        </Button>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-semibold">
              {tarefa?.titulo ?? "Tarefa"}
            </h1>
            {tarefa && (
              <p className="text-sm text-muted-foreground mt-1">
                {turma?.nome ?? `Turma #${tarefa.turma}`} ·{" "}
                {disciplina?.nome ?? `Disciplina #${tarefa.disciplina}`}
              </p>
            )}
          </div>
          {tarefa && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon">
                  ⋯
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setEditOpen(true)}>
                  Editar
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => setDeleteAlvo(true)}
                  className="text-destructive focus:text-destructive"
                >
                  Excluir
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </header>

      {tarefaQuery.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-32 w-full" />
          </CardContent>
        </Card>
      ) : tarefaQuery.isError || !tarefa ? (
        <Card>
          <CardContent className="pt-6 text-destructive">
            Tarefa não encontrada.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Informações</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Lançamento</dt>
                <dd>
                  {new Date(
                    tarefa.data_lancamento + "T00:00:00",
                  ).toLocaleDateString("pt-BR")}
                </dd>

                <dt className="text-muted-foreground">Prazo</dt>
                <dd>
                  {tarefa.prazo
                    ? new Date(tarefa.prazo + "T00:00:00").toLocaleDateString(
                        "pt-BR",
                      )
                    : "Sem prazo"}
                </dd>

                <dt className="text-muted-foreground">Vale nota</dt>
                <dd>
                  {tarefa.vale_nota
                    ? `Sim — máxima ${tarefa.nota_maxima ?? "—"}, peso ${tarefa.peso}`
                    : "Não"}
                </dd>

                {tarefa.descricao && (
                  <>
                    <dt className="text-muted-foreground">Descrição</dt>
                    <dd className="whitespace-pre-wrap">{tarefa.descricao}</dd>
                  </>
                )}
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Resumo</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-6 text-sm">
                <div className="space-y-1">
                  <p className="text-muted-foreground text-xs uppercase">
                    Pendentes
                  </p>
                  <p className="text-2xl font-semibold tabular-nums">
                    {resumo.pendente}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-muted-foreground text-xs uppercase">
                    Atrasadas
                  </p>
                  <p className="text-2xl font-semibold tabular-nums">
                    {resumo.atrasada}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-muted-foreground text-xs uppercase">
                    Entregues
                  </p>
                  <p className="text-2xl font-semibold tabular-nums">
                    {resumo.entregue_no_prazo + resumo.entregue_com_atraso}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Entregas</CardTitle>
            </CardHeader>
            <CardContent>
              {entregasQuery.isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : entregasOrdenadas.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  Nenhuma entrega registrada.
                </p>
              ) : (
                <ul className="divide-y">
                  {entregasOrdenadas.map((entrega) => {
                    const alunoInfo = alunosPorId.get(entrega.aluno);
                    return (
                      <li
                        key={entrega.id}
                        className="flex items-center justify-between gap-4 py-3"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-medium truncate">
                            {alunoInfo?.nome_completo ?? `Aluno #${entrega.aluno}`}
                          </p>
                          {alunoInfo?.matricula && (
                            <p className="text-xs text-muted-foreground font-mono">
                              {alunoInfo.matricula}
                            </p>
                          )}
                        </div>

                        <div className="flex items-center gap-3 shrink-0">
                          <span
                            className={cn(
                              "text-xs px-2 py-0.5 rounded",
                              STATUS_BADGE[entrega.status],
                            )}
                          >
                            {STATUS_LABEL[entrega.status]}
                          </span>

                          {tarefa.vale_nota && entrega.entregue && (
                            <Input
                              type="number"
                              step="0.01"
                              min="0"
                              max={tarefa.nota_maxima ?? undefined}
                              placeholder="Nota"
                              defaultValue={entrega.nota ?? ""}
                              onBlur={(e) =>
                                e.target.value !== (entrega.nota ?? "")
                                  ? setNota(entrega.id, e.target.value)
                                  : null
                              }
                              className="w-24"
                            />
                          )}

                          <Button
                            variant={entrega.entregue ? "default" : "outline"}
                            size="sm"
                            onClick={() =>
                              toggleEntregue(entrega.id, entrega.entregue)
                            }
                          >
                            {entrega.entregue ? "Entregue" : "Marcar entrega"}
                          </Button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>

          <TarefaFormDialog
            open={editOpen}
            onOpenChange={setEditOpen}
            tarefa={tarefa}
          />
          <TarefaDeleteDialog
            tarefa={deleteAlvo ? tarefa : null}
            onOpenChange={(open) => !open && setDeleteAlvo(false)}
            onDeleted={() => navigate("/tarefas")}
          />
        </>
      )}
    </div>
  );
}
