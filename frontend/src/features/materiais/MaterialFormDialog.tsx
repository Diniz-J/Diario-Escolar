import axios from "axios";
import { useMemo, useState } from "react";

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
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useLecionamentos } from "@/features/lecionamentos/hooks";
import { useProfessores } from "@/features/professores/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { Material, Professor } from "@/types/api";

import { useCreateMaterial, useUpdateMaterial } from "./hooks";

interface MaterialFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Presente = edição. Na edição só título, descrição e link mudam: turma,
  // disciplina e professor ficam fixos (pra mudar, despublica e publica
  // outro) — evita reabrir a validação de lecionamento no meio da edição.
  material?: Material | null;
  // Direção escolhe o professor; professor publica só em nome próprio.
  ehDirecao: boolean;
  // Professor logado (null pra direção sem cadastro de professor).
  meuProfessor: Professor | null;
}

const LABEL_CLASS = "text-[11px] uppercase tracking-[0.18em] text-sepia";

// Ajuda pra quem digita; quem valida de verdade é o backend (só http/https).
function linkValido(link: string): boolean {
  return !link || /^https?:\/\//i.test(link.trim());
}

export function MaterialFormDialog({
  open,
  onOpenChange,
  material,
  ehDirecao,
  meuProfessor,
}: MaterialFormDialogProps) {
  const editando = material != null;
  const createMutation = useCreateMaterial();
  const updateMutation = useUpdateMaterial();
  const professoresQuery = useProfessores();
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();

  // Estado nasce dos props. A página remonta o dialog (`key`) a cada
  // abertura, então não há `useEffect` pra resetar.
  const [professorId, setProfessorId] = useState<string>(
    ehDirecao ? "" : String(meuProfessor?.id ?? ""),
  );
  const [lecionamentoId, setLecionamentoId] = useState<string>("");
  const [titulo, setTitulo] = useState(material?.titulo ?? "");
  const [descricao, setDescricao] = useState(material?.descricao ?? "");
  const [link, setLink] = useState(material?.link ?? "");
  const [erro, setErro] = useState<string | null>(null);

  // Só os lecionamentos ATIVOS do professor escolhido: o professor nem vê
  // turma que não leciona (o backend recusaria de qualquer jeito).
  const lecionamentosQuery = useLecionamentos(
    { professor: Number(professorId), ativo: true },
    !editando && professorId !== "",
  );

  const turmas = turmasQuery.data;
  const disciplinas = disciplinasQuery.data;
  const nomeTurma = (id: number) =>
    turmas?.find((t) => t.id === id)?.nome ?? `Turma #${id}`;
  const nomeDisciplina = (id: number) =>
    disciplinas?.find((d) => d.id === id)?.nome ?? `Disciplina #${id}`;

  const opcoes = useMemo(
    () =>
      (lecionamentosQuery.data ?? []).map((l) => ({
        id: String(l.id),
        turma: l.turma,
        disciplina: l.disciplina,
        label: `${turmas?.find((t) => t.id === l.turma)?.nome ?? `Turma #${l.turma}`} — ${
          disciplinas?.find((d) => d.id === l.disciplina)?.nome ??
          `Disciplina #${l.disciplina}`
        }`,
      })),
    [lecionamentosQuery.data, turmas, disciplinas],
  );

  const professoresAtivos = (professoresQuery.data ?? []).filter((p) => p.ativo);
  const enviando = createMutation.isPending || updateMutation.isPending;

  async function salvar() {
    setErro(null);
    if (!titulo.trim()) {
      setErro("Informe o título.");
      return;
    }
    if (!linkValido(link)) {
      setErro("O link precisa começar com http:// ou https://.");
      return;
    }
    try {
      if (editando && material) {
        await updateMutation.mutateAsync({
          id: material.id,
          patch: { titulo, descricao, link: link.trim() },
        });
      } else {
        const escolhido = opcoes.find((o) => o.id === lecionamentoId);
        if (!escolhido) {
          setErro("Escolha a turma e a disciplina.");
          return;
        }
        await createMutation.mutateAsync({
          turma: escolhido.turma,
          disciplina: escolhido.disciplina,
          professor: Number(professorId),
          titulo,
          descricao,
          link: link.trim(),
        });
      }
      onOpenChange(false);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const dados = err.response.data as Record<string, unknown>;
        const primeira = Object.values(dados)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeira ?? "Não foi possível salvar o material.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar material" : "Publicar material"}
          </DialogTitle>
          <DialogDescription>
            {editando && material
              ? `${nomeTurma(material.turma)} — ${nomeDisciplina(material.disciplina)} · ${material.professor_nome}`
              : "Aparece no portal para os responsáveis dos alunos da turma."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {!editando && ehDirecao && (
            <div className="space-y-2">
              <Label className={LABEL_CLASS}>Professor</Label>
              <Select
                value={professorId}
                onValueChange={(v) => {
                  setProfessorId(v);
                  setLecionamentoId("");
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Escolha o professor" />
                </SelectTrigger>
                <SelectContent>
                  {professoresAtivos.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.nome_completo}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {!editando && (
            <div className="space-y-2">
              <Label className={LABEL_CLASS}>Turma e disciplina</Label>
              <Select
                value={lecionamentoId}
                onValueChange={setLecionamentoId}
                disabled={professorId === "" || lecionamentosQuery.isLoading}
              >
                <SelectTrigger className="w-full">
                  <SelectValue
                    placeholder={
                      professorId === ""
                        ? "Escolha o professor primeiro"
                        : "Escolha a turma e a disciplina"
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
              {professorId !== "" &&
                !lecionamentosQuery.isLoading &&
                opcoes.length === 0 && (
                  <p className="text-xs text-sepia">
                    Nenhuma turma vinculada a este professor.
                  </p>
                )}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="material-titulo" className={LABEL_CLASS}>
              Título
            </Label>
            <Input
              id="material-titulo"
              maxLength={200}
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Ex.: Lista de exercícios — frações"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="material-descricao" className={LABEL_CLASS}>
              Descrição (opcional)
            </Label>
            <textarea
              id="material-descricao"
              rows={4}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              className="w-full rounded-md border border-border bg-paper px-3 py-2 text-sm focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition resize-y"
              placeholder="O que é, para quando, como usar."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="material-link" className={LABEL_CLASS}>
              Link (opcional)
            </Label>
            <Input
              id="material-link"
              type="url"
              maxLength={500}
              value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://..."
            />
            <p className="text-xs text-sepia">
              Começa com http:// ou https://. Arquivos: suba no Drive e cole o
              link de compartilhamento.
            </p>
          </div>
        </div>

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
          <Button type="button" onClick={salvar} disabled={enviando}>
            {enviando ? "Salvando..." : editando ? "Salvar" : "Publicar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
