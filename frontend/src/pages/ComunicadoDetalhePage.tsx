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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { ComunicadoDeleteDialog } from "@/features/comunicados/ComunicadoDeleteDialog";
import { ComunicadoFormDialog } from "@/features/comunicados/ComunicadoFormDialog";
import { EnviarComunicadoDialog } from "@/features/comunicados/EnviarComunicadoDialog";
import {
  DEST_STATUS_BADGE,
  DEST_STATUS_LABEL,
  STATUS_BADGE,
  STATUS_LABEL,
} from "@/features/comunicados/constants";
import {
  useComunicado,
  useComunicadoDestinatarios,
} from "@/features/comunicados/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { ComunicadoDestinatarioStatus } from "@/types/api";

const FILTRO_TODOS = "__all__";

const DEST_STATUS_OPTIONS: {
  value: ComunicadoDestinatarioStatus;
  label: string;
}[] = [
  { value: "enviado", label: "Enviados" },
  { value: "falhou", label: "Falhas" },
  { value: "sem_email", label: "Sem email" },
  { value: "pendente", label: "Pendentes" },
];

function formatarDataHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ComunicadoDetalhePage() {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = params.id ? parseInt(params.id, 10) : undefined;

  const { podeModificarCadastros } = usePermissoes();
  const comunicadoQuery = useComunicado(id);
  const turmasQuery = useTurmas();

  const [editOpen, setEditOpen] = useState(false);
  const [enviarOpen, setEnviarOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [filtroDest, setFiltroDest] = useState<string>(FILTRO_TODOS);

  const comunicado = comunicadoQuery.data;
  // Rascunho não tem log — as linhas nascem no disparo. Evita uma
  // requisição que só voltaria vazia.
  const temLog = comunicado != null && comunicado.status !== "rascunho";

  const destinatariosQuery = useComunicadoDestinatarios(
    id,
    filtroDest !== FILTRO_TODOS
      ? { status: filtroDest as ComunicadoDestinatarioStatus }
      : {},
    { enabled: temLog },
  );

  const turmasDoComunicado = useMemo(() => {
    if (!comunicado || comunicado.destino !== "turmas") return [];
    return (turmasQuery.data ?? []).filter((t) =>
      comunicado.turmas.includes(t.id),
    );
  }, [comunicado, turmasQuery.data]);

  if (comunicadoQuery.isLoading) {
    return (
      <div className="p-4 md:p-8 space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (comunicadoQuery.isError || !comunicado) {
    return (
      <div className="p-4 md:p-8 space-y-4">
        <p className="text-sm text-destructive">
          Não foi possível carregar este comunicado.
        </p>
        <Link to="/comunicados" className="text-sm underline">
          Voltar para comunicados
        </Link>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-3">
          <Link
            to="/comunicados"
            className="text-[11px] uppercase tracking-[0.18em] text-sepia hover:underline"
          >
            ← Comunicados
          </Link>
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            {comunicado.titulo}
          </h1>
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[comunicado.status]}`}
            >
              {STATUS_LABEL[comunicado.status]}
            </span>
            <span className="text-sm text-muted-foreground">
              {comunicado.destino_display}
            </span>
          </div>
        </div>

        {podeModificarCadastros && comunicado.editavel && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setEditOpen(true)}>
              Editar
            </Button>
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(true)}
              className="text-destructive hover:text-destructive"
            >
              Excluir
            </Button>
            <Button onClick={() => setEnviarOpen(true)}>Enviar</Button>
          </div>
        )}
      </header>

      <ComunicadoFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        comunicado={comunicado}
      />
      <EnviarComunicadoDialog
        comunicado={enviarOpen ? comunicado : null}
        onOpenChange={(aberto) => !aberto && setEnviarOpen(false)}
      />
      <ComunicadoDeleteDialog
        comunicado={deleteOpen ? comunicado : null}
        onOpenChange={(aberto) => !aberto && setDeleteOpen(false)}
        onDeleted={() => navigate("/comunicados")}
      />

      <Card>
        <CardHeader>
          <CardTitle className="font-heading tracking-tight">
            Mensagem
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* `whitespace-pre-wrap` preserva os parágrafos digitados — é
              assim que o responsável lê no email. */}
          <p className="text-sm whitespace-pre-wrap leading-relaxed">
            {comunicado.mensagem}
          </p>

          {comunicado.destino === "turmas" && (
            <div className="space-y-1">
              <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Turmas
              </div>
              <p className="text-sm">
                {turmasDoComunicado.length > 0
                  ? turmasDoComunicado.map((t) => t.nome).join(", ")
                  : "—"}
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2 border-t border-border">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Criado por
              </div>
              <p className="text-sm">{comunicado.criado_por_nome ?? "—"}</p>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Enviado por
              </div>
              <p className="text-sm">{comunicado.enviado_por_nome ?? "—"}</p>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Enviado em
              </div>
              <p className="text-sm">
                {formatarDataHora(comunicado.enviado_em)}
              </p>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Criado em
              </div>
              <p className="text-sm">
                {formatarDataHora(comunicado.criado_em)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {comunicado.status === "rascunho" ? (
        <Card>
          <CardContent className="py-6">
            <p className="text-sm text-muted-foreground">
              Este comunicado ainda é um rascunho — nenhum email foi
              enviado.
              {podeModificarCadastros
                ? ' Use o botão "Enviar" para disparar aos responsáveis.'
                : ""}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <CardTitle className="font-heading tracking-tight">
              Log de entrega
            </CardTitle>
            <Select value={filtroDest} onValueChange={setFiltroDest}>
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={FILTRO_TODOS}>Todos</SelectItem>
                {DEST_STATUS_OPTIONS.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-6">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                  Enviados
                </div>
                <p className="text-2xl font-heading text-olive">
                  {comunicado.total_enviados}
                </p>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                  Falhas
                </div>
                <p
                  className={`text-2xl font-heading ${comunicado.total_falhas > 0 ? "text-destructive" : ""}`}
                >
                  {comunicado.total_falhas}
                </p>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                  Sem email
                </div>
                <p className="text-2xl font-heading text-muted-foreground">
                  {comunicado.total_sem_email}
                </p>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                  Alunos alcançados
                </div>
                <p className="text-2xl font-heading">
                  {comunicado.total_destinatarios}
                </p>
              </div>
            </div>

            {comunicado.total_sem_email > 0 && (
              <p className="text-sm text-destructive">
                {comunicado.total_sem_email}{" "}
                {comunicado.total_sem_email === 1 ? "aluno" : "alunos"} sem
                email de responsável no cadastro — esses responsáveis não
                receberam o comunicado.
              </p>
            )}

            {destinatariosQuery.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : destinatariosQuery.isError ? (
              <p className="text-sm text-destructive">
                Não foi possível carregar o log de entrega.
              </p>
            ) : (destinatariosQuery.data?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nenhum destinatário neste filtro.
              </p>
            ) : (
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Aluno</TableHead>
                      <TableHead>Turma</TableHead>
                      <TableHead>Responsável</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {destinatariosQuery.data?.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="font-medium">
                          {d.aluno_nome}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {d.turma_nome ?? "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {d.nome_responsavel || "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {d.email || "—"}
                        </TableCell>
                        <TableCell>
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${DEST_STATUS_BADGE[d.status]}`}
                          >
                            {DEST_STATUS_LABEL[d.status]}
                          </span>
                          {/* O erro do provedor é o que diferencia
                              "email inválido" de "cota estourada". */}
                          {d.erro && (
                            <span
                              className="block text-xs text-destructive mt-1"
                              title={d.erro}
                            >
                              {d.erro}
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
