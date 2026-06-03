import axios from "axios";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/useAuth";
import { useRequestOwnPasswordChange } from "@/features/auth/passwordHooks";

// Página /conta/senha — protegida.
// Botão único "Enviar link" — usa o email do usuário autenticado (do JWT)
// pra mandar o link de redefinição. Mesmo fluxo do reset, sem precisar
// digitar username.
export function ContaSenhaPage() {
  const { user } = useAuth();
  const mutation = useRequestOwnPasswordChange();
  const [erro, setErro] = useState<string | null>(null);
  const [emailAlvo, setEmailAlvo] = useState<string | null>(null);

  async function handleEnviar() {
    setErro(null);
    try {
      const resp = await mutation.mutateAsync();
      setEmailAlvo(resp.email ?? null);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data as Record<string, unknown>;
        const detail =
          typeof data.detail === "string" ? data.detail : undefined;
        setErro(detail ?? "Não foi possível enviar o link.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  const nome = user?.first_name || user?.username || "";

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-2xl">
      <header className="space-y-3">
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          Trocar minha senha
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
      </header>

      <div className="bg-paper rounded-lg border border-border p-6 space-y-5">
        {emailAlvo ? (
          <>
            <p className="text-sm">
              Enviamos um link de redefinição para{" "}
              <strong>{emailAlvo}</strong>. O link é válido por 1 hora.
            </p>
            <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Verifique também a pasta de spam.
            </p>
          </>
        ) : (
          <>
            <p className="text-sm">
              {nome ? `Olá, ${nome}. ` : ""}Pra trocar sua senha, vamos
              enviar um link pro email cadastrado no seu perfil.
            </p>
            <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Sem senha atual — você define a nova diretamente pelo link.
            </p>

            {erro && (
              <p className="text-sm px-3 py-2 rounded-md bg-destructive/15 text-destructive border border-destructive/30">
                {erro}
              </p>
            )}

            <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-end pt-2">
              <Button asChild variant="ghost">
                <Link to="/dashboard">Cancelar</Link>
              </Button>
              <Button
                type="button"
                onClick={handleEnviar}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? "Enviando..." : "Enviar link"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
