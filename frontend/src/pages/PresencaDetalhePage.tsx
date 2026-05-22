import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlunos } from "@/features/alunos/hooks";
import { STATUS_PRESENCA } from "@/features/presenca/constants";
import {
  useDeleteRegistro,
  useItensDoRegistro,
  useRegistro,
  useUpdateItemStatus,
} from "@/features/presenca/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { cn } from "@/lib/utils";
import type { PresencaStatus } from "@/types/api";

// Tela de chamada de uma turma num dia. Lista os alunos com botões
// P/A/J/R por linha — clicar atualiza o status do item via optimistic
// update do TanStack Query (ver useUpdateItemStatus).
export function PresencaDetalhePage() {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = params.id ? parseInt(params.id, 10) : undefined;

  const registroQuery = useRegistro(id);
  const itensQuery = useItensDoRegistro(id);
  const turmasQuery = useTurmas();
  const alunosQuery = useAlunos();
  const updateStatusMutation = useUpdateItemStatus();
  const deleteMutation = useDeleteRegistro();

  const [confirmandoExclusao, setConfirmandoExclusao] = useState(false);

  const registro = registroQuery.data;
  const turma = registro
    ? turmasQuery.data?.find((t) => t.id === registro.turma)
    : undefined;

  const alunosPorId = useMemo(() => {
    const map = new Map<
      number,
      { nome_completo: string; matricula: string }
    >();
    alunosQuery.data?.forEach((a) =>
      map.set(a.id, {
        nome_completo: a.nome_completo,
        matricula: a.matricula,
      }),
    );
    return map;
  }, [alunosQuery.data]);

  // Ordena itens por nome do aluno pra UX previsível.
  const itensOrdenados = useMemo(() => {
    if (!itensQuery.data) return [];
    return [...itensQuery.data].sort((a, b) => {
      const nomeA = alunosPorId.get(a.aluno)?.nome_completo ?? "";
      const nomeB = alunosPorId.get(b.aluno)?.nome_completo ?? "";
      return nomeA.localeCompare(nomeB);
    });
  }, [itensQuery.data, alunosPorId]);

  // Resumo no topo: contagem por status.
  const resumo = useMemo(() => {
    const r: Record<PresencaStatus, number> = { P: 0, A: 0, J: 0, R: 0 };
    itensQuery.data?.forEach((i) => {
      r[i.status]++;
    });
    return r;
  }, [itensQuery.data]);

  async function handleExcluir() {
    if (!registro) return;
    try {
      await deleteMutation.mutateAsync(registro.id);
      navigate("/presenca");
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="p-8 space-y-6">
      <header className="space-y-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/presenca">← Voltar</Link>
        </Button>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold">Chamada</h1>
            {registro && (
              <p className="text-sm text-muted-foreground mt-1">
                {turma?.nome ?? `Turma #${registro.turma}`} —{" "}
                {new Date(registro.data + "T00:00:00").toLocaleDateString(
                  "pt-BR",
                )}
              </p>
            )}
          </div>
          {registro && (
            <Button
              variant="outline"
              onClick={() => setConfirmandoExclusao(true)}
              className="text-destructive hover:text-destructive"
            >
              Excluir
            </Button>
          )}
        </div>
      </header>

      {registroQuery.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-32 w-full" />
          </CardContent>
        </Card>
      ) : registroQuery.isError || !registro ? (
        <Card>
          <CardContent className="pt-6 text-destructive">
            Chamada não encontrada.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Resumo</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-6 text-sm">
                {STATUS_PRESENCA.map((s) => (
                  <div key={s.value} className="space-y-1">
                    <p className="text-muted-foreground text-xs uppercase">
                      {s.full}
                    </p>
                    <p className="text-2xl font-semibold tabular-nums">
                      {resumo[s.value]}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Alunos</CardTitle>
            </CardHeader>
            <CardContent>
              {itensQuery.isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : itensOrdenados.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  Nenhum aluno nesta chamada.
                </p>
              ) : (
                <ul className="divide-y">
                  {itensOrdenados.map((item) => {
                    const alunoInfo = alunosPorId.get(item.aluno);
                    return (
                      <li
                        key={item.id}
                        className="flex items-center justify-between gap-4 py-3"
                      >
                        <div className="min-w-0">
                          <p className="font-medium truncate">
                            {alunoInfo?.nome_completo ?? `Aluno #${item.aluno}`}
                          </p>
                          {alunoInfo?.matricula && (
                            <p className="text-xs text-muted-foreground font-mono">
                              {alunoInfo.matricula}
                            </p>
                          )}
                        </div>
                        <div className="flex gap-1 shrink-0">
                          {STATUS_PRESENCA.map((s) => {
                            const ativo = item.status === s.value;
                            return (
                              <button
                                key={s.value}
                                type="button"
                                title={s.full}
                                onClick={() =>
                                  !ativo &&
                                  updateStatusMutation.mutate({
                                    id: item.id,
                                    status: s.value,
                                  })
                                }
                                disabled={ativo}
                                className={cn(
                                  "w-9 h-9 rounded-md font-semibold text-sm transition-colors",
                                  ativo
                                    ? s.className + " ring-2 ring-foreground/40"
                                    : "bg-muted text-muted-foreground hover:bg-muted-foreground/20",
                                )}
                              >
                                {s.label}
                              </button>
                            );
                          })}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>

          <AlertDialog
            open={confirmandoExclusao}
            onOpenChange={setConfirmandoExclusao}
          >
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Excluir esta chamada?</AlertDialogTitle>
                <AlertDialogDescription>
                  Todos os registros de presença dos alunos desta chamada
                  serão removidos junto.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={deleteMutation.isPending}>
                  Cancelar
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleExcluir}
                  disabled={deleteMutation.isPending}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {deleteMutation.isPending ? "Excluindo..." : "Excluir"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      )}
    </div>
  );
}
