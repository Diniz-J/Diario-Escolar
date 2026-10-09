import axios from "axios";
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

import { useCriarResponsavel } from "./hooks";

interface NovoResponsavelDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Cadastro de conta de responsável.
 *
 * É o que permite o segundo responsável (mãe e pai) sem passar pelo
 * `/admin/`: a semeadura cria uma conta por família, derivada do campo de
 * email do aluno. Ver `RESPONSAVEIS.md` §1.
 *
 * A conta nasce **sem senha utilizável** — cadastrar não dá acesso a
 * nada. O acesso vem do convite, que é a ação seguinte na própria
 * listagem (a conta aparece como "Sem convite").
 */
export function NovoResponsavelDialog({
  open,
  onOpenChange,
}: NovoResponsavelDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {/* O formulário é um componente próprio de propósito: o
            `DialogContent` do Radix desmonta ao fechar, então o estado
            nasce limpo a cada abertura sem um `useEffect` que chama
            `setState` (regra `react-hooks/set-state-in-effect`, o mesmo
            achado que o CR da 6b pagou na paginação desta tela). */}
        <Formulario onPronto={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function Formulario({ onPronto }: { onPronto: () => void }) {
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();
  const criar = useCriarResponsavel();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [escolaId, setEscolaId] = useState<string>("");
  const [erro, setErro] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      await criar.mutateAsync({
        nome: nome.trim(),
        email: email.trim(),
        // Só o admin global manda escola; os outros perfis o backend
        // deduz pelo JWT e o select nem aparece.
        ...(ehAdminGlobal && escolaId ? { escola: Number(escolaId) } : {}),
      });
      onPronto();
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        // Erro por campo: `{email: ["..."]}` quando o email já existe na
        // escola, `{escola: ["..."]}` no guard de escola alheia.
        const data = err.response.data as Record<string, unknown>;
        const primeira = Object.values(data)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeira ?? "Não foi possível cadastrar.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  return (
    <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="font-heading">
              Novo responsável
            </DialogTitle>
            <DialogDescription>
              A conta nasce sem acesso. Depois de cadastrar, use Convidar
              para enviar o link de definição de senha.
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
                htmlFor="responsavel-nome"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Nome
              </Label>
              <Input
                id="responsavel-nome"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
                maxLength={200}
              />
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="responsavel-email"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Email
              </Label>
              <Input
                id="responsavel-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                É por este endereço que o convite sai e com ele que o
                responsável entra no portal.
              </p>
            </div>

            {ehAdminGlobal && (
              <div className="space-y-2">
                <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                  Escola
                </Label>
                <Select value={escolaId} onValueChange={setEscolaId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Escolha a escola..." />
                  </SelectTrigger>
                  <SelectContent>
                    {(escolasQuery.data ?? []).map((e) => (
                      <SelectItem key={e.id} value={String(e.id)}>
                        {e.nome}
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
              onClick={onPronto}
              disabled={criar.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={criar.isPending}>
              {criar.isPending ? "Cadastrando..." : "Cadastrar"}
            </Button>
          </DialogFooter>
    </form>
  );
}
