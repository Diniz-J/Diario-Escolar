import axios from "axios";
import { useState, type FormEvent } from "react";

import { AlertaOpcoesIndisponiveis } from "@/components/AlertaOpcoesIndisponiveis";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/features/auth/useAuth";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { horaCurta } from "@/features/grade/constants";
import { useGradeAulas, useTemposAula } from "@/features/grade/hooks";
import { useProfessores } from "@/features/professores/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { diaDaSemanaISO, hojeISO } from "@/lib/datas";
import { cn } from "@/lib/utils";
import type { RegistroPresencaInput } from "@/types/api";

import { useCreateRegistro } from "./hooks";

const LABEL = "text-[11px] uppercase tracking-[0.18em] text-sepia";

interface RegistroFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Disparado após criar o registro com sucesso — útil pra navegar
  // pra tela de chamada do novo registro.
  onCreated?: (id: number) => void;
}

// Form de criação de uma chamada. Itens (status por aluno) são gerados
// automaticamente pelo backend no perform_create da view — não enviamos
// itens daqui.
//
// A chamada cobre um bloco de tempos (`PRESENCA.md`), e a grade horária
// pré-marca o bloco: o professor abre, confere e lança. Quando a grade diz
// que ele tem o 1º e o 2º tempo naquela turma naquele dia, é isso que vem
// marcado, com a disciplina dele junto — era o "mínimo de trabalho
// possível" que o pedido exigia.
export function RegistroFormDialog({
  open,
  onOpenChange,
  onCreated,
}: RegistroFormDialogProps) {
  // `escola` no payload SÓ pra admin global — derivada da turma.
  // Outros perfis: backend deduz via JWT.
  const { ehAdminGlobal } = usePermissoes();
  const { user } = useAuth();
  const turmasQuery = useTurmas();
  const professoresQuery = useProfessores();
  const createMutation = useCreateRegistro();

  const hoje = hojeISO();

  // Cada estado guarda só a escolha explícita; o valor que vale é o
  // derivado abaixo. É o padrão da casa pra valor que depende de query:
  // sincronizar com `setState` num efeito é o que a regra
  // `react-hooks/set-state-in-effect` acusa.
  const [turmaId, setTurmaId] = useState("");
  const [data, setData] = useState(hoje);
  const [temposTocados, setTemposTocados] = useState<number[] | null>(null);
  const [disciplinaTocada, setDisciplinaTocada] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  // Se há uma única turma, ela entra sozinha quando a lista chega.
  const turmas = turmasQuery.data;
  const turmaEfetiva =
    turmaId || (turmas?.length === 1 ? String(turmas[0].id) : "");
  const turma = turmas?.find((t) => String(t.id) === turmaEfetiva);

  const temposQuery = useTemposAula(
    turma ? { turno: turma.turno, ativo: true } : { ativo: true },
  );
  const gradeQuery = useGradeAulas(
    { turma: turma?.id, dia_semana: diaDaSemanaISO(data), ativo: true },
    turma != null,
  );

  const tempos = (temposQuery.data ?? [])
    .filter((tempo) => !turma || tempo.turno === turma.turno)
    .sort((a, b) => a.ordem - b.ordem);

  // Professor logado: cruza o user_id do JWT com o Professor da escola
  // (mesmo critério do Diário de Aula e do Mural).
  const meuProfessor =
    professoresQuery.data?.find((p) => p.usuario === user?.user_id) ?? null;

  // Sugestão da grade: os slots **deste professor** nesta turma neste dia
  // da semana. O critério é o cadastro de `Professor` do usuário logado, e
  // não o perfil: o diretor que também dá aula (comum em escola pequena)
  // tem grade própria e merece a mesma sugestão. Quem não tem cadastro de
  // professor, ou não tem aula ali, recebe o dia todo — que é a semântica
  // que a chamada diária tinha.
  const meusSlots = meuProfessor
    ? (gradeQuery.data ?? []).filter((slot) => slot.professor === meuProfessor.id)
    : [];
  const temposSugeridos =
    meusSlots.length > 0
      ? [...new Set(meusSlots.map((slot) => slot.tempo_ordem))].sort(
          (a, b) => a - b,
        )
      : tempos.map((tempo) => tempo.ordem);

  // A disciplina só é sugerida quando os slots do dia são todos da mesma:
  // dois tempos de matérias diferentes são duas chamadas, e preencher uma
  // delas por palpite colocaria a aula errada no registro.
  const disciplinasDosSlots = [
    ...new Set(meusSlots.map((slot) => String(slot.disciplina))),
  ];
  const disciplinaSugerida =
    disciplinasDosSlots.length === 1 ? disciplinasDosSlots[0] : "";

  const temposEfetivos = temposTocados ?? temposSugeridos;
  const disciplinaEfetiva = disciplinaTocada ?? disciplinaSugerida;

  // A turma é exigida na validação de submit: sem a lista não há chamada a
  // abrir. As listas de tempo e de grade **não** travam o envio: sem
  // catálogo cadastrado o backend assume um tempo, e é assim que a escola
  // que ainda não montou a grade segue lançando chamada.
  const falhouCarregar = turmasQuery.isError;

  function alternarTempo(ordem: number) {
    const atual = temposEfetivos;
    setTemposTocados(
      atual.includes(ordem)
        ? atual.filter((item) => item !== ordem)
        : [...atual, ordem].sort((a, b) => a - b),
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (!turma) {
      setErro("Selecione uma turma.");
      return;
    }
    if (tempos.length > 0 && temposEfetivos.length === 0) {
      setErro("Marque ao menos um tempo de aula.");
      return;
    }

    const payload: RegistroPresencaInput = {
      // `escola` deduzida pelo backend quando o user tem escola no perfil.
      ...(ehAdminGlobal ? { escola: turma.escola } : {}),
      turma: turma.id,
      data,
      // O backend resolve o professor do usuário logado; mandar null aqui
      // mantém o campo no payload sem tentar assinar por outro.
      professor: null,
      observacao: "",
      // Sem catálogo de tempos, o campo fica fora do payload e o backend
      // assume um tempo — é o que mantém a chamada funcionando antes de a
      // escola montar a grade.
      ...(tempos.length > 0 ? { tempos: temposEfetivos } : {}),
      ...(disciplinaEfetiva
        ? { disciplina: parseInt(disciplinaEfetiva, 10) }
        : {}),
    };

    try {
      const novo = await createMutation.mutateAsync(payload);
      onOpenChange(false);
      onCreated?.(novo.id);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const dataErr = err.response.data as Record<string, unknown>;
        const primeiraMsg = Object.values(dataErr)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeiraMsg ?? "Não foi possível criar a chamada.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            Nova chamada
          </DialogTitle>
          <DialogDescription>
            Os alunos ativos da turma serão adicionados automaticamente
            como presentes; você ajusta os ausentes na tela seguinte.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label className={LABEL}>Turma</Label>
            <Select value={turmaEfetiva} onValueChange={setTurmaId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Selecione uma turma" />
              </SelectTrigger>
              <SelectContent>
                {turmas?.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.nome} — {t.turno_display} {t.ano_letivo}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="data" className={LABEL}>
              Data
            </Label>
            <Input
              id="data"
              type="date"
              required
              max={hoje}
              value={data}
              onChange={(e) => setData(e.target.value)}
            />
          </div>

          {tempos.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label className={LABEL}>Tempos</Label>
                <div className="flex gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() =>
                      setTemposTocados(tempos.map((tempo) => tempo.ordem))
                    }
                  >
                    Dia todo
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => setTemposTocados([])}
                  >
                    Limpar
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {tempos.map((tempo) => {
                  const marcado = temposEfetivos.includes(tempo.ordem);
                  return (
                    <button
                      key={tempo.id}
                      type="button"
                      aria-pressed={marcado}
                      onClick={() => alternarTempo(tempo.ordem)}
                      className={cn(
                        "rounded border px-3 py-2 text-left transition",
                        marcado
                          ? "border-olive bg-olive/10 text-tinta"
                          : "border-border bg-paper text-muted-foreground hover:text-tinta",
                      )}
                    >
                      <span className="block text-sm leading-tight">
                        {tempo.ordem}º
                      </span>
                      <span className="block text-[11px] tabular-nums leading-tight">
                        {horaCurta(tempo.hora_inicio)}
                      </span>
                    </button>
                  );
                })}
              </div>
              {meusSlots.length > 0 && temposTocados === null && (
                <p className="text-xs text-muted-foreground">
                  Marcados pela grade horária desta turma.
                </p>
              )}
            </div>
          )}

          {meusSlots.length > 0 && (
            <div className="space-y-2">
              <Label className={LABEL}>Disciplina</Label>
              <Select
                value={disciplinaEfetiva}
                onValueChange={setDisciplinaTocada}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Chamada do dia (sem disciplina)" />
                </SelectTrigger>
                <SelectContent>
                  {[
                    ...new Map(
                      meusSlots.map((slot) => [
                        String(slot.disciplina),
                        slot.disciplina_nome,
                      ]),
                    ),
                  ].map(([id, nome]) => (
                    <SelectItem key={id} value={id}>
                      {nome}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <AlertaOpcoesIndisponiveis falhou={falhouCarregar} />

          {erro && (
            <Alert variant="destructive">
              <AlertDescription>{erro}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={createMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isPending || falhouCarregar}
            >
              {createMutation.isPending ? "Criando..." : "Abrir chamada"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
