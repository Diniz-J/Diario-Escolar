import axios from "axios";
import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePortalAuth } from "@/features/portal/usePortalAuth";

export function EntrarPage() {
  const { entrar } = usePortalAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(email, senha);
      // Volta pra onde o pai tentou ir antes do portão, se houver.
      const de = (location.state as { de?: { pathname: string } } | null)?.de;
      navigate(de?.pathname ?? "/portal", { replace: true });
    } catch (err) {
      if (axios.isAxiosError(err)) {
        // 409 = mesmo email com acesso em duas escolas. A mensagem do
        // backend é específica e útil, então passa adiante; o resto cai no
        // texto genérico (o backend não diferencia email inexistente de
        // senha errada, de propósito).
        setErro(
          err.response?.data?.detail ?? "Não foi possível entrar. Tente de novo.",
        );
      } else {
        setErro("Não foi possível entrar. Tente de novo.");
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-sepia">
            Diário Diniz
          </p>
          <h1 className="font-heading text-[26px] md:text-[30px] tracking-tight text-tinta leading-[1.15]">
            Portal do responsável
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground">
            Acompanhe comunicados, boletim e ocorrências dos seus filhos.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label
              htmlFor="email"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Email
            </Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="senha"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Senha
            </Label>
            <Input
              id="senha"
              type="password"
              autoComplete="current-password"
              required
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
            />
          </div>

          {erro && (
            <Alert variant="destructive">
              <AlertDescription>{erro}</AlertDescription>
            </Alert>
          )}

          <Button type="submit" className="w-full" disabled={enviando}>
            {enviando ? "Entrando..." : "Entrar"}
          </Button>
        </form>

        <Link
          to="/portal/esqueci-senha"
          className="block text-sm text-center underline text-muted-foreground"
        >
          Esqueci minha senha
        </Link>
      </div>
    </div>
  );
}
