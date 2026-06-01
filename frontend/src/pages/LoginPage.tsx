import axios from "axios";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";

// Login repaginado — vibe "profissional caloroso" (B), paleta olive/linho.
//
// Decisões visuais conscientes (vivem inline aqui em vez dos tokens
// globais porque ainda estamos validando a direção; quando aprovada,
// migram pra CSS variables em `index.css`):
//
//   olive  #4D5A2E  — cor primária (CTA, marca, filete)
//   linho  #EBE2D1  — fundo (papel)
//   ferrugem #B07D62 — accent quente (filete decorativo)
//   tinta  #2D2A24  — texto principal (não preto puro)
//   sepia  #6B6859  — texto secundário
//
// A tela ignora o `<html class="dark">` permanente do app — login é a
// porta de entrada e funciona melhor com palete clara. O resto do app
// continua dark até decidirmos repaginar.
//
// Tipografia: título usa `font-heading` (Fraunces variable, italic) +
// peso 400 pra ar editorial sem peso visual; resto fica em Geist.

const PALETA = {
  olive: "#4D5A2E",
  oliveDark: "#3D4A1F",
  linho: "#EBE2D1",
  ferrugem: "#B07D62",
  tinta: "#2D2A24",
  sepia: "#6B6859",
  border: "#D9CFB8",
  inputBg: "#F5EFE0",
} as const;

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await login({ username, password });
      const from =
        (location.state as { from?: { pathname: string } } | null)?.from
          ?.pathname ?? "/dashboard";
      navigate(from, { replace: true });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setErro("Usuário ou senha inválidos.");
      } else {
        setErro("Não foi possível entrar. Tente novamente.");
        console.error(err);
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: PALETA.linho, color: PALETA.tinta }}
    >
      <div className="w-full max-w-lg">
        {/* Microtípico no topo — substitui o "logo" enquanto não há marca. */}
        <p
          className="text-[11px] uppercase tracking-[0.25em] mb-10"
          style={{ color: PALETA.olive }}
        >
          · diário diniz
        </p>

        {/* Título serif regular (sem italic — Fraunces já tem personalidade
            suficiente em peso médio). Tamanho contido pra não dominar
            visualmente a tela: o foco é o form, o título dá o tom. */}
        <h1
          className="font-heading mb-2 leading-[1.2] text-[26px] md:text-[30px] tracking-tight"
          style={{ color: PALETA.tinta, fontWeight: 500 }}
        >
          Que bom te ver de volta.
        </h1>

        <p
          className="text-sm mb-7"
          style={{ color: PALETA.sepia }}
        >
          Continue de onde parou.
        </p>

        {/* Filete ferrugem — detalhe memorável (`encadernação`). */}
        <div
          className="h-px w-12 mb-10"
          style={{ background: PALETA.ferrugem }}
        />

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label
              htmlFor="username"
              className="block text-[11px] uppercase tracking-[0.18em]"
              style={{ color: PALETA.sepia }}
            >
              Usuário
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2.5 text-base rounded-md focus:outline-none focus:ring-2 transition"
              style={{
                background: PALETA.inputBg,
                border: `1px solid ${PALETA.border}`,
                color: PALETA.tinta,
                // Foco em ferrugem (anel) — testando accent quente como pediu.
                outline: "none",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = PALETA.ferrugem;
                e.currentTarget.style.boxShadow = `0 0 0 3px ${PALETA.ferrugem}33`;
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = PALETA.border;
                e.currentTarget.style.boxShadow = "none";
              }}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <label
                htmlFor="password"
                className="block text-[11px] uppercase tracking-[0.18em]"
                style={{ color: PALETA.sepia }}
              >
                Senha
              </label>
              <button
                type="button"
                className="text-xs hover:underline"
                style={{ color: PALETA.ferrugem }}
                onClick={() => {
                  /* Reset por email entra depois (FASE 4); por ora vira no-op. */
                }}
              >
                Esqueci a senha
              </button>
            </div>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2.5 text-base rounded-md focus:outline-none transition"
              style={{
                background: PALETA.inputBg,
                border: `1px solid ${PALETA.border}`,
                color: PALETA.tinta,
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = PALETA.ferrugem;
                e.currentTarget.style.boxShadow = `0 0 0 3px ${PALETA.ferrugem}33`;
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = PALETA.border;
                e.currentTarget.style.boxShadow = "none";
              }}
            />
          </div>

          {erro && (
            <p
              className="text-sm px-3 py-2 rounded-md"
              style={{
                background: "#F4DAD3",
                color: "#7C2D1A",
                border: "1px solid #E9B8AB",
              }}
            >
              {erro}
            </p>
          )}

          <button
            type="submit"
            disabled={enviando}
            className="w-full py-3 text-base font-medium rounded-md transition disabled:opacity-60 disabled:cursor-not-allowed"
            style={{
              background: PALETA.olive,
              color: PALETA.linho,
            }}
            onMouseEnter={(e) => {
              if (!enviando)
                e.currentTarget.style.background = PALETA.oliveDark;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = PALETA.olive;
            }}
          >
            {enviando ? "Acessando..." : "Acessar →"}
          </button>
        </form>

        {/* Rodapé sutil — versão + paleta. */}
        <div
          className="mt-12 flex items-center gap-2 text-[11px]"
          style={{ color: PALETA.sepia }}
        >
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ background: PALETA.olive }}
          />
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ background: PALETA.ferrugem }}
          />
          <span>v1.0 · Diário Diniz</span>
        </div>
      </div>
    </div>
  );
}
