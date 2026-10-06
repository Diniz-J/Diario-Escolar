import axios from "axios";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { portalApi } from "@/features/portal/api";

/**
 * Tela que o link do email abre — serve ao convite E à redefinição.
 *
 * O backend usa o mesmo `ConviteResponsavel` nas duas finalidades, então
 * uma tela só: o pai não precisa saber a diferença, e duas telas iguais
 * divergiriam com o tempo.
 */
export function DefinirSenhaPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") ?? "";

  const [senha, setSenha] = useState("");
  const [confirma, setConfirma] = useState("");
  const [erros, setErros] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErros([]);
    if (senha !== confirma) {
      setErros(["As duas senhas não são iguais."]);
      return;
    }
    setEnviando(true);
    try {
      await portalApi.post("/auth/senha/definir/", { token, password: senha });
      navigate("/portal/entrar", { replace: true, state: { senhaDefinida: true } });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data as Record<string, unknown>;
        // O backend devolve a lista de falhas do validador de senha do
        // Django em `password`, e `detail` quando o link morreu. Mostrar
        // todas ajuda o pai a acertar de primeira.
        const lista = Array.isArray(data.password)
          ? (data.password as string[])
          : typeof data.detail === "string"
            ? [data.detail]
            : [];
        setErros(lista.length ? lista : ["Não foi possível definir a senha."]);
      } else {
        setErros(["Não foi possível definir a senha."]);
      }
    } finally {
      setEnviando(false);
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-sm space-y-4">
          <Alert variant="destructive">
            <AlertDescription>
              Link inválido: falta o código. Abra o link do email exatamente
              como ele chegou, ou peça um novo.
            </AlertDescription>
          </Alert>
          <Link
            to="/portal/esqueci-senha"
            className="block text-sm text-center underline text-muted-foreground"
          >
            Pedir um link novo
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-3">
          <h1 className="font-heading text-[26px] tracking-tight text-tinta leading-[1.15]">
            Definir senha
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground">
            Escolha a senha de acesso ao portal.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label
              htmlFor="senha"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Nova senha
            </Label>
            <Input
              id="senha"
              type="password"
              autoComplete="new-password"
              required
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="confirma"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Repita a senha
            </Label>
            <Input
              id="confirma"
              type="password"
              autoComplete="new-password"
              required
              value={confirma}
              onChange={(e) => setConfirma(e.target.value)}
            />
          </div>

          {erros.length > 0 && (
            <Alert variant="destructive">
              <AlertDescription>
                <ul className="space-y-1">
                  {erros.map((msg) => (
                    <li key={msg}>{msg}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          <Button type="submit" className="w-full" disabled={enviando}>
            {enviando ? "Salvando..." : "Salvar senha"}
          </Button>
        </form>
      </div>
    </div>
  );
}
