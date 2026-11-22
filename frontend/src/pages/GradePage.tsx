import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { ClonarGradeDialog } from "@/features/grade/ClonarGradeDialog";
import { SlotFormDialog } from "@/features/grade/SlotFormDialog";
import { GradeTabs } from "@/features/grade/GradeTabs";
import {
  DIAS_SEMANA,
  DIAS_UTEIS,
  horaCurta,
} from "@/features/grade/constants";
import {
  useDeleteSlot,
  useGradeAulas,
  useTemposAula,
} from "@/features/grade/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { AulaGrade, TempoAula } from "@/types/api";

const EYEBROW = "text-[11px] uppercase tracking-[0.18em] text-sepia";

// Grade horária de uma turma: linhas são os tempos do turno dela, colunas
// são os dias da semana. A matriz tem scroll horizontal no celular em vez
// de esconder colunas (o padrão das listagens): numa grade os dois eixos
// são o dado, e sumir com quarta-feira não é uma simplificação, é perder
// a informação.
export function GradePage() {
  const { podeModificarCadastros: ehDirecao } = usePermissoes();
  const turmasQuery = useTurmas();
  const deleteSlotMutation = useDeleteSlot();

  // A turma escolhida mora na URL, como no financeiro (`/financeiro?turma=`):
  // dá link direto pra grade de uma turma e evita uma segunda fonte de
  // verdade ao lado do `?turma=` que o Select escreve.
  const [searchParams, setSearchParams] = useSearchParams();
  const turmaId = searchParams.get("turma") ?? "";
  const [incluirSabado, setIncluirSabado] = useState(false);
  const [slotNovo, setSlotNovo] = useState<{
    diaSemana: number;
    tempo: TempoAula;
  } | null>(null);
  // Incrementa a cada abertura: remonta o dialog, que inicializa o estado
  // a partir dos props (sem `useEffect` pra resetar).
  const [formKey, setFormKey] = useState(0);
  const [clonando, setClonando] = useState(false);

  // Só turmas ativas no select de montagem, como nos outros selects de
  // criação do projeto. (O dialog de clonagem lista todas de propósito:
  // a origem costuma ser a turma do ano anterior, já encerrada.)
  const turmas = (turmasQuery.data ?? []).filter((t) => t.ativa);
  const turma = turmas.find((t) => String(t.id) === turmaId);

  // Catálogo do turno da turma — é o `clean()` do backend que exige o
  // casamento, então oferecer tempo de outro turno daria erro ao salvar.
  const temposQuery = useTemposAula(
    turma ? { turno: turma.turno, ativo: true } : { ativo: true },
  );
  const gradeQuery = useGradeAulas(
    { turma: turma?.id, ativo: true },
    turma != null,
  );

  // Derivados sem `useMemo`: o React Compiler já memoiza, e a memoização
  // manual aqui era rejeitada por ele (`preserve-manual-memoization`)
  // porque as deps saem de arrays derivados. A escala torna isso
  // irrelevante — uma turma tem algumas dezenas de slots.
  const tempos = (temposQuery.data ?? [])
    .filter((tempo) => !turma || tempo.turno === turma.turno)
    .sort((a, b) => a.ordem - b.ordem);

  const slots = gradeQuery.data ?? [];

  function slotDaCelula(dia: number, tempoId: number): AulaGrade | undefined {
    return slots.find(
      (slot) => slot.dia_semana === dia && slot.tempo === tempoId,
    );
  }

  // Sábado e domingo entram quando a escola usa: por escolha explícita no
  // toggle, ou porque já existe aula lançada ali (senão o slot existiria
  // sem nenhuma coluna que o mostrasse).
  const diasExtras = new Set<number>();
  if (incluirSabado) diasExtras.add(5);
  slots.forEach((slot) => {
    if (!DIAS_UTEIS.includes(slot.dia_semana)) diasExtras.add(slot.dia_semana);
  });
  const dias = [...DIAS_UTEIS, ...[...diasExtras].sort((a, b) => a - b)];

  function escolherTurma(valor: string) {
    const proximo = new URLSearchParams(searchParams);
    if (valor) {
      proximo.set("turma", valor);
    } else {
      proximo.delete("turma");
    }
    // `replace`: trocar de turma não é passo de navegação que mereça
    // entrada no histórico do browser.
    setSearchParams(proximo, { replace: true });
  }

  function abrirSlot(diaSemana: number, tempo: TempoAula) {
    setSlotNovo({ diaSemana, tempo });
    setFormKey((k) => k + 1);
  }

  const carregando =
    turmasQuery.isLoading ||
    (turma != null && (temposQuery.isLoading || gradeQuery.isLoading));
  // Ramo de erro vem ANTES do vazio: no TanStack Query o `isLoading` volta
  // a false quando a query falha, e sem isto a tela apresentaria a falha
  // de rede como "esta turma não tem grade montada".
  const falhou =
    turmasQuery.isError ||
    (turma != null && (temposQuery.isError || gradeQuery.isError));

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Grade horária
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground max-w-xl">
            Que aula a turma tem em cada tempo da semana. A chamada usa esta
            grade para já vir com os tempos do dia marcados.
          </p>
        </div>
        {ehDirecao && turma && (
          <Button
            type="button"
            variant="outline"
            onClick={() => setClonando(true)}
          >
            Clonar grade
          </Button>
        )}
      </header>

      <GradeTabs />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="space-y-2">
          <Label className={EYEBROW}>Turma</Label>
          <Select value={turmaId} onValueChange={escolherTurma}>
            <SelectTrigger className="w-full sm:w-72">
              <SelectValue placeholder="Selecione a turma" />
            </SelectTrigger>
            <SelectContent>
              {turmas.map((t) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.nome} — {t.turno_display} ({t.ano_letivo})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <Switch
            id="sabado"
            checked={incluirSabado}
            onCheckedChange={setIncluirSabado}
          />
          <Label htmlFor="sabado" className="cursor-pointer text-sm">
            Incluir sábado
          </Label>
        </div>
      </div>

      {falhou && (
        <Alert variant="destructive">
          <AlertDescription>
            Não foi possível carregar a grade. Tente novamente.
          </AlertDescription>
        </Alert>
      )}

      {!falhou && carregando && <Skeleton className="h-64 w-full" />}

      {!falhou && !carregando && !turma && (
        <p className="text-sm text-muted-foreground">
          Escolha uma turma para ver e montar a grade dela.
        </p>
      )}

      {!falhou && !carregando && turma && tempos.length === 0 && (
        <div className="rounded-lg border border-border bg-paper p-6 space-y-2">
          <p className="text-sm text-tinta">
            O turno {turma.turno_display.toLowerCase()} ainda não tem tempos
            de aula cadastrados.
          </p>
          <p className="text-sm text-muted-foreground">
            Cadastre os horários na aba "Tempos de aula" — é o catálogo que
            esta grade usa.
          </p>
        </div>
      )}

      {!falhou && !carregando && turma && tempos.length > 0 && (
        <div className="rounded-lg border border-border bg-paper overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse">
            <thead>
              <tr>
                <th className={`${EYEBROW} p-3 text-left font-normal`}>
                  Tempo
                </th>
                {dias.map((dia) => (
                  <th
                    key={dia}
                    className={`${EYEBROW} p-3 text-left font-normal`}
                  >
                    {DIAS_SEMANA.find((d) => d.valor === dia)?.label ?? dia}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tempos.map((tempo) => (
                <tr key={tempo.id} className="border-t border-border">
                  <td className="p-3 align-top whitespace-nowrap">
                    <div className="text-sm text-tinta">{tempo.ordem}º</div>
                    <div className="text-xs text-muted-foreground">
                      {horaCurta(tempo.hora_inicio)}–
                      {horaCurta(tempo.hora_fim)}
                    </div>
                  </td>
                  {dias.map((dia) => {
                    const slot = slotDaCelula(dia, tempo.id);
                    return (
                      <td key={dia} className="p-2 align-top">
                        {slot ? (
                          <div className="rounded border border-border bg-creme/60 p-2 space-y-1">
                            <div className="text-sm text-tinta leading-tight">
                              {slot.disciplina_nome}
                            </div>
                            <div className="text-xs text-muted-foreground leading-tight">
                              {slot.professor_nome}
                            </div>
                            {ehDirecao && (
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-6 px-1 text-xs text-destructive"
                                disabled={deleteSlotMutation.isPending}
                                onClick={() =>
                                  deleteSlotMutation.mutate(slot.id)
                                }
                              >
                                Remover
                              </Button>
                            )}
                          </div>
                        ) : ehDirecao ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-8 w-full text-sepia"
                            onClick={() => abrirSlot(dia, tempo)}
                          >
                            +
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            —
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {slotNovo && turma && (
        <SlotFormDialog
          key={formKey}
          open={slotNovo != null}
          onOpenChange={(aberto) => !aberto && setSlotNovo(null)}
          turmaId={turma.id}
          diaSemana={slotNovo.diaSemana}
          tempo={slotNovo.tempo}
        />
      )}

      {clonando && turma && (
        <ClonarGradeDialog
          open={clonando}
          onOpenChange={(aberto) => !aberto && setClonando(false)}
          turmaDestino={turma}
        />
      )}
    </div>
  );
}
