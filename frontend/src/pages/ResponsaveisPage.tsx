import { useEffect, useState } from "react";

import { Pagination } from "@/components/Pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { ConvidarDialog } from "@/features/responsaveis/ConvidarDialog";
import {
  PODE_CONVIDAR,
  SITUACAO_BADGE,
  SITUACAO_OPTIONS,
} from "@/features/responsaveis/constants";
import { useResponsaveisPaginated } from "@/features/responsaveis/hooks";
import type { ResponsavelSituacao, ResponsavelStaff } from "@/types/api";

const FILTRO_TODOS = "__all__";
const PAGE_SIZE = 20;

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

export function ResponsaveisPage() {
  const [filtroSituacao, setFiltroSituacao] = useState<string>(FILTRO_TODOS);
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [page, setPage] = useState(1);
  const [convidarAlvo, setConvidarAlvo] = useState<ResponsavelStaff | null>(
    null,
  );

  // A busca é server-side (inclui nome de aluno, que não está na linha), e
  // sai com atraso pra não disparar uma request por tecla.
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 350);
    return () => clearTimeout(t);
  }, [busca]);

  // Filtro server-side mudou: a página atual pode não existir no novo subset.
  useEffect(() => {
    setPage(1);
  }, [filtroSituacao, buscaAplicada]);

  const query = useResponsaveisPaginated(
    {
      ...(filtroSituacao !== FILTRO_TODOS
        ? { situacao: filtroSituacao as ResponsavelSituacao }
        : {}),
      ...(buscaAplicada ? { search: buscaAplicada } : {}),
    },
    { page, page_size: PAGE_SIZE },
  );

  const linhas = query.data?.results ?? [];
  const totalCount = query.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="space-y-3">
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          Responsáveis
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
        <p className="text-sm text-muted-foreground max-w-xl">
          Contas de acesso ao portal. O cadastro vem do campo de responsável
          do aluno; aqui você vê o estado do acesso e envia o convite.
        </p>
      </header>

      <ConvidarDialog
        responsavel={convidarAlvo}
        onOpenChange={(aberto) => !aberto && setConvidarAlvo(null)}
      />

      <div className="flex flex-wrap gap-3 items-end">
        <Input
          placeholder="Buscar por responsável, email ou aluno..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-xs"
        />
        <Select value={filtroSituacao} onValueChange={setFiltroSituacao}>
          <SelectTrigger className="w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={FILTRO_TODOS}>Todas as situações</SelectItem>
            {SITUACAO_OPTIONS.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {query.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : query.isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar os responsáveis.
        </p>
      ) : linhas.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {buscaAplicada || filtroSituacao !== FILTRO_TODOS
            ? "Nenhum responsável neste filtro."
            : "Nenhum responsável cadastrado. Rode o comando de semeadura para criar as contas a partir do cadastro dos alunos."}
        </p>
      ) : (
        <>
          <div className="rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Responsável</TableHead>
                  <TableHead className="hidden md:table-cell">Alunos</TableHead>
                  <TableHead>Situação</TableHead>
                  <TableHead className="hidden lg:table-cell">
                    Último acesso
                  </TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {linhas.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <span className="font-medium block">
                        {r.nome || "(sem nome)"}
                      </span>
                      <span className="text-sm text-muted-foreground break-all">
                        {r.email}
                      </span>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                      {r.alunos.length === 0
                        ? "—"
                        : r.alunos.map((a) => (
                            <span key={a.id} className="block">
                              {a.nome_completo}
                              {a.turma ? ` · ${a.turma}` : ""}
                              {!a.ativo ? " [ inativo ]" : ""}
                            </span>
                          ))}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${SITUACAO_BADGE[r.situacao]}`}
                      >
                        {r.situacao_display}
                      </span>
                      {r.situacao === "convidado" && r.convite_expira_em && (
                        <span className="block text-xs text-muted-foreground mt-1">
                          expira {formatarDataHora(r.convite_expira_em)}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                      {formatarDataHora(r.ultimo_acesso)}
                    </TableCell>
                    <TableCell className="text-right">
                      {PODE_CONVIDAR.includes(r.situacao) && (
                        <Button
                          size="sm"
                          variant={
                            r.situacao === "convidado" ? "outline" : "default"
                          }
                          onClick={() => setConvidarAlvo(r)}
                        >
                          {r.situacao === "convidado" ? "Reenviar" : "Convidar"}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalLabel={`${totalCount} ${totalCount === 1 ? "responsável" : "responsáveis"} no total`}
          />
        </>
      )}
    </div>
  );
}
