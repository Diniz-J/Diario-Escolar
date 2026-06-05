import axios from "axios";
import { useEffect, useMemo, useState, type FormEvent } from "react";

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
import { useAuth } from "@/features/auth/useAuth";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useEscolas } from "@/features/escolas/hooks";
import {
  useCreateLecionamento,
  useDeleteLecionamento,
  useLecionamentos,
} from "@/features/lecionamentos/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { useCreateUsuario, useUpdateUsuario } from "@/features/usuarios/hooks";
import type { Professor } from "@/types/api";

import { useCreateProfessor } from "./hooks";

interface ProfessorFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  professor?: Professor | null;
}

// Linha temporária de lecionamento no formulário. `id` só existe quando
// já foi persistido (vindo do servidor) — usado pra diff de exclusão.
interface LinhaLecionamento {
  id: number | null;
  turmaId: string;
  disciplinaId: string;
}

// Form unificado para criar/editar professor. Fluxo:
//
// Criar:
//   1. POST /usuarios/ (perfil=professor, escola, password)
//   2. POST /professores/ (escola, usuario)
//   3. Para cada linha de lecionamento: POST /lecionamentos/
//
// Editar:
//   1. PATCH /usuarios/:id (first_name, last_name)
//   2. Diff dos lecionamentos:
//      - Novos (sem id) → POST
//      - Removidos (estavam no servidor mas saíram da UI) → DELETE
export function ProfessorFormDialog({
  open,
  onOpenChange,
  professor,
}: ProfessorFormDialogProps) {
  const { user } = useAuth();
  const { ehAdminGlobal } = usePermissoes();
  // Select de escola **só** pra `perfil === "admin"`. Outros perfis
  // nunca veem nem mandam — backend deduz a escola via JWT. Gate
  // estrito por perfil pra cobrir edge case "usuário não-admin sem
  // escola_id".
  //
  // `user?.escola_id` continua sendo o VALOR (número) usado na hora de
  // montar o payload pra admin que esquece de selecionar — diferente
  // de `ehAdminGlobal` que é uma flag booleana.
  const escolasQuery = useEscolas();
  const disciplinasQuery = useDisciplinas();
  const turmasQuery = useTurmas();
  const lecionamentosQuery = useLecionamentos(
    professor ? { professor: professor.id } : {},
  );

  const createUsuario = useCreateUsuario();
  const createProfessor = useCreateProfessor();
  const updateUsuario = useUpdateUsuario();
  const createLec = useCreateLecionamento();
  const deleteLec = useDeleteLecionamento();

  const editando = professor != null;

  const [escolaId, setEscolaId] = useState<string>("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [linhas, setLinhas] = useState<LinhaLecionamento[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  // Hidrata o form quando abre. Em edição, espera os lecionamentos do
  // professor carregarem pra popular as linhas.
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
      // Linhas vêm dos lecionamentos persistidos. Se ainda carregando,
      // outro `useEffect` abaixo sincroniza quando chegar.
      setLinhas(
        (lecionamentosQuery.data ?? []).map((l) => ({
          id: l.id,
          turmaId: String(l.turma),
          disciplinaId: String(l.disciplina),
        })),
      );
    } else {
      const escolas = escolasQuery.data;
      setEscolaId(escolas?.length === 1 ? String(escolas[0].id) : "");
      setFirstName("");
      setLastName("");
      setUsername("");
      setEmail("");
      setPassword("");
      setLinhas([]);
    }
  // `lecionamentosQuery.data` propositalmente fora — sync em outro effect.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, professor, escolasQuery.data]);

  // Quando os lecionamentos terminam de carregar no modo edição, popula
  // as linhas iniciais.
  useEffect(() => {
    if (!open || !professor || !lecionamentosQuery.data) return;
    setLinhas(
      lecionamentosQuery.data.map((l) => ({
        id: l.id,
        turmaId: String(l.turma),
        disciplinaId: String(l.disciplina),
      })),
    );
  }, [open, professor, lecionamentosQuery.data]);

  const enviando =
    createUsuario.isPending ||
    createProfessor.isPending ||
    updateUsuario.isPending ||
    createLec.isPending ||
    deleteLec.isPending;

  const mostrarEscolaSelect =
    ehAdminGlobal && (escolasQuery.data?.length ?? 0) > 1;

  // Filtra turmas da escola selecionada — admin com múltiplas escolas
  // não vê turmas de outra ao montar lecionamento.
  const turmasDaEscola = useMemo(() => {
    if (!escolaId) return [];
    const escolaIdNum = parseInt(escolaId, 10);
    return (turmasQuery.data ?? []).filter(
      (t) => t.escola === escolaIdNum && t.ativa,
    );
  }, [escolaId, turmasQuery.data]);

  const disciplinasDaEscola = useMemo(() => {
    if (!escolaId) return [];
    const escolaIdNum = parseInt(escolaId, 10);
    return (disciplinasQuery.data ?? []).filter(
      (d) => d.escola === escolaIdNum && d.ativa,
    );
  }, [escolaId, disciplinasQuery.data]);

  function adicionarLinha() {
    setLinhas((prev) => [...prev, { id: null, turmaId: "", disciplinaId: "" }]);
  }

  function removerLinha(index: number) {
    setLinhas((prev) => prev.filter((_, i) => i !== index));
  }

  function atualizarLinha(
    index: number,
    campo: "turmaId" | "disciplinaId",
    valor: string,
  ) {
    setLinhas((prev) =>
      prev.map((l, i) => (i === index ? { ...l, [campo]: valor } : l)),
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

    // Resolve a escola alvo:
    // - admin global: o que ele selecionou no select de escola
    // - demais perfis: a do JWT (`user.escola_id`); select nem é renderizado
    const escolaIdNum = ehAdminGlobal
      ? (escolaId ? parseInt(escolaId, 10) : NaN)
      : (user?.escola_id ?? NaN);
    if (Number.isNaN(escolaIdNum)) {
      setErro("Selecione uma escola.");
      return;
    }

    // Valida linhas: turma + disciplina obrigatórios em toda linha.
    const linhasValidas = linhas.filter(
      (l) => l.turmaId && l.disciplinaId,
    );

    try {
      let professorIdAlvo: number;

      if (editando && professor) {
        await updateUsuario.mutateAsync({
          id: professor.usuario,
          patch: { first_name: firstName, last_name: lastName },
        });
        professorIdAlvo = professor.id;

        // Diff de lecionamentos:
        const idsAtuais = new Set(
          linhasValidas
            .map((l) => l.id)
            .filter((id): id is number => id !== null),
        );
        const persistidos = lecionamentosQuery.data ?? [];

        // Removidos: estavam no servidor, sumiram da UI.
        for (const l of persistidos) {
          if (!idsAtuais.has(l.id)) {
            await deleteLec.mutateAsync(l.id);
          }
        }
        // Novos: linhas sem id. `escola` deduzida pelo backend quando
        // o user tem escola no perfil.
        for (const linha of linhasValidas) {
          if (linha.id == null) {
            await createLec.mutateAsync({
              ...(ehAdminGlobal ? { escola: escolaIdNum } : {}),
              professor: professorIdAlvo,
              turma: parseInt(linha.turmaId, 10),
              disciplina: parseInt(linha.disciplinaId, 10),
            });
          }
        }
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
        const novoProfessor = await createProfessor.mutateAsync({
          // `escola` omitida quando o user tem escola no perfil — backend deduz.
          ...(ehAdminGlobal ? { escola: escolaIdNum } : {}),
          usuario: usuario.id,
        });
        professorIdAlvo = novoProfessor.id;

        // Cria lecionamentos depois do Professor existir.
        for (const linha of linhasValidas) {
          await createLec.mutateAsync({
            ...(ehAdminGlobal ? { escola: escolaIdNum } : {}),
            professor: professorIdAlvo,
            turma: parseInt(linha.turmaId, 10),
            disciplina: parseInt(linha.disciplinaId, 10),
          });
        }
      }

      onOpenChange(false);
    } catch (err) {
      setErro(extrairPrimeiraMsgErro(err));
      if (!axios.isAxiosError(err)) console.error(err);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar professor" : "Novo professor"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize nome e o que leciona."
              : "Cadastre o professor, seu acesso ao sistema e o que leciona."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label
                htmlFor="first-name"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Nome
              </Label>
              <Input
                id="first-name"
                required
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="last-name"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Sobrenome
              </Label>
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
                <Label
                  htmlFor="username"
                  className="text-[11px] uppercase tracking-[0.18em] text-sepia"
                >
                  Usuário (login)
                </Label>
                <Input
                  id="username"
                  required
                  autoComplete="off"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="ex.: maria.silva"
                />
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="email"
                  className="text-[11px] uppercase tracking-[0.18em] text-sepia"
                >
                  E-mail
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="opcional"
                />
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="password"
                  className="text-[11px] uppercase tracking-[0.18em] text-sepia"
                >
                  Senha
                </Label>
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
              <Label
                htmlFor="escola"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Escola
              </Label>
              <select
                id="escola"
                value={escolaId}
                onChange={(e) => setEscolaId(e.target.value)}
                className="w-full rounded-md border border-border bg-paper px-3 py-2 text-sm focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition"
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
            <div className="flex items-center justify-between">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Lecionamentos (turma + disciplina)
              </Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={adicionarLinha}
                disabled={!escolaId}
              >
                + Adicionar
              </Button>
            </div>
            {linhas.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Nenhum lecionamento. Clique em "+ Adicionar" para vincular o
                professor a uma turma + disciplina.
              </p>
            ) : (
              <div className="space-y-2">
                {linhas.map((linha, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <select
                      value={linha.turmaId}
                      onChange={(e) =>
                        atualizarLinha(idx, "turmaId", e.target.value)
                      }
                      className="flex-1 rounded-md border border-border bg-paper px-3 py-2 text-sm focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition"
                    >
                      <option value="">Turma</option>
                      {turmasDaEscola.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.nome} — {t.ano_letivo}
                        </option>
                      ))}
                    </select>
                    <select
                      value={linha.disciplinaId}
                      onChange={(e) =>
                        atualizarLinha(idx, "disciplinaId", e.target.value)
                      }
                      className="flex-1 rounded-md border border-border bg-paper px-3 py-2 text-sm focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition"
                    >
                      <option value="">Disciplina</option>
                      {disciplinasDaEscola.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.nome}
                        </option>
                      ))}
                    </select>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => removerLinha(idx)}
                      aria-label="Remover lecionamento"
                    >
                      ×
                    </Button>
                  </div>
                ))}
              </div>
            )}
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
            <Button type="submit" disabled={enviando}>
              {enviando ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
