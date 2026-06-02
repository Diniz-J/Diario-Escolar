import axios from "axios";
import { useEffect, useState, type FormEvent } from "react";

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
import { useTurmas } from "@/features/turmas/hooks";
import type { Aluno, AlunoInput } from "@/types/api";

import { useCreateAluno, useUpdateAluno } from "./hooks";

interface AlunoFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Quando fornecido, abre em modo edição. Caso contrário, modo criação.
  aluno?: Aluno | null;
}

// Form de criação/edição de aluno em modal. A escola é derivada
// automaticamente da turma escolhida — o usuário nunca precisa
// selecionar escola (e o backend valida `aluno.escola == turma.escola`).
export function AlunoFormDialog({
  open,
  onOpenChange,
  aluno,
}: AlunoFormDialogProps) {
  const { user } = useAuth();
  // Quando o usuário tem escola no perfil, o backend deduz — omitimos
  // `escola` do payload. Admin global envia derivada da turma.
  const escolaAuto = user?.escola_id ?? null;
  const turmasQuery = useTurmas();
  const createMutation = useCreateAluno();
  const updateMutation = useUpdateAluno();

  const editando = aluno != null;

  const [matricula, setMatricula] = useState("");
  const [nomeCompleto, setNomeCompleto] = useState("");
  const [dataNascimento, setDataNascimento] = useState("");
  const [turmaId, setTurmaId] = useState<string>("");
  const [ativo, setAtivo] = useState(true);
  const [nomeResponsavel, setNomeResponsavel] = useState("");
  const [emailResponsavel, setEmailResponsavel] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  // Repreenche o formulário quando abre em modo edição.
  useEffect(() => {
    if (open) {
      setErro(null);
      if (aluno) {
        setMatricula(aluno.matricula);
        setNomeCompleto(aluno.nome_completo);
        setDataNascimento(aluno.data_nascimento ?? "");
        setTurmaId(String(aluno.turma));
        setAtivo(aluno.ativo);
        setNomeResponsavel(aluno.nome_responsavel ?? "");
        setEmailResponsavel(aluno.email_responsavel ?? "");
      } else {
        setMatricula("");
        setNomeCompleto("");
        setDataNascimento("");
        setTurmaId("");
        setAtivo(true);
        setNomeResponsavel("");
        setEmailResponsavel("");
      }
    }
  }, [open, aluno]);

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    const turma = turmasQuery.data?.find((t) => String(t.id) === turmaId);
    if (!turma) {
      setErro("Selecione uma turma.");
      return;
    }

    const payload: AlunoInput = {
      // `escola` omitida quando o usuário tem escola no perfil — backend
      // deduz via `AutoEscopoEscolaMixin`. Admin global envia derivado
      // da turma (invariante: aluno.escola == turma.escola).
      ...(escolaAuto == null ? { escola: turma.escola } : {}),
      turma: turma.id,
      matricula,
      nome_completo: nomeCompleto,
      data_nascimento: dataNascimento || null,
      ativo,
      nome_responsavel: nomeResponsavel,
      email_responsavel: emailResponsavel,
    };

    try {
      if (editando && aluno) {
        await updateMutation.mutateAsync({ id: aluno.id, patch: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
      onOpenChange(false);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        // Backend devolve { campo: ["mensagem"] }. Pega a primeira
        // mensagem de qualquer campo pra mostrar inline.
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {editando ? "Editar aluno" : "Novo aluno"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize os dados do aluno."
              : "Preencha os dados para cadastrar um aluno."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="matricula">Matrícula</Label>
            <Input
              id="matricula"
              required
              value={matricula}
              onChange={(e) => setMatricula(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="nome">Nome completo</Label>
            <Input
              id="nome"
              required
              value={nomeCompleto}
              onChange={(e) => setNomeCompleto(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="data_nascimento">Data de nascimento</Label>
            <Input
              id="data_nascimento"
              type="date"
              value={dataNascimento}
              onChange={(e) => setDataNascimento(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label>Turma</Label>
            <Select value={turmaId} onValueChange={setTurmaId}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione uma turma" />
              </SelectTrigger>
              <SelectContent>
                {turmasQuery.data?.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.nome} — {t.turno_display} {t.ano_letivo}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="nome_responsavel">Nome do responsável</Label>
            <Input
              id="nome_responsavel"
              required
              value={nomeResponsavel}
              onChange={(e) => setNomeResponsavel(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="email_responsavel">E-mail do responsável</Label>
            <Input
              id="email_responsavel"
              type="email"
              required
              value={emailResponsavel}
              onChange={(e) => setEmailResponsavel(e.target.value)}
              placeholder="recebe as notificações de ocorrência"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              id="ativo"
              type="checkbox"
              checked={ativo}
              onChange={(e) => setAtivo(e.target.checked)}
              className="rounded border-input"
            />
            <Label htmlFor="ativo" className="cursor-pointer">
              Aluno ativo
            </Label>
          </div>

          {erro && (
            <Alert variant="destructive">
              <AlertDescription>{erro}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={enviando}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando}>
              {enviando ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
