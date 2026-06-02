import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AlunoDeleteDialog } from "@/features/alunos/AlunoDeleteDialog";
import { AlunoFormDialog } from "@/features/alunos/AlunoFormDialog";
import { useAlunos, useUpdateAluno } from "@/features/alunos/hooks";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useTurmas } from "@/features/turmas/hooks";
import type { Aluno } from "@/types/api";

export function AlunosPage() {
  const navigate = useNavigate();
  const [mostrarInativos, setMostrarInativos] = useState(false);
  // Padrão: lista só ativos. Toggle "Mostrar inativos" inverte e o
  // backend devolve só os com `ativo=false` — soft delete deixa de
  // poluir a listagem do dia a dia, mas permanece acessível pra
  // pesquisar histórico ou reativar um aluno.
  const alunosQuery = useAlunos({ ativo: !mostrarInativos });
  const turmasQuery = useTurmas();
  const updateMutation = useUpdateAluno();
  const { podeModificarCadastros } = usePermissoes();
  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  // Aluno em edição: null fecha o dialog; objeto abre em modo edição.
  const [editando, setEditando] = useState<Aluno | null>(null);
  const [excluindo, setExcluindo] = useState<Aluno | null>(null);

  const turmasPorId = useMemo(() => {
    const map = new Map<number, string>();
    turmasQuery.data?.forEach((t) => map.set(t.id, t.nome));
    return map;
  }, [turmasQuery.data]);

  const alunosFiltrados = useMemo(() => {
    if (!alunosQuery.data) return [];
    const q = busca.trim().toLowerCase();
    if (!q) return alunosQuery.data;
    return alunosQuery.data.filter(
      (a) =>
        a.nome_completo.toLowerCase().includes(q) ||
        a.matricula.toLowerCase().includes(q),
    );
  }, [alunosQuery.data, busca]);

  // Unifica criação e edição no mesmo dialog: `editando=null` + `formOpen`
  // = modo criar; `editando=aluno` = modo editar.
  const dialogAberto = formOpen || editando !== null;
  function fecharDialog(open: boolean) {
    if (!open) {
      setFormOpen(false);
      setEditando(null);
    }
  }

  // PATCH `ativo: true` num aluno desativado. Usa o mesmo serializer da
  // edição (DRF não exige campos `required` ausentes em PATCH parcial).
  function reativar(aluno: Aluno) {
    updateMutation.mutate({ id: aluno.id, patch: { ativo: true } });
  }

  // Mensagem do estado vazio considera os 3 cenários: busca sem hit,
  // toggle de inativos sem ninguém pra mostrar, e cadastro zerado.
  function mensagemVazia(): string {
    if (busca) return "Nenhum aluno encontrado para essa busca.";
    if (mostrarInativos) return "Nenhum aluno inativo.";
    return "Nenhum aluno cadastrado.";
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Alunos
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
        </div>
        {podeModificarCadastros && (
          <Button onClick={() => setFormOpen(true)}>Novo aluno</Button>
        )}
      </header>

      <AlunoFormDialog
        open={dialogAberto}
        onOpenChange={fecharDialog}
        aluno={editando}
      />
      <AlunoDeleteDialog
        aluno={excluindo}
        onOpenChange={(open) => !open && setExcluindo(null)}
      />

      <div className="flex flex-wrap items-center gap-4">
        <Input
          placeholder="Buscar por nome ou matrícula..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-sm"
        />
        <div className="flex items-center gap-2">
          <Switch
            id="mostrar-inativos"
            checked={mostrarInativos}
            onCheckedChange={setMostrarInativos}
          />
          <Label
            htmlFor="mostrar-inativos"
            className="text-[11px] uppercase tracking-[0.18em] text-sepia cursor-pointer select-none"
          >
            Mostrar inativos
          </Label>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-paper overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              {/* Em mobile mostramos só Nome + Turma + ⋯; o resto fica
                  no boletim (linha clicável). Matrícula volta em sm,
                  Status em md.
                  Headers em eyebrow mono — padrão do DESIGN.md §7.1. */}
              <TableHead className="hidden sm:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Matrícula
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Nome completo
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Turma
              </TableHead>
              <TableHead className="hidden md:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Status
              </TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {alunosQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-48" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell></TableCell>
                </TableRow>
              ))
            ) : alunosQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar alunos.
                </TableCell>
              </TableRow>
            ) : alunosFiltrados.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="text-center text-muted-foreground py-8"
                >
                  {mensagemVazia()}
                </TableCell>
              </TableRow>
            ) : (
              alunosFiltrados.map((aluno) => (
                <TableRow
                  key={aluno.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/boletim/${aluno.id}`)}
                >
                  <TableCell className="hidden sm:table-cell font-mono text-xs">
                    {aluno.matricula}
                  </TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-2">
                      {aluno.nome_completo}
                      {/* Reforço visual em mobile, onde a coluna Status
                          some. Mesmo no md+ é útil pra varredura rápida
                          ao olhar o nome diretamente. */}
                      {!aluno.ativo && (
                        <span className="text-[10px] uppercase tracking-wide bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                          inativo
                        </span>
                      )}
                    </span>
                  </TableCell>
                  <TableCell>
                    {turmasPorId.get(aluno.turma) ?? "—"}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {aluno.ativo ? (
                      <span className="text-[10px] uppercase tracking-wide text-olive bg-olive/10 px-1.5 py-0.5 rounded">
                        Ativo
                      </span>
                    ) : (
                      <span className="text-[10px] uppercase tracking-wide text-sepia">
                        Inativo
                      </span>
                    )}
                  </TableCell>
                  <TableCell
                    // Bloqueia bubble-up: clicar no menu de ações não
                    // dispara a navegação pro boletim.
                    onClick={(e) => e.stopPropagation()}
                  >
                    {podeModificarCadastros && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon-sm">
                            ⋯
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => setEditando(aluno)}>
                            Editar
                          </DropdownMenuItem>
                          {aluno.ativo ? (
                            <DropdownMenuItem
                              onClick={() => setExcluindo(aluno)}
                              className="text-destructive focus:text-destructive"
                            >
                              Excluir
                            </DropdownMenuItem>
                          ) : (
                            // Aluno inativo: oferece reativar em vez de
                            // excluir. Mesmo endpoint da edição (PATCH).
                            <DropdownMenuItem
                              onClick={() => reativar(aluno)}
                              disabled={updateMutation.isPending}
                            >
                              Reativar
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
