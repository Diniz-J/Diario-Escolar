import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { ComunicadoFormDialog } from "@/features/comunicados/ComunicadoFormDialog";
import { EnviarComunicadoDialog } from "@/features/comunicados/EnviarComunicadoDialog";
import {
  STATUS_BADGE,
  STATUS_LABEL,
  STATUS_ORDEM,
  STATUS_OPTIONS,
} from "@/features/comunicados/constants";
import { useComunicadosPaginated } from "@/features/comunicados/hooks";
import type { Comunicado, ComunicadoStatus } from "@/types/api";

const FILTRO_TODOS = "__all__";
const PAGE_SIZE = 20;

function formatarDataHora(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ComunicadosPage() {
  const navigate = useNavigate();
  // Professor/inspetor acompanham os comunicados, mas não publicam nem
  // disparam — espelha a permissão do backend (ReadWritePermissionMixin).
  const { podeModificarCadastros } = usePermissoes();

  const [filtroStatus, setFiltroStatus] = useState<string>(FILTRO_TODOS);
  const [busca, setBusca] = useState("");
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [enviarAlvo, setEnviarAlvo] = useState<Comunicado | null>(null);

  // Reseta pra página 1 quando o filtro server-side muda — senão pode
  // cair numa página que não existe no novo subset.
  useEffect(() => {
    setPage(1);
  }, [filtroStatus]);

  const comunicadosQuery = useComunicadosPaginated(
    filtroStatus !== FILTRO_TODOS
      ? { status: filtroStatus as ComunicadoStatus }
      : {},
    { page, page_size: PAGE_SIZE },
  );

  // Rascunho primeiro (pede ação), falha depois (pede atenção), enviados
  // por último. Dentro do mesmo status, mais recente primeiro.
  const ordenados = useMemo(() => {
    const resultados = comunicadosQuery.data?.results ?? [];
    return [...resultados].sort((a, b) => {
      const diff = STATUS_ORDEM[a.status] - STATUS_ORDEM[b.status];
      if (diff !== 0) return diff;
      return b.criado_em.localeCompare(a.criado_em);
    });
  }, [comunicadosQuery.data]);

  // Busca por título é client-side (sobre a página atual), igual ao
  // padrão da página de ocorrências.
  const filtrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return ordenados;
    return ordenados.filter((c) => c.titulo.toLowerCase().includes(q));
  }, [ordenados, busca]);

  const totalCount = comunicadosQuery.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Comunicados
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground max-w-xl">
            Avisos enviados por email aos responsáveis. Salvar cria um
            rascunho; o email só sai quando você confirma o envio.
          </p>
        </div>
        {podeModificarCadastros && (
          <Button onClick={() => setFormOpen(true)}>Novo comunicado</Button>
        )}
      </header>

      <ComunicadoFormDialog open={formOpen} onOpenChange={setFormOpen} />
      <EnviarComunicadoDialog
        comunicado={enviarAlvo}
        onOpenChange={(aberto) => !aberto && setEnviarAlvo(null)}
      />

      <div className="flex flex-wrap gap-3 items-end">
        <Input
          placeholder="Buscar por título..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-xs"
        />
        <Select value={filtroStatus} onValueChange={setFiltroStatus}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={FILTRO_TODOS}>Todos os status</SelectItem>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {comunicadosQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : comunicadosQuery.isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar os comunicados.
        </p>
      ) : filtrados.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhum comunicado encontrado.
        </p>
      ) : (
        <>
          <div className="rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Título</TableHead>
                  <TableHead>Destinatários</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Envio</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtrados.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/comunicados/${c.id}`)}
                  >
                    <TableCell className="font-medium">{c.titulo}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {c.destino_display}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[c.status]}`}
                      >
                        {STATUS_LABEL[c.status]}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {c.status === "rascunho" ? (
                        "Não enviado"
                      ) : (
                        <>
                          {formatarDataHora(c.enviado_em)}
                          <span className="block text-xs">
                            {c.total_enviados} enviados
                            {c.total_falhas > 0 && (
                              <span className="text-destructive">
                                {" "}
                                · {c.total_falhas} falhas
                              </span>
                            )}
                          </span>
                        </>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {podeModificarCadastros && c.editavel && (
                        <Button
                          size="sm"
                          onClick={(e) => {
                            // A linha inteira navega pro detalhe; o botão
                            // de envio não pode disparar essa navegação.
                            e.stopPropagation();
                            setEnviarAlvo(c);
                          }}
                        >
                          Enviar
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
            totalLabel={`${totalCount} ${totalCount === 1 ? "comunicado" : "comunicados"} no total`}
          />
        </>
      )}
    </div>
  );
}
