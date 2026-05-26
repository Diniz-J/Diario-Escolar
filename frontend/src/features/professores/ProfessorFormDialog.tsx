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
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useEscolas } from "@/features/escolas/hooks";
import { useCreateUsuario, useUpdateUsuario } from "@/features/usuarios/hooks";
import type { Professor } from "@/types/api";

import { useCreateProfessor, useProfessores, useUpdateProfessor } from "./hooks";

interface ProfessorFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // `null` ou ausente = modo criar. Objeto = modo editar.
  professor?: Professor | null;
}

// Form unificado para criar/editar professor.
//
// Criar: dispara 2 requests em sequência:
//   1. POST /usuarios/ com perfil=professor + escola + password
//   2. POST /professores/ com usuario.id + disciplinas
// Se o segundo falhar, o Usuario órfão fica no banco (cleanup manual via
// Admin é aceitável pra um app escolar interno).
//
// Editar: também 2 requests, agora PATCH em /usuarios/:id (nome/email) e
// PATCH em /professores/:id (disciplinas, ativo).
export function ProfessorFormDialog({
  open,
  onOpenChange,
  professor,
}: ProfessorFormDialogProps) {
  const escolasQuery = useEscolas();
  const disciplinasQuery = useDisciplinas();
  const professoresQuery = useProfessores();

  const createUsuario = useCreateUsuario();
  const createProfessor = useCreateProfessor();
  const updateUsuario = useUpdateUsuario();
  const updateProfessor = useUpdateProfessor();

  const editando = professor != null;

  const [escolaId, setEscolaId] = useState<string>("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [disciplinasSel, setDisciplinasSel] = useState<number[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  // Hidrata o form quando abre. No modo edição precisamos pegar o Usuario
  // vinculado — mas o Professor não traz username/email, só `nome_completo`.
  // Estratégia: pegamos first_name/last_name via split do nome_completo. O
  // username/email só aparecem editáveis se o backend devolver — por
  // simplicidade nessa fase, edição mexe só em disciplinas e ativo.
  useEffect(() => {
    if (!open) return;
    setErro(null);
    if (professor) {
      const partes = professor.nome_completo.split(" ");
      setFirstName(partes[0] ?? "");
      setLastName(partes.slice(1).join(" "));
      setEscolaId(String(professor.escola));
      setUsername("");
      setEmail("");
      setPassword("");
      setDisciplinasSel([...professor.disciplinas]);
    } else {
      const escolas = escolasQuery.data;
      setEscolaId(escolas?.length === 1 ? String(escolas[0].id) : "");
      setFirstName("");
      setLastName("");
      setUsername("");
      setEmail("");
      setPassword("");
      setDisciplinasSel([]);
    }
  }, [open, professor, escolasQuery.data]);

  const enviando =
    createUsuario.isPending ||
    createProfessor.isPending ||
    updateUsuario.isPending ||
    updateProfessor.isPending;

  const mostrarEscolaSelect = (escolasQuery.data?.length ?? 0) > 1;

  function toggleDisciplina(id: number) {
    setDisciplinasSel((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    );
  }

  function extrairPrimeiraMsgErro(err: unknown): string {
    if (axios.isAxiosError(err) && err.response?.data) {
      const data = err.response.data as Record<string, unknown>;
      const valores = Object.values(data).flat();
      const primeira = valores.find(
        (v): v is string => typeof v === "string",
      );
      if (primeira) return primeira;
    }
    return "Erro inesperado.";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (!escolaId) {
      setErro("Selecione uma escola.");
      return;
    }
    const escolaIdNum = parseInt(escolaId, 10);

    try {
      if (editando && professor) {
        // Edição: PATCH no Usuario vinculado (nome) e no Professor (disciplinas/ativo).
        await updateUsuario.mutateAsync({
          id: professor.usuario,
          patch: { first_name: firstName, last_name: lastName },
        });
        await updateProfessor.mutateAsync({
          id: professor.id,
          patch: { disciplinas: disciplinasSel },
        });
      } else {
        if (!username.trim() || !password) {
          setErro("Preencha usuário e senha.");
          return;
        }
        const usuario = await createUsuario.mutateAsync({
          username: username.trim(),
          email: email.trim(),
          first_name: firstName,
          last_name: lastName,
          perfil: "professor",
          escola: escolaIdNum,
          password,
        });
        await createProfessor.mutateAsync({
          escola: escolaIdNum,
          usuario: usuario.id,
          disciplinas: disciplinasSel,
        });
      }
      onOpenChange(false);
    } catch (err) {
      setErro(extrairPrimeiraMsgErro(err));
      if (!axios.isAxiosError(err)) console.error(err);
    }
  }

  // Username conflict hint: avisa antes de submeter quando o usuário já
  // existe entre os professores listados. Só uma camada de UX — o backend
  // tem o unique constraint real.
  const usernameJaUsado =
    !editando &&
    username.trim().length > 0 &&
    (professoresQuery.data ?? []).some(
      (p) =>
        // Não temos username no Professor; só impedimos colisão óbvia
        // pelo `nome_completo` exato com mesmo primeiro/último nome.
        p.nome_completo.toLowerCase() ===
        `${firstName} ${lastName}`.trim().toLowerCase(),
    );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {editando ? "Editar professor" : "Novo professor"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize nome e disciplinas que leciona."
              : "Cadastre o professor e seu acesso ao sistema."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="first-name">Nome</Label>
              <Input
                id="first-name"
                required
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="last-name">Sobrenome</Label>
              <Input
                id="last-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
          </div>

          {!editando && (
            <>
              <div className="space-y-2">
                <Label htmlFor="username">Usuário (login)</Label>
                <Input
                  id="username"
                  required
                  autoComplete="off"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="ex.: maria.silva"
                />
                {usernameJaUsado && (
                  <p className="text-xs text-amber-700 dark:text-amber-400">
                    Já existe um professor com esse nome — confirme se é o mesmo
                    antes de prosseguir.
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">E-mail</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="opcional"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Senha</Label>
                <Input
                  id="password"
                  type="password"
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Mínimo 8 caracteres"
                />
              </div>
            </>
          )}

          {mostrarEscolaSelect && (
            <div className="space-y-2">
              <Label htmlFor="escola">Escola</Label>
              <select
                id="escola"
                value={escolaId}
                onChange={(e) => setEscolaId(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Selecione uma escola</option>
                {escolasQuery.data?.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.nome}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="space-y-2">
            <Label>Disciplinas que leciona</Label>
            <div className="max-h-48 overflow-y-auto rounded-md border border-input p-3 space-y-1.5">
              {disciplinasQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">Carregando...</p>
              ) : (disciplinasQuery.data?.length ?? 0) === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nenhuma disciplina cadastrada.
                </p>
              ) : (
                disciplinasQuery.data?.map((d) => (
                  <label
                    key={d.id}
                    className="flex items-center gap-2 text-sm cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={disciplinasSel.includes(d.id)}
                      onChange={() => toggleDisciplina(d.id)}
                      className="rounded border-input"
                    />
                    {d.nome}
                  </label>
                ))
              )}
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
