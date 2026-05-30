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
import { useAlunos } from "@/features/alunos/hooks";
import { useTurma } from "@/features/turmas/hooks";

// Página /turmas/:id — detalhe + alunos vinculados.
//
// Faz duas queries em paralelo: a turma (pra cabeçalho) e os alunos
// filtrados por turma (backend já suporta ?turma=X via DjangoFilterBackend).
export function TurmaDetalhePage() {
  const params = useParams<{ id: string }>();
  const turmaId = params.id ? parseInt(params.id, 10) : undefined;

  const turmaQuery = useTurma(turmaId);
  // Lista só alunos ativos da turma — alunos inativos (soft delete)
  // ficam disponíveis pra pesquisa de histórico na página de Alunos
  // via toggle "Mostrar inativos", não aqui.
  const alunosQuery = useAlunos({ turma: turmaId, ativo: true });

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="space-y-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/turmas">← Voltar</Link>
        </Button>
        <h1 className="text-2xl md:text-3xl font-semibold">
          {turmaQuery.isLoading ? (
            <Skeleton className="h-8 w-64" />
          ) : turmaQuery.data ? (
            turmaQuery.data.nome
          ) : (
            "Turma não encontrada"
          )}
        </h1>
      </header>

      {turmaQuery.data && (
        <Card>
          <CardHeader>
            <CardTitle>Informações</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Turno</dt>
              <dd>{turmaQuery.data.turno_display}</dd>
              <dt className="text-muted-foreground">Ano letivo</dt>
              <dd>{turmaQuery.data.ano_letivo}</dd>
              <dt className="text-muted-foreground">Status</dt>
              <dd>{turmaQuery.data.ativa ? "Ativa" : "Inativa"}</dd>
            </dl>
          </CardContent>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Alunos</h2>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Matrícula</TableHead>
                <TableHead>Nome completo</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {alunosQuery.isLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-48" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                  </TableRow>
                ))
              ) : alunosQuery.isError ? (
                <TableRow>
                  <TableCell
                    colSpan={3}
                    className="text-center text-destructive py-8"
                  >
                    Erro ao carregar alunos.
                  </TableCell>
                </TableRow>
              ) : !alunosQuery.data || alunosQuery.data.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={3}
                    className="text-center text-muted-foreground py-8"
                  >
                    Nenhum aluno nesta turma.
                  </TableCell>
                </TableRow>
              ) : (
                alunosQuery.data.map((aluno) => (
                  <TableRow key={aluno.id}>
                    <TableCell className="font-mono text-xs">
                      {aluno.matricula}
                    </TableCell>
                    <TableCell>{aluno.nome_completo}</TableCell>
                    <TableCell>
                      {aluno.ativo ? (
                        <span className="text-xs text-green-700 bg-green-50 dark:bg-green-950 dark:text-green-300 px-2 py-0.5 rounded">
                          Ativo
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          Inativo
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}
