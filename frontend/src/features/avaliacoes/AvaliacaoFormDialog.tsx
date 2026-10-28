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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useEscolas } from "@/features/escolas/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { hojeISO } from "@/lib/datas";
import type { Avaliacao, AvaliacaoInput, AvaliacaoTipo } from "@/types/api";

import { useCreateAvaliacao, useUpdateAvaliacao } from "./hooks";

interface AvaliacaoFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  avaliacao?: Avaliacao | null;
}

const TIPOS: { value: AvaliacaoTipo; label: string }[] = [
  { value: "prova", label: "Prova" },
  { value: "trabalho", label: "Trabalho" },
  { value: "atividade", label: "Atividade" },
  { value: "participacao", label: "Participação" },
];

export function AvaliacaoFormDialog({
  open,
  onOpenChange,
  avaliacao,
}: AvaliacaoFormDialogProps) {
  // **Estritamente** o perfil `admin` enxerga o select de escola.
  // Diretor/secretaria/professor/inspetor NUNCA — mesmo se algum dia
  // tiver `escola_id=null` por bug, esses perfis não podem ver UI
  // de "escolha de escola" (decisão crítica de produto). Backend
  // continua sendo a fonte de verdade da permissão; isso é só UX.
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();
  const createMutation = useCreateAvaliacao();
  const updateMutation = useUpdateAvaliacao();

  const editando = avaliacao != null;

  // Estado nasce dos props — a página remonta o dialog (`key={formKey}`) a
  // cada abertura, então não há `useEffect` pra repreencher.
  const [titulo, setTitulo] = useState(avaliacao?.titulo ?? "");
  const [descricao, setDescricao] = useState(avaliacao?.descricao ?? "");
  const [tipo, setTipo] = useState<AvaliacaoTipo>(avaliacao?.tipo ?? "prova");
  const [data, setData] = useState(avaliacao?.data ?? hojeISO());
  const [notaMaxima, setNotaMaxima] = useState(avaliacao?.nota_maxima ?? "10");
  const [peso, setPeso] = useState(avaliacao?.peso ?? "1");
  const [turmaId, setTurmaId] = useState(
    avaliacao ? String(avaliacao.turma) : "",
  );
  const [disciplinaId, setDisciplinaId] = useState(
    avaliacao ? String(avaliacao.disciplina) : "",
  );
  // `escolaId` guarda só a escolha explícita; o valor que vale é o
  // derivado abaixo. A lista de escolas chega depois do mount, e
  // sincronizá-la com `setState` num efeito é o que a regra
  // `react-hooks/set-state-in-effect` acusa.
  const [escolaId, setEscolaId] = useState(
    avaliacao ? String(avaliacao.escola) : "",
  );
  const [erro, setErro] = useState<string | null>(null);

  // Pré-seleção só faz sentido pra admin global (só ele vê o campo).
  const escolas = escolasQuery.data;
  const escolaEfetiva =
    escolaId ||
    (ehAdminGlobal && escolas?.length === 1 ? String(escolas[0].id) : "");

  // Turma e disciplina são exigidas na validação, e a escola também
  // pro admin global — qualquer uma das três faltando impede salvar.
  const falhouCarregar =
    turmasQuery.isError ||
    disciplinasQuery.isError ||
    (ehAdminGlobal && escolasQuery.isError);

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (!turmaId || !disciplinaId) {
      setErro("Selecione turma e disciplina.");
      return;
    }
    if (ehAdminGlobal && !escolaEfetiva) {
      setErro("Selecione uma escola.");
      return;
    }

    const payload: AvaliacaoInput = {
      // `escola` no payload só pra admin global. Demais perfis: backend
      // deduz via AutoEscopoEscolaMixin a partir do JWT — não enviamos
      // mesmo que o estado local tenha algo (defesa contra bug futuro).
      ...(ehAdminGlobal && escolaEfetiva
        ? { escola: parseInt(escolaEfetiva, 10) }
        : {}),
      turma: parseInt(turmaId, 10),
      disciplina: parseInt(disciplinaId, 10),
      professor: avaliacao?.professor ?? null,
      titulo,
      descricao,
      tipo,
      data,
      nota_maxima: notaMaxima,
      peso,
    };

    try {
      if (editando && avaliacao) {
        await updateMutation.mutateAsync({ id: avaliacao.id, patch: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
      onOpenChange(false);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data as Record<string, unknown>;
        const primeiraMsg = Object.values(data)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeiraMsg ?? "Não foi possível salvar.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  // Turmas ativas só pra reduzir ruído no select.
  const turmasAtivas = (turmasQuery.data ?? []).filter((t) => t.ativa);
  const disciplinasAtivas = (disciplinasQuery.data ?? []).filter(
    (d) => d.ativa,
  );

  // Select de escola: **só** pra `perfil === "admin"`. Outros perfis
  // NUNCA enxergam. Mostramos pra admin SEMPRE — mesmo com 1 escola só
  // — pra deixar explícito em qual escola o registro está sendo criado.
  // Quando há 1 escola, vem pré-selecionada pelo useEffect; quando há
  // 2+, o admin escolhe.
  const mostrarEscolaSelect = ehAdminGlobal;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar avaliação" : "Nova avaliação"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize os dados da avaliação. As notas dos alunos continuam preservadas."
              : "Cria a avaliação e gera notas em branco pra cada aluno ativo da turma — pronto pra lançar na próxima tela."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label
              htmlFor="titulo"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Título
            </Label>
            <Input
              id="titulo"
              required
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Ex.: Prova bimestral 1"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Tipo
              </Label>
              <Select
                value={tipo}
                onValueChange={(v) => setTipo(v as AvaliacaoTipo)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIPOS.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="data"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Data
              </Label>
              <Input
                id="data"
                required
                type="date"
                value={data}
                onChange={(e) => setData(e.target.value)}
              />
            </div>
          </div>

          {mostrarEscolaSelect && (
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Escola
              </Label>
              <Select value={escolaEfetiva} onValueChange={setEscolaId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Selecione a escola" />
                </SelectTrigger>
                <SelectContent>
                  {escolasQuery.data?.map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      {e.nome}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Turma
              </Label>
              <Select value={turmaId} onValueChange={setTurmaId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Selecione a turma" />
                </SelectTrigger>
                <SelectContent>
                  {turmasAtivas.map((t) => (
                    <SelectItem key={t.id} value={String(t.id)}>
                      {t.nome} — {t.ano_letivo}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Disciplina
              </Label>
              <Select value={disciplinaId} onValueChange={setDisciplinaId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Selecione a disciplina" />
                </SelectTrigger>
                <SelectContent>
                  {disciplinasAtivas.map((d) => (
                    <SelectItem key={d.id} value={String(d.id)}>
                      {d.nome}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label
                htmlFor="nota_maxima"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Nota máxima
              </Label>
              <Input
                id="nota_maxima"
                required
                type="number"
                step="0.01"
                min="0.01"
                value={notaMaxima}
                onChange={(e) => setNotaMaxima(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="peso"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Peso
              </Label>
              <Input
                id="peso"
                type="number"
                step="0.01"
                min="0"
                value={peso}
                onChange={(e) => setPeso(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label
              htmlFor="descricao"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Descrição (opcional)
            </Label>
            <textarea
              id="descricao"
              rows={3}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder="Conteúdo cobrado, regra de recuperação, etc."
              className="w-full rounded-md border border-border bg-paper px-3 py-2 text-sm focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition resize-y"
            />
          </div>

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
              disabled={enviando}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando || falhouCarregar}>
              {enviando ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
