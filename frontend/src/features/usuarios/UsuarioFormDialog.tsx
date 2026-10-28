import { useState, type FormEvent } from "react";

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
import { useEscolas } from "@/features/escolas/hooks";
import type { Perfil } from "@/features/auth/types";
import type { Usuario, UsuarioInput } from "@/types/api";

import { opcoesDePerfil } from "./constants";
import { mensagemDeErro, useCreateUsuario, useUpdateUsuario } from "./hooks";

interface UsuarioFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  usuario?: Usuario | null;
}

export function UsuarioFormDialog({
  open,
  onOpenChange,
  usuario,
}: UsuarioFormDialogProps) {
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();
  const createMutation = useCreateUsuario();
  const updateMutation = useUpdateUsuario();

  const editando = usuario != null;

  // Estado nasce dos props; a página remonta o dialog (`key={formKey}`)
  // a cada abertura, então não há efeito repreenchendo campo.
  const [username, setUsername] = useState(usuario?.username ?? "");
  const [email, setEmail] = useState(usuario?.email ?? "");
  const [firstName, setFirstName] = useState(usuario?.first_name ?? "");
  const [lastName, setLastName] = useState(usuario?.last_name ?? "");
  const [perfil, setPerfil] = useState<string>(usuario?.perfil ?? "professor");
  const [escolaId, setEscolaId] = useState(
    usuario?.escola != null ? String(usuario.escola) : "",
  );
  const [erro, setErro] = useState("");

  const escolas = escolasQuery.data ?? [];
  // Mesma derivação dos outros dialogs: a lista chega depois do mount, e
  // sincronizá-la por efeito é o que a regra `set-state-in-effect` acusa.
  const escolaEfetiva =
    escolaId || (escolas.length === 1 ? String(escolas[0].id) : "");

  const perfisDisponiveis = opcoesDePerfil(ehAdminGlobal);

  const salvando = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro("");

    const payload: UsuarioInput = {
      username: username.trim(),
      email: email.trim(),
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      perfil: perfil as Perfil,
    };
    if (ehAdminGlobal && escolaEfetiva) {
      payload.escola = Number(escolaEfetiva);
    }

    try {
      if (editando) {
        // `perfil` só vai quando mudou: mandá-lo sempre faria a edição da
        // própria conta levar 400 do guard de autoalteração, mesmo quando
        // a pessoa só quis corrigir o próprio sobrenome.
        const patch: Partial<UsuarioInput> = { ...payload };
        if (perfil === usuario.perfil) delete patch.perfil;
        if (!ehAdminGlobal) delete patch.escola;
        await updateMutation.mutateAsync({ id: usuario.id, patch });
      } else {
        // Sem `password`: a conta nasce sem senha utilizável e o acesso
        // chega pelo link de redefinição, que vai pro email do próprio
        // dono. Quem cadastra nunca escolhe nem vê a senha de ninguém.
        await createMutation.mutateAsync(payload);
      }
      onOpenChange(false);
    } catch (err) {
      // O texto do backend é a UI: é ele que nomeia a invariante
      // ("Apenas um administrador pode criar ou promover conta com este
      // perfil", "username já existe").
      setErro(mensagemDeErro(err, "Não foi possível salvar o usuário."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="font-heading">
              {editando ? "Editar usuário" : "Novo usuário"}
            </DialogTitle>
            <DialogDescription>
              {editando
                ? "Altere os dados de acesso desta conta."
                : "A conta nasce sem senha. Use “Enviar link de senha” para que a pessoa defina a dela."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {erro && (
              <Alert variant="destructive">
                <AlertDescription>{erro}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label
                htmlFor="username"
                className="text-xs uppercase tracking-wider font-mono"
              >
                Usuário
              </Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label
                  htmlFor="first_name"
                  className="text-xs uppercase tracking-wider font-mono"
                >
                  Nome
                </Label>
                <Input
                  id="first_name"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label
                  htmlFor="last_name"
                  className="text-xs uppercase tracking-wider font-mono"
                >
                  Sobrenome
                </Label>
                <Input
                  id="last_name"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="email"
                className="text-xs uppercase tracking-wider font-mono"
              >
                Email
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                É para cá que vai o link de definição de senha.
              </p>
            </div>

            <div className="space-y-2">
              <Label className="text-xs uppercase tracking-wider font-mono">
                Perfil
              </Label>
              <Select value={perfil} onValueChange={setPerfil}>
                <SelectTrigger aria-label="Perfil">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {perfisDisponiveis.map((opcao) => (
                    <SelectItem key={opcao.value} value={opcao.value}>
                      {opcao.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Só o admin global escolhe escola; para o resto o backend
                deduz pelo JWT (padrão de auto-escopo dos FormDialogs). */}
            {ehAdminGlobal && (
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-wider font-mono">
                  Escola
                </Label>
                <Select value={escolaEfetiva} onValueChange={setEscolaId}>
                  <SelectTrigger aria-label="Escola">
                    <SelectValue placeholder="Selecione" />
                  </SelectTrigger>
                  <SelectContent>
                    {escolas.map((escola) => (
                      <SelectItem key={escola.id} value={String(escola.id)}>
                        {escola.nome}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={salvando}>
              {salvando ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
