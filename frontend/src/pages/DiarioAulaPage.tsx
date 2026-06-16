import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RegistroAulaFormDialog } from "@/features/aulas/RegistroAulaFormDialog";
import { DIAS_SEMANA_LABEL, STATUS_AULA } from "@/features/aulas/constants";
import { useAgendaAula } from "@/features/aulas/hooks";
import { useAuth } from "@/features/auth/useAuth";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useLecionamentos } from "@/features/lecionamentos/hooks";
import { useProfessores } from "@/features/professores/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { AgendaSlot } from "@/types/api";

const MESES = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

// "2026-06-16" -> "16/06"
function diaMes(iso: string): string {
  const [, mes, dia] = iso.split("-");
  return `${dia}/${mes}`;
}

export function DiarioAulaPage() {
  const { user } = useAuth();
  const professoresQuery = useProfessores();
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();

  // Professor logado: cruza o user_id do JWT com o Professor da escola.
  const meuProfessor = useMemo(
    () => professoresQuery.data?.find((p) => p.usuario === user?.user_id),
    [professoresQuery.data, user?.user_id],
  );

  const lecionamentosQuery = useLecionamentos(
    meuProfessor ? { professor: meuProfessor.id, ativo: true } : {},
  );

  const [lecionamentoId, setLecionamentoId] = useState<string>("");
  const [mesAtual, setMesAtual] = useState(() => {
    const hoje = new Date();
    return { ano: hoje.getFullYear(), mes: hoje.getMonth() + 1 };
  });

  const [dialogAberto, setDialogAberto] = useState(false);
  const [slotSelecionado, setSlotSelecionado] = useState<AgendaSlot | null>(
    null,
  );

  // Opções do select: cada lecionamento do professor com nomes resolvidos.
  const opcoes = useMemo(() => {
    const lecionamentos = meuProfessor ? lecionamentosQuery.data ?? [] : [];
    return lecionamentos.map((l) => {
      const turma = turmasQuery.data?.find((t) => t.id === l.turma);
      const disciplina = disciplinasQuery.data?.find(
        (d) => d.id === l.disciplina,
      );
      return {
        id: String(l.id),
        turma: l.turma,
        disciplina: l.disciplina,
        label: `${turma?.nome ?? `Turma #${l.turma}`} — ${
          disciplina?.nome ?? `Disciplina #${l.disciplina}`
        }`,
      };
    });
  }, [meuProfessor, lecionamentosQuery.data, turmasQuery.data, disciplinasQuery.data]);

  const lecionamentoSel = opcoes.find((o) => o.id === lecionamentoId);
  const mesParam = `${mesAtual.ano}-${String(mesAtual.mes).padStart(2, "0")}`;

  const agendaQuery = useAgendaAula(
    lecionamentoSel
      ? {
          turma: lecionamentoSel.turma,
          disciplina: lecionamentoSel.disciplina,
          mes: mesParam,
          professor: meuProfessor?.id,
        }
      : {},
  );

  function navegarMes(delta: number) {
    setMesAtual((atual) => {
      const d = new Date(atual.ano, atual.mes - 1 + delta, 1);
      return { ano: d.getFullYear(), mes: d.getMonth() + 1 };
    });
  }

  function abrirSlot(slot: AgendaSlot) {
    // Aula no futuro ainda não pode ser preenchida (backend bloqueia data
    // futura); só abre se já existe registro (ex.: editar rascunho).
    if (slot.futuro && slot.status === "vazio") return;
    setSlotSelecionado(slot);
    setDialogAberto(true);
  }

  const carregandoBase =
    professoresQuery.isLoading || lecionamentosQuery.isLoading;

  return (
    <div className="p-4 md:p-8 max-w-4xl">
      <header className="mb-6">
        <h1 className="font-heading text-2xl md:text-3xl tracking-tight text-tinta">
          Diário de Aula
        </h1>
        <div className="h-px w-10 bg-ferrugem mt-2 mb-3" />
        <p className="text-sm text-sepia">
          Registre o conteúdo ministrado em cada aula. Os dias vêm da grade
          horária do seu vínculo com a turma.
        </p>
      </header>

      {!carregandoBase && !meuProfessor && (
        <p className="text-sm text-sepia">
          Esta área é do professor — seu usuário não tem um cadastro de
          professor vinculado.
        </p>
      )}

      {meuProfessor && (
        <>
          {/* Controles: vínculo (turma+disciplina) + navegação de mês. */}
          <div className="flex flex-col sm:flex-row sm:items-end gap-4 mb-6">
            <div className="flex-1 space-y-2">
              <label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Turma — Disciplina
              </label>
              <Select value={lecionamentoId} onValueChange={setLecionamentoId}>
                <SelectTrigger className="w-full">
                  <SelectValue
                    placeholder={
                      opcoes.length === 0
                        ? "Você não tem vínculos ativos"
                        : "Selecione a turma e disciplina"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {opcoes.map((o) => (
                    <SelectItem key={o.id} value={o.id}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                aria-label="Mês anterior"
                onClick={() => navegarMes(-1)}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <span className="min-w-[140px] text-center text-sm font-medium text-tinta">
                {MESES[mesAtual.mes - 1]} {mesAtual.ano}
              </span>
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                aria-label="Próximo mês"
                onClick={() => navegarMes(1)}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>

          {/* Lista de slots do mês. */}
          {!lecionamentoSel ? (
            <p className="text-sm text-sepia">
              Selecione uma turma e disciplina para ver os dias de aula.
            </p>
          ) : agendaQuery.isLoading ? (
            <p className="text-sm text-sepia">Carregando agenda…</p>
          ) : (agendaQuery.data?.length ?? 0) === 0 ? (
            <p className="text-sm text-sepia">
              Nenhum dia de aula neste mês. Verifique a grade horária (dias da
              semana) deste vínculo no cadastro do lecionamento.
            </p>
          ) : (
            <ul className="space-y-2">
              {agendaQuery.data?.map((slot) => {
                const estilo = STATUS_AULA[slot.status];
                const bloqueado = slot.futuro && slot.status === "vazio";
                return (
                  <li
                    key={slot.data}
                    className="flex items-center gap-4 rounded-md border border-border bg-paper px-4 py-3"
                  >
                    <div className="w-20 shrink-0">
                      <div className="text-sm font-medium text-tinta">
                        {diaMes(slot.data)}
                      </div>
                      <div className="text-[11px] uppercase tracking-[0.12em] text-sepia">
                        {DIAS_SEMANA_LABEL[slot.dia_semana]}
                      </div>
                    </div>

                    <span
                      className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${estilo.classe}`}
                    >
                      {estilo.label}
                    </span>

                    <div className="ml-auto">
                      <Button
                        type="button"
                        variant={slot.status === "vazio" ? "default" : "outline"}
                        size="sm"
                        disabled={bloqueado}
                        onClick={() => abrirSlot(slot)}
                      >
                        {bloqueado
                          ? "Futuro"
                          : slot.status === "vazio"
                            ? "Preencher"
                            : slot.status === "conferido"
                              ? "Ver"
                              : "Editar"}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}

      {slotSelecionado && lecionamentoSel && meuProfessor && (
        <RegistroAulaFormDialog
          open={dialogAberto}
          onOpenChange={setDialogAberto}
          turma={lecionamentoSel.turma}
          disciplina={lecionamentoSel.disciplina}
          professor={meuProfessor.id}
          data={slotSelecionado.data}
          registroId={slotSelecionado.registro_id}
          contextoLabel={`${lecionamentoSel.label} · ${diaMes(slotSelecionado.data)}`}
        />
      )}
    </div>
  );
}
