import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import {
  useAvaliacao,
  useLancarNotas,
  useNotasDaAvaliacao,
} from "@/features/avaliacoes/hooks";
import { cn } from "@/lib/utils";
import type { LancarNotaItem, NotaAvaliacao } from "@/types/api";

// Estado local de cada linha (string pra suportar input vazio + edição
// parcial). Sincronizado com `notas` (vindas do backend) via useEffect.
interface LinhaEstado {
  nota: string; // "" significa "não lançada"
  observacao: string;
}

function formatarDataBR(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatarTimestamp(iso: string | null): string {
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

export function AvaliacaoDetalhePage() {
  const { id } = useParams<{ id: string }>();
  const avaliacaoId = id ? parseInt(id, 10) : null;
  const avaliacaoQuery = useAvaliacao(avaliacaoId);
  const notasQuery = useNotasDaAvaliacao(avaliacaoId);
  const lancarMutation = useLancarNotas(avaliacaoId ?? 0);
  const { podeModificarCadastros } = usePermissoes();

  // `linhas`: estado controlado da tabela. Sincroniza com o backend
  // sempre que `notasQuery.data` mudar (load inicial + após salvar).
  const [linhas, setLinhas] = useState<Record<number, LinhaEstado>>({});
  const [erroSubmit, setErroSubmit] = useState<string | null>(null);

  useEffect(() => {
    if (!notasQuery.data) return;
    const novo: Record<number, LinhaEstado> = {};
    for (const n of notasQuery.data) {
      novo[n.id] = {
        nota: n.nota ?? "",
        observacao: n.observacao,
      };
    }
    setLinhas(novo);
  }, [notasQuery.data]);

  const avaliacao = avaliacaoQuery.data;

  // Itens "sujos": linhas onde nota ou observação mudou em relação ao
  // backend. Só essas vão no payload — economia de banco e clareza no
  // audit log (não cria snapshot pra nota inalterada).
  const itensSujos: LancarNotaItem[] = useMemo(() => {
    if (!notasQuery.data) return [];
    const sujos: LancarNotaItem[] = [];
    for (const n of notasQuery.data) {
      const atual = linhas[n.id];
      if (!atual) continue;
      const notaBackend = n.nota ?? "";
      const obsBackend = n.observacao;
      const mudouNota = atual.nota !== notaBackend;
      const mudouObs = atual.observacao !== obsBackend;
      if (mudouNota || mudouObs) {
        sujos.push({
          aluno_id: n.aluno,
          nota: atual.nota === "" ? null : atual.nota,
          observacao: atual.observacao,
        });
      }
    }
    return sujos;
  }, [linhas, notasQuery.data]);

  async function handleSalvar() {
    if (itensSujos.length === 0) return;
    setErroSubmit(null);
    try {
      const resp = await lancarMutation.mutateAsync(itensSujos);
      if (resp.falhas.length > 0) {
        setErroSubmit(
          `${resp.falhas.length} linhas falharam. Nada foi salvo.`,
        );
      }
    } catch (err) {
      console.error(err);
      setErroSubmit("Falha ao salvar. Tente novamente.");
    }
  }

  function atualizarLinha(notaId: number, patch: Partial<LinhaEstado>) {
    setLinhas((prev) => ({
      ...prev,
      [notaId]: { ...prev[notaId], ...patch },
    }));
  }

  // Validação local de nota: aceita vazio, número >= 0 e <= nota_maxima
  // (advisory — backend não bloqueia bonus, então só sinalizamos).
  function notaInvalida(valor: string): boolean {
    if (valor === "") return false;
    const n = Number(valor.replace(",", "."));
    if (Number.isNaN(n) || n < 0) return true;
    return false;
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <div>
        <Link
          to="/avaliacoes"
          className="text-[11px] uppercase tracking-[0.18em] text-sepia hover:text-ferrugem transition-colors"
        >
          ← Avaliações
        </Link>
      </div>

      {avaliacaoQuery.isLoading || !avaliacao ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-4 w-1/3" />
        </div>
      ) : (
        <header className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            {avaliacao.titulo}
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-sepia">
            <span>
              <span className="text-[10px] uppercase tracking-wider text-sepia/60 mr-1">
                Tipo
              </span>
              {avaliacao.tipo_display}
            </span>
            <span>
              <span className="text-[10px] uppercase tracking-wider text-sepia/60 mr-1">
                Turma
              </span>
              {avaliacao.turma_nome}
            </span>
            <span>
              <span className="text-[10px] uppercase tracking-wider text-sepia/60 mr-1">
                Disciplina
              </span>
              {avaliacao.disciplina_nome}
            </span>
            <span>
              <span className="text-[10px] uppercase tracking-wider text-sepia/60 mr-1">
                Data
              </span>
              {formatarDataBR(avaliacao.data)}
            </span>
            <span>
              <span className="text-[10px] uppercase tracking-wider text-sepia/60 mr-1">
                Nota máx.
              </span>
              {avaliacao.nota_maxima}
            </span>
            <span>
              <span className="text-[10px] uppercase tracking-wider text-sepia/60 mr-1">
                Peso
              </span>
              {avaliacao.peso}
            </span>
            <span>
              <span className="text-[10px] uppercase tracking-wider text-sepia/60 mr-1">
                Período
              </span>
              {avaliacao.periodo_nome ?? (
                <span className="text-ferrugem">não alocado</span>
              )}
            </span>
          </div>
        </header>
      )}

      {avaliacao && avaliacao.periodo_nome === null && (
        <div className="rounded-md border border-ferrugem/40 bg-[#FCE7BC]/40 px-4 py-3 text-sm text-tinta">
          A data desta avaliação não cai em nenhum período avaliativo
          cadastrado. Cadastre um período em{" "}
          <Link
            to="/configuracao/periodos"
            className="underline text-ferrugem"
          >
            Configuração → Períodos avaliativos
          </Link>{" "}
          que cubra a data, e a alocação é refeita automaticamente quando
          esta avaliação for salva de novo.
        </div>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-xl text-tinta">Notas</h2>
          {podeModificarCadastros && (
            <Button
              onClick={handleSalvar}
              disabled={
                itensSujos.length === 0 || lancarMutation.isPending
              }
            >
              {lancarMutation.isPending
                ? "Salvando..."
                : itensSujos.length === 0
                  ? "Sem alterações"
                  : `Salvar ${itensSujos.length} ${itensSujos.length === 1 ? "nota" : "notas"}`}
            </Button>
          )}
        </div>

        {erroSubmit && (
          <p className="text-sm text-destructive">{erroSubmit}</p>
        )}

        <p className="text-[11px] text-sepia/70">
          Toda mudança em nota fica registrada com quem fez e quando — o
          histórico é visível na coluna "Última edição".
        </p>

        <div className="rounded-lg border border-border bg-paper overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                  Aluno
                </TableHead>
                <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal w-24">
                  Nota
                </TableHead>
                <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal hidden md:table-cell">
                  Observação
                </TableHead>
                <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal hidden lg:table-cell w-48">
                  Última edição
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {notasQuery.isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-8 w-16" />
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <Skeleton className="h-8 w-full" />
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                  </TableRow>
                ))
              ) : (notasQuery.data?.length ?? 0) === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="text-center text-muted-foreground py-8"
                  >
                    Nenhum aluno listado.
                  </TableCell>
                </TableRow>
              ) : (
                (notasQuery.data ?? []).map((n: NotaAvaliacao) => {
                  const linha = linhas[n.id] ?? { nota: "", observacao: "" };
                  const invalido = notaInvalida(linha.nota);
                  const editavel = podeModificarCadastros;
                  return (
                    <TableRow key={n.id}>
                      <TableCell>
                        <div className="text-tinta">{n.aluno_nome}</div>
                        <div className="text-[10px] text-sepia font-mono">
                          {n.aluno_matricula}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Input
                          type="text"
                          inputMode="decimal"
                          disabled={!editavel}
                          value={linha.nota}
                          onChange={(e) =>
                            atualizarLinha(n.id, { nota: e.target.value })
                          }
                          placeholder="—"
                          className={cn(
                            "w-20 text-center tabular-nums",
                            invalido && "border-destructive",
                          )}
                        />
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <Input
                          type="text"
                          disabled={!editavel}
                          value={linha.observacao}
                          onChange={(e) =>
                            atualizarLinha(n.id, {
                              observacao: e.target.value,
                            })
                          }
                          placeholder="(opcional — não vai pro boletim)"
                          className="w-full"
                        />
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-[11px] text-sepia">
                        {n.ultima_edicao && n.ultima_edicao.em ? (
                          <>
                            <span className="text-tinta">
                              {n.ultima_edicao.por ?? "—"}
                            </span>
                            <br />
                            <span className="font-mono tabular-nums">
                              {formatarTimestamp(n.ultima_edicao.em)}
                            </span>
                          </>
                        ) : (
                          <span className="text-sepia/60">nunca</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}
