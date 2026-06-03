import { useState } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { useAlunos } from "@/features/alunos/hooks";
import { OcorrenciaDeleteDialog } from "@/features/ocorrencias/OcorrenciaDeleteDialog";
import { OcorrenciaFormDialog } from "@/features/ocorrencias/OcorrenciaFormDialog";
import { STATUS_BADGE, STATUS_LABEL } from "@/features/ocorrencias/constants";
import {
  useOcorrencia,
  useUpdateOcorrencia,
} from "@/features/ocorrencias/hooks";
import { useProfessores } from "@/features/professores/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { OcorrenciaStatus } from "@/types/api";

// Ações de mudança rápida de status disponíveis por estado atual.
// Foco no fluxo natural de uma ocorrência: aberta → em andamento →
// resolvida → arquivada. Reabrir / desarquivar volta pra em_andamento.
const ACOES_POR_STATUS: Record<
  OcorrenciaStatus,
  { para: OcorrenciaStatus; label: string; variant?: "default" | "outline" }[]
> = {
  aberta: [
    { para: "em_andamento", label: "Iniciar acompanhamento" },
    { para: "resolvida", label: "Resolver" },
    { para: "arquivada", label: "Arquivar", variant: "outline" },
  ],
  em_andamento: [
    { para: "resolvida", label: "Resolver" },
    { para: "arquivada", label: "Arquivar", variant: "outline" },
  ],
  resolvida: [
    { para: "em_andamento", label: "Reabrir", variant: "outline" },
    { para: "arquivada", label: "Arquivar", variant: "outline" },
  ],
  arquivada: [
    { para: "em_andamento", label: "Desarquivar", variant: "outline" },
  ],
};

export function OcorrenciaDetalhePage() {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = params.id ? parseInt(params.id, 10) : undefined;

  const ocorrenciaQuery = useOcorrencia(id);
  const alunosQuery = useAlunos();
  const turmasQuery = useTurmas();
  const professoresQuery = useProfessores();
  const updateMutation = useUpdateOcorrencia();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteAlvo, setDeleteAlvo] = useState(false);

  const ocorrencia = ocorrenciaQuery.data;
  const aluno = ocorrencia
    ? alunosQuery.data?.find((a) => a.id === ocorrencia.aluno)
    : undefined;
  const turma = ocorrencia
    ? turmasQuery.data?.find((t) => t.id === ocorrencia.turma)
    : undefined;
  const professor = ocorrencia?.professor
    ? professoresQuery.data?.find((p) => p.id === ocorrencia.professor)
    : undefined;

  function mudarStatus(novoStatus: OcorrenciaStatus) {
    if (!ocorrencia) return;
    updateMutation.mutate({
      id: ocorrencia.id,
      patch: { status: novoStatus },
    });
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="space-y-3">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/ocorrencias">← Voltar</Link>
        </Button>
        {/* Empilha título e ações até `lg` (1024px). No iPad em portrait
            (768-1024px) os 3 botões de status + dropdown não cabem na
            mesma linha do título sem ficar colados; só a partir de `lg`
            há respiro pra mostrar tudo lado a lado. */}
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between lg:gap-4">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
                Ocorrência
              </h1>
              {ocorrencia && (
                <span
                  className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[ocorrencia.status]}`}
                >
                  {STATUS_LABEL[ocorrencia.status]}
                </span>
              )}
            </div>
            <div className="h-px w-10 bg-ferrugem" />
          </div>

          {ocorrencia && (
            // `flex-wrap` cobre o pior caso (telas estreitas tipo iPhone SE):
            // se os botões + dropdown ainda não couberem na linha, o `⋯`
            // pula sozinho pra próxima — sem overflow horizontal.
            <div className="flex flex-wrap items-center gap-2">
              {ACOES_POR_STATUS[ocorrencia.status].map((acao) => (
                <Button
                  key={acao.para}
                  variant={acao.variant ?? "default"}
                  onClick={() => mudarStatus(acao.para)}
                  disabled={updateMutation.isPending}
                >
                  {acao.label}
                </Button>
              ))}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="icon">
                    ⋯
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => setEditOpen(true)}>
                    Editar detalhes
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => setDeleteAlvo(true)}
                    className="text-destructive focus:text-destructive"
                  >
                    Excluir
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
        </div>
      </header>

      {ocorrenciaQuery.isLoading ? (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-20 w-full" />
          </CardContent>
        </Card>
      ) : ocorrenciaQuery.isError || !ocorrencia ? (
        <Card>
          <CardContent className="pt-6 text-destructive">
            Ocorrência não encontrada.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Informações
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Data
                </dt>
                <dd>
                  {new Date(
                    ocorrencia.data_ocorrencia + "T00:00:00",
                  ).toLocaleDateString("pt-BR")}
                </dd>

                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Turma
                </dt>
                <dd>{turma?.nome ?? "—"}</dd>

                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Aluno
                </dt>
                <dd>
                  {aluno
                    ? `${aluno.nome_completo} (${aluno.matricula})`
                    : "—"}
                </dd>

                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Professor
                </dt>
                <dd>
                  {professor?.nome_completo ??
                    (ocorrencia.professor
                      ? `Professor #${ocorrencia.professor}`
                      : "—")}
                </dd>

                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Registrada em
                </dt>
                <dd>
                  {new Date(ocorrencia.criado_em).toLocaleString("pt-BR")}
                </dd>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Descrição
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm whitespace-pre-wrap">
                {ocorrencia.descricao}
              </p>
            </CardContent>
          </Card>

          <OcorrenciaFormDialog
            open={editOpen}
            onOpenChange={setEditOpen}
            ocorrencia={ocorrencia}
          />
          <OcorrenciaDeleteDialog
            ocorrencia={deleteAlvo ? ocorrencia : null}
            onOpenChange={(open) => !open && setDeleteAlvo(false)}
            onDeleted={() => navigate("/ocorrencias")}
          />
        </>
      )}
    </div>
  );
}
