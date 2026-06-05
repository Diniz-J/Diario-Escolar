import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

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
import { Label } from "@/components/ui/label";
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
import { NomeArquivoDialog } from "@/features/boletins/NomeArquivoDialog";
import {
  useBaixarBoletimPDF,
  useBoletim,
  useExportarAvaliacoesAluno,
} from "@/features/boletins/hooks";
import { usePeriodosAvaliativos } from "@/features/periodos-avaliativos/hooks";

// Valor especial pro <Select> que representa "anual" (sem filtro).
const PERIODO_ANUAL = "anual";

// Qual export está aguardando confirmação do nome no dialog. Null
// quando nenhum dialog está aberto.
type ExportAlvo = "pdf" | "csv" | "xlsx" | null;

// Página /boletim/:alunoId — visão consolidada do aluno (frequência,
// notas por disciplina e ocorrências). Sistema NÃO calcula média;
// mostra avaliações individuais + média final que o professor lançou.
//
// Botões na header:
// - "Imprimir": window.print() (CSS print esconde sidebar/botões)
// - "Baixar boletim (PDF)": gera PDF via WeasyPrint no backend
// - "Exportar avaliações": dropdown CSV/XLSX plano
export function BoletimPage() {
  const params = useParams<{ alunoId: string }>();
  const alunoId = params.alunoId ? parseInt(params.alunoId, 10) : undefined;

  const [periodoRaw, setPeriodoRaw] = useState(PERIODO_ANUAL);
  const periodoId =
    periodoRaw === PERIODO_ANUAL ? undefined : parseInt(periodoRaw, 10);

  const boletimQuery = useBoletim(
    alunoId,
    periodoId ? { periodo: periodoId } : {},
  );
  const periodosQuery = usePeriodosAvaliativos({ ativo: true });
  const baixarPDF = useBaixarBoletimPDF();
  const exportarAvaliacoes = useExportarAvaliacoesAluno();
  const [exportAlvo, setExportAlvo] = useState<ExportAlvo>(null);

  const boletim = boletimQuery.data;

  // Restringe os períodos do select ao ano letivo da turma do aluno
  // pra não poluir com anos antigos.
  const periodosDisponiveis = useMemo(() => {
    const todos = periodosQuery.data ?? [];
    const ano = boletim?.turma.ano_letivo ?? null;
    if (ano == null) return todos;
    return todos.filter((p) => p.ano_letivo === ano);
  }, [periodosQuery.data, boletim]);

  // Sugere nome default baseado no contexto: tipo (boletim ou
  // avaliacoes), matrícula e período. Servidor enviaria o mesmo no
  // Content-Disposition; aqui só pré-preenchemos o input do dialog.
  function nomeDefault(tipo: "boletim" | "avaliacoes"): string {
    if (!boletim) return tipo;
    const matricula = boletim.aluno.matricula;
    const sufixoPeriodo = boletim.periodo.nome
      ? boletim.periodo.nome.replace(/\s+/g, "_").toLowerCase()
      : "anual";
    return `${tipo}_${matricula}_${sufixoPeriodo}`;
  }

  function handleConfirmarDownload(nome: string) {
    if (alunoId == null || !exportAlvo) return;
    if (exportAlvo === "pdf") {
      baixarPDF.mutate(
        { alunoId, periodo: periodoId, nome },
        { onSettled: () => setExportAlvo(null) },
      );
    } else {
      exportarAvaliacoes.mutate(
        { alunoId, formato: exportAlvo, periodo: periodoId, nome },
        { onSettled: () => setExportAlvo(null) },
      );
    }
  }

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-4xl mx-auto print:p-0 print:max-w-none">
      <header className="space-y-3 print:hidden">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/alunos">← Voltar</Link>
        </Button>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="space-y-3">
            <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
              Boletim
            </h1>
            <div className="h-px w-10 bg-ferrugem" />
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Período
              </Label>
              <Select value={periodoRaw} onValueChange={setPeriodoRaw}>
                <SelectTrigger className="w-[200px] bg-paper border-border">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={PERIODO_ANUAL}>Anual</SelectItem>
                  {periodosDisponiveis.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.nome} ({p.ano_letivo})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              variant="outline"
              onClick={() => setExportAlvo("pdf")}
              disabled={baixarPDF.isPending}
            >
              {baixarPDF.isPending ? "Gerando..." : "Baixar boletim (PDF)"}
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  disabled={exportarAvaliacoes.isPending}
                >
                  {exportarAvaliacoes.isPending
                    ? "Exportando..."
                    : "Exportar avaliações"}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setExportAlvo("csv")}>
                  CSV
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setExportAlvo("xlsx")}>
                  XLSX
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button variant="ghost" onClick={() => window.print()}>
              Imprimir
            </Button>
          </div>
        </div>
      </header>

      {/* Cabeçalho que aparece SÓ na impressão — tipografia plana, sem
          paleta da marca, pra economizar tinta e ficar serio em papel. */}
      <header className="hidden print:block space-y-1 mb-6">
        <h1 className="text-2xl font-semibold">Boletim escolar</h1>
        <p className="text-sm">
          Emitido em {new Date().toLocaleDateString("pt-BR")}
        </p>
      </header>

      {boletimQuery.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-40 w-full" />
          </CardContent>
        </Card>
      ) : boletimQuery.isError || !boletim ? (
        <Card>
          <CardContent className="pt-6 text-destructive">
            Não foi possível carregar o boletim.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Aluno
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Nome
                </dt>
                <dd>{boletim.aluno.nome_completo}</dd>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Matrícula
                </dt>
                <dd className="font-mono">{boletim.aluno.matricula}</dd>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Turma
                </dt>
                <dd>
                  {boletim.turma.nome ?? "—"}
                  {boletim.turma.ano_letivo
                    ? ` — ${boletim.turma.ano_letivo}`
                    : ""}
                </dd>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Período
                </dt>
                <dd>
                  {boletim.periodo.nome ??
                    (boletim.periodo.data_inicio
                      ? `${boletim.periodo.data_inicio} a ${boletim.periodo.data_fim ?? "—"}`
                      : "Anual")}
                </dd>
                <dt className="text-[11px] uppercase tracking-[0.18em] text-sepia self-center">
                  Situação
                </dt>
                <dd>{boletim.aluno.ativo ? "Ativo" : "Inativo"}</dd>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Frequência
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <Indicador label="Presenças" valor={boletim.frequencia.presentes} />
                <Indicador
                  label="Retardatários"
                  valor={boletim.frequencia.retardatarios}
                />
                <Indicador
                  label="Justificadas"
                  valor={boletim.frequencia.justificados}
                />
                <Indicador label="Faltas" valor={boletim.frequencia.ausentes} />
              </div>
              <div className="border-t border-border pt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                    Total de chamadas
                  </p>
                  <p className="font-heading text-3xl tabular-nums text-tinta">
                    {boletim.frequencia.total}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                    Frequência
                  </p>
                  <p className="font-heading text-3xl tabular-nums text-tinta">
                    {boletim.frequencia.percentual_presenca}%
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Notas por disciplina
              </CardTitle>
            </CardHeader>
            <CardContent>
              {boletim.notas_por_disciplina.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  Nenhuma nota lançada até o momento.
                </p>
              ) : (
                <div className="space-y-6">
                  {boletim.notas_por_disciplina.map((d) => (
                    <div key={d.disciplina.id} className="space-y-3">
                      <h3 className="font-heading text-base tracking-tight">
                        {d.disciplina.nome}
                      </h3>

                      {/* Bloco 1: Notas finais por período (decisão do professor) */}
                      {d.notas_finais_por_periodo.length > 0 && (
                        <div className="rounded-lg border border-border bg-paper overflow-hidden print:bg-white">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                  Período
                                </TableHead>
                                <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                  Nota final
                                </TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {d.notas_finais_por_periodo.map((nf) => (
                                <TableRow key={nf.periodo_id}>
                                  <TableCell>{nf.periodo_nome}</TableCell>
                                  <TableCell className="text-right tabular-nums">
                                    <strong>{nf.nota_final}</strong>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      )}

                      {/* Bloco 2: Avaliações individuais */}
                      {d.avaliacoes.length > 0 ? (
                        <div className="rounded-lg border border-border bg-paper overflow-hidden print:bg-white">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                  Avaliação
                                </TableHead>
                                <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                  Tipo
                                </TableHead>
                                <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                  Nota
                                </TableHead>
                                <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                                  Máxima
                                </TableHead>
                                <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal hidden md:table-cell">
                                  Peso
                                </TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {d.avaliacoes.map((a) => (
                                <TableRow key={a.avaliacao_id}>
                                  <TableCell>
                                    {a.titulo}
                                    {a.periodo_nome && (
                                      <span className="text-[11px] text-sepia ml-2">
                                        — {a.periodo_nome}
                                      </span>
                                    )}
                                  </TableCell>
                                  <TableCell className="text-sepia text-sm">
                                    {a.tipo_display}
                                  </TableCell>
                                  <TableCell className="text-right tabular-nums">
                                    {a.nota_obtida}
                                  </TableCell>
                                  <TableCell className="text-right tabular-nums text-muted-foreground">
                                    {a.nota_maxima}
                                  </TableCell>
                                  <TableCell className="text-right tabular-nums text-muted-foreground hidden md:table-cell">
                                    {a.peso}
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground italic">
                          Nenhuma avaliação individual lançada.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg tracking-tight">
                Ocorrências
              </CardTitle>
            </CardHeader>
            <CardContent>
              {boletim.ocorrencias.total === 0 ? (
                <p className="text-sm text-muted-foreground py-2">
                  Sem ocorrências registradas.
                </p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  <Indicador
                    label="Abertas"
                    valor={boletim.ocorrencias.abertas}
                  />
                  <Indicador
                    label="Em andamento"
                    valor={boletim.ocorrencias.em_andamento}
                  />
                  <Indicador
                    label="Resolvidas"
                    valor={boletim.ocorrencias.resolvidas}
                  />
                  <Indicador
                    label="Arquivadas"
                    valor={boletim.ocorrencias.arquivadas}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Dialog único reaproveitado pros 3 tipos de export (PDF/CSV/XLSX).
          Aberto via `setExportAlvo` nos botões da header. */}
      <NomeArquivoDialog
        open={exportAlvo === "pdf"}
        onOpenChange={(open) => !open && setExportAlvo(null)}
        nomeDefault={nomeDefault("boletim")}
        extensao=".pdf"
        titulo="Baixar boletim em PDF"
        descricao="Escolha o nome do arquivo. O período selecionado é aplicado automaticamente."
        enviando={baixarPDF.isPending}
        onConfirmar={handleConfirmarDownload}
      />
      <NomeArquivoDialog
        open={exportAlvo === "csv"}
        onOpenChange={(open) => !open && setExportAlvo(null)}
        nomeDefault={nomeDefault("avaliacoes")}
        extensao=".csv"
        titulo="Exportar avaliações em CSV"
        descricao="Formato plano (uma linha por avaliação) — abre em Excel/Sheets pra calcular média no Excel."
        enviando={exportarAvaliacoes.isPending}
        onConfirmar={handleConfirmarDownload}
      />
      <NomeArquivoDialog
        open={exportAlvo === "xlsx"}
        onOpenChange={(open) => !open && setExportAlvo(null)}
        nomeDefault={nomeDefault("avaliacoes")}
        extensao=".xlsx"
        titulo="Exportar avaliações em XLSX"
        descricao="Mesmo conteúdo do CSV, formato Excel nativo (com colunas tipadas)."
        enviando={exportarAvaliacoes.isPending}
        onConfirmar={handleConfirmarDownload}
      />
    </div>
  );
}

function Indicador({ label, valor }: { label: string; valor: number }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
        {label}
      </p>
      <p className="font-heading text-3xl tabular-nums text-tinta">{valor}</p>
    </div>
  );
}
