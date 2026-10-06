import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { portalApi } from "@/features/portal/api";

export function EsqueciSenhaPage() {
  const [email, setEmail] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    try {
      await portalApi.post("/auth/senha/esqueci/", { email });
    } catch {
      // Silencioso de propósito: o backend responde igual pra email que
      // existe e pra que não existe (anti-enumeração), e a UI não pode
      // desfazer isso contando que falhou.
    } finally {
      setEnviado(true);
      setEnviando(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-3">
          <h1 className="font-heading text-[26px] tracking-tight text-tinta leading-[1.15]">
            Esqueci minha senha
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
        </div>

        {enviado ? (
          <Alert>
            <AlertDescription>
              Se houver uma conta com esse email, o link de redefinição foi
              enviado. Verifique a caixa de entrada e o spam.
            </AlertDescription>
          </Alert>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label
                htmlFor="email"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Email cadastrado
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
            <Button type="submit" className="w-full" disabled={enviando}>
              {enviando ? "Enviando..." : "Enviar link"}
            </Button>
          </form>
        )}

        <Link
          to="/portal/entrar"
          className="block text-sm text-center underline text-muted-foreground"
        >
          Voltar para entrar
        </Link>
      </div>
    </div>
  );
}
