import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/features/auth/useAuth";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useProfessores } from "@/features/professores/hooks";
import { UsuarioFormDialog } from "@/features/usuarios/UsuarioFormDialog";
import {
  PERFIL_BADGE,
  PERFIL_LABEL,
} from "@/features/usuarios/constants";
import {
  useAtivacaoUsuario,
  useEnviarResetSenha,
  useUsuarios,
} from "@/features/usuarios/hooks";
import type { Usuario } from "@/types/api";

export function UsuariosPage() {
  const { user } = useAuth();
  const { podeModificarCadastros } = usePermissoes();
  const [busca, setBusca] = useState("");
  const [mostrarInativos, setMostrarInativos] = useState(false);
  const [editando, setEditando] = useState<Usuario | null>(null);
  const [criando, setCriando] = useState(false);
  // Remonta o dialog a cada abertura, pra o estado nascer dos props.
  const [formKey, setFormKey] = useState(0);

  const usuariosQuery = useUsuarios();
  // Resolve quem tem ficha de professor, pra o ⋯ linkar pra lá. SEM
  // filtro de `ativo`: um professor desativado ainda tem ficha, e o item
  // sumir do menu faria parecer que a ficha deixou de existir.
  const professoresQuery = useProfessores();
  const ativacao = useAtivacaoUsuario();
  const enviarReset = useEnviarResetSenha();

  const professorPorUsuario = new Map(
    (professoresQuery.data ?? []).map((p) => [p.usuario, p.id]),
  );

  const termo = busca.trim().toLowerCase();
  const usuarios = (usuariosQuery.data ?? [])
    .filter((u) => u.is_active !== mostrarInativos)
    .filter((u) =>
      termo === ""
        ? true
        : [u.username, u.email, u.first_name, u.last_name]
            .join(" ")
            .toLowerCase()
            .includes(termo),
    );

  function abrirNovo() {
    setEditando(null);
    setFormKey((k) => k + 1);
    setCriando(true);
  }

  function abrirEdicao(usuario: Usuario) {
    setEditando(usuario);
    setFormKey((k) => k + 1);
    setCriando(true);
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] font-mono text-sepia">
            Acesso
          </p>
          <h1 className="font-heading text-2xl md:text-3xl text-tinta">
            Usuários
          </h1>
          <div className="h-px w-16 bg-ferrugem mt-2" />
          <p className="text-sm text-muted-foreground mt-3">
            Contas de quem opera o sistema. Responsáveis têm tela própria.
          </p>
        </div>
        {podeModificarCadastros && (
          <Button onClick={abrirNovo}>Novo usuário</Button>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Buscar por nome, usuário ou email"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="sm:max-w-xs"
        />
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <Switch
            checked={mostrarInativos}
            onCheckedChange={setMostrarInativos}
            aria-label="Mostrar inativos"
          />
          Mostrar inativos
        </label>
      </div>

      {usuariosQuery.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : usuariosQuery.isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar os usuários.
        </p>
      ) : usuarios.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {mostrarInativos
            ? "Nenhum usuário inativo."
            : "Nenhum usuário encontrado."}
        </p>
      ) : (
        <div className="rounded-lg border border-border bg-paper">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead className="hidden sm:table-cell">Usuário</TableHead>
                <TableHead className="hidden md:table-cell">Email</TableHead>
                <TableHead>Perfil</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {usuarios.map((u) => {
                const professorId = professorPorUsuario.get(u.id);
                const souEu = u.id === user?.user_id;
                return (
                  <TableRow key={u.id} className={u.is_active ? "" : "opacity-60"}>
                    <TableCell>
                      <span className="font-medium">
                        {[u.first_name, u.last_name].filter(Boolean).join(" ") ||
                          u.username}
                      </span>
                      {!u.is_active && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          [ inativo ]
                        </span>
                      )}
                      {/* Conta criada e ainda não ativada: sem isto a
                          secretaria não distingue quem nunca entrou de
                          quem usa o sistema, e reenvia link a esmo. */}
                      {u.is_active && !u.senha_definida && (
                        <span className="ml-2 rounded-full bg-mostarda px-2 py-0.5 text-xs text-ambar">
                          aguardando senha
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-muted-foreground">
                      {u.username}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-muted-foreground">
                      {u.email}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex whitespace-nowrap items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          PERFIL_BADGE[u.perfil] ?? "bg-muted"
                        }`}
                      >
                        {PERFIL_LABEL[u.perfil] ?? u.perfil}
                      </span>
                    </TableCell>
                    <TableCell>
                      {podeModificarCadastros && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              aria-label={`Ações de ${u.username}`}
                            >
                              ⋯
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => abrirEdicao(u)}>
                              Editar
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => enviarReset.mutate(u.id)}
                            >
                              Enviar link de senha
                            </DropdownMenuItem>
                            {/* A ficha do professor é a dona do que é
                                específico de docente (lecionamentos,
                                diário). Linkar em vez de duplicar evita
                                duas verdades sobre a mesma pessoa. */}
                            {professorId != null && (
                              <DropdownMenuItem asChild>
                                <Link to={`/professores/${professorId}`}>
                                  Ver ficha do professor
                                </Link>
                              </DropdownMenuItem>
                            )}
                            {/* O backend recusa desativar a própria conta
                                (auto-tranco); esconder o item evita
                                oferecer o que só devolve 400. */}
                            {!souEu && (
                              <DropdownMenuItem
                                onClick={() =>
                                  ativacao.mutate({
                                    id: u.id,
                                    ativo: !u.is_active,
                                  })
                                }
                              >
                                {u.is_active ? "Desativar" : "Reativar"}
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <UsuarioFormDialog
        key={formKey}
        open={criando}
        onOpenChange={setCriando}
        usuario={editando}
      />
    </div>
  );
}
