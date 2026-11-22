import { useMemo, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { GradeTabs } from "@/features/grade/GradeTabs";
import { TempoAulaFormDialog } from "@/features/grade/TempoAulaFormDialog";
import { TURNOS, horaCurta } from "@/features/grade/constants";
import {
  useDeleteTempoAula,
  useTemposAula,
  useUpdateTempoAula,
} from "@/features/grade/hooks";
import type { TempoAula, Turno } from "@/types/api";

const EYEBROW = "text-[11px] uppercase tracking-[0.18em] text-sepia";
const FILTRO_TODOS = "__all__";

// Catálogo de horários da escola, por turno. É o que torna a duração do
// tempo configurável por cliente: uma escola de 50 minutos e outra de 45
// cadastram o que usam, e nada disso está no código.
export function TemposAulaPage() {
  const { podeModificarCadastros: ehDirecao } = usePermissoes();
  const updateMutation = useUpdateTempoAula();
  const deleteMutation = useDeleteTempoAula();

  const [filtroTurno, setFiltroTurno] = useState<string>(FILTRO_TODOS);
  const [mostrarInativos, setMostrarInativos] = useState(false);
  const [formAberto, setFormAberto] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [editando, setEditando] = useState<TempoAula | null>(null);

  const temposQuery = useTemposAula({
    ativo: !mostrarInativos,
    ...(filtroTurno !== FILTRO_TODOS && { turno: filtroTurno as Turno }),
  });

  const tempos = useMemo(
    () =>
      [...(temposQuery.data ?? [])].sort(
        (a, b) => a.turno.localeCompare(b.turno) || a.ordem - b.ordem,
      ),
    [temposQuery.data],
  );

  function abrirNovo() {
    setEditando(null);
    setFormKey((k) => k + 1);
    setFormAberto(true);
  }

  function abrirEdicao(tempo: TempoAula) {
    setEditando(tempo);
    setFormKey((k) => k + 1);
    setFormAberto(true);
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Tempos de aula
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground max-w-xl">
            Os horários de cada turno. A grade das turmas e a chamada por
            tempo saem daqui.
          </p>
        </div>
        {ehDirecao && (
          <Button type="button" onClick={abrirNovo}>
            Novo tempo
          </Button>
        )}
      </header>

      <GradeTabs />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="space-y-2">
          <Label className={EYEBROW}>Turno</Label>
          <Select value={filtroTurno} onValueChange={setFiltroTurno}>
            <SelectTrigger className="w-full sm:w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={FILTRO_TODOS}>Todos</SelectItem>
              {TURNOS.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <Switch
            id="inativos"
            checked={mostrarInativos}
            onCheckedChange={setMostrarInativos}
          />
          <Label htmlFor="inativos" className="cursor-pointer text-sm">
            Mostrar inativos
          </Label>
        </div>
      </div>

      {/* Erro antes de vazio: o `isLoading` volta a false quando a query
          falha, e o ramo de lista vazia diria "nenhum tempo cadastrado"
          pra uma falha de rede — a escola concluiria que precisa cadastrar
          tudo de novo. */}
      {temposQuery.isError && (
        <Alert variant="destructive">
          <AlertDescription>
            Não foi possível carregar os tempos de aula. Tente novamente.
          </AlertDescription>
        </Alert>
      )}

      {!temposQuery.isError && temposQuery.isLoading && (
        <Skeleton className="h-48 w-full" />
      )}

      {!temposQuery.isError && !temposQuery.isLoading && (
        <div className="rounded-lg border border-border bg-paper overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className={`${EYEBROW} font-normal`}>
                  Ordem
                </TableHead>
                <TableHead className={`${EYEBROW} font-normal`}>
                  Turno
                </TableHead>
                <TableHead className={`${EYEBROW} font-normal`}>
                  Horário
                </TableHead>
                {ehDirecao && <TableHead className="w-10" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {tempos.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={ehDirecao ? 4 : 3}
                    className="text-sm text-muted-foreground"
                  >
                    {mostrarInativos
                      ? "Nenhum tempo inativo."
                      : "Nenhum tempo cadastrado ainda."}
                  </TableCell>
                </TableRow>
              )}
              {tempos.map((tempo) => (
                <TableRow key={tempo.id}>
                  <TableCell className="text-tinta">
                    {tempo.ordem}º
                    {!tempo.ativo && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        [ inativo ]
                      </span>
                    )}
                  </TableCell>
                  <TableCell>{tempo.turno_display}</TableCell>
                  <TableCell>
                    {horaCurta(tempo.hora_inicio)} às{" "}
                    {horaCurta(tempo.hora_fim)}
                  </TableCell>
                  {ehDirecao && (
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm" aria-label="Ações">
                            ⋯
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => abrirEdicao(tempo)}>
                            Editar
                          </DropdownMenuItem>
                          {tempo.ativo ? (
                            <DropdownMenuItem
                              onClick={() => deleteMutation.mutate(tempo.id)}
                            >
                              Desativar
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem
                              onClick={() =>
                                updateMutation.mutate({
                                  id: tempo.id,
                                  patch: { ativo: true },
                                })
                              }
                            >
                              Reativar
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <TempoAulaFormDialog
        key={formKey}
        open={formAberto}
        onOpenChange={setFormAberto}
        tempo={editando}
        turnoInicial={
          filtroTurno !== FILTRO_TODOS ? (filtroTurno as Turno) : ""
        }
      />
    </div>
  );
}
