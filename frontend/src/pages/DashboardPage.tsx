import { useMemo, useState } from "react";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAlunos } from "@/features/alunos/hooks";
import { useAuth } from "@/features/auth/useAuth";
import { MetricCard } from "@/features/dashboard/MetricCard";
import { UltimasChamadasCard } from "@/features/dashboard/UltimasChamadasCard";
import { UltimasOcorrenciasCard } from "@/features/dashboard/UltimasOcorrenciasCard";
import { useOcorrencias } from "@/features/ocorrencias/hooks";
import { useTurmas } from "@/features/turmas/hooks";

const PERFIL_LABEL: Record<string, string> = {
  admin: "Administrador",
  diretor: "Diretor",
  professor: "Professor",
  secretaria: "Secretaria",
  inspetor: "Inspetor",
};

// Valor especial do <Select> que representa "sem filtro de turma". O
// Radix Select não aceita value="" então usamos um literal explícito.
const TODAS = "todas";

// Dashboard — destino padrão após o login. Renderizado dentro do
// AppLayout (sidebar e botão Sair ficam por conta de lá).
//
// Estrutura editorial: saudação em Fraunces + filete ferrugem
// (consistente com Login + Sidebar), perfil/sessão em mono pequena,
// filtro de turma como linha discreta, e grid 2x2 de cards já
// repaginados (ver MetricCard, UltimasChamadasCard, UltimasOcorrenciasCard).
export function DashboardPage() {
  const { user } = useAuth();
  const turmasQuery = useTurmas();

  const [turmaFiltroRaw, setTurmaFiltroRaw] = useState<string>(TODAS);
  const turmaFiltro =
    turmaFiltroRaw === TODAS ? null : parseInt(turmaFiltroRaw, 10);

  const perfilLabel = user?.perfil
    ? PERFIL_LABEL[user.perfil] ?? user.perfil
    : "—";
  const nomeUsuario = user?.first_name || user?.username || "";

  // Métricas que ficam só no card 1 (ocorrências) e card 2 (alunos).
  // Os outros dois cards são componentes independentes que cuidam dos
  // próprios fetchs.
  const ocorrenciasQuery = useOcorrencias(
    turmaFiltro ? { turma: turmaFiltro } : {},
  );
  // `ativo: true` é obrigatório: o backend por default lista alunos soft-deleted
  // também, e o card mostra "Alunos ativos".
  const alunosQuery = useAlunos(
    turmaFiltro ? { turma: turmaFiltro, ativo: true } : { ativo: true },
  );

  const ocorrenciasAbertas = useMemo(() => {
    const dados = ocorrenciasQuery.data ?? [];
    const abertas = dados.filter((o) => o.status === "aberta").length;
    const emAndamento = dados.filter((o) => o.status === "em_andamento").length;
    return { total: abertas + emAndamento, abertas, emAndamento };
  }, [ocorrenciasQuery.data]);

  const totalAlunos = alunosQuery.data?.length ?? 0;
  const turmasComAluno = useMemo(() => {
    const dados = alunosQuery.data ?? [];
    return new Set(dados.map((a) => a.turma)).size;
  }, [alunosQuery.data]);

  const linkOcorrencias = "/ocorrencias";
  const linkAlunos = "/alunos";

  return (
    <div className="p-4 md:p-10 space-y-8">
      <header className="space-y-3">
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          {nomeUsuario ? `Olá, ${nomeUsuario}.` : "Dashboard"}
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
        <p className="text-[11px] uppercase tracking-[0.2em] text-sepia">
          {perfilLabel}
          {user && (
            <span className="normal-case tracking-normal text-sepia/70 ml-2">
              · sessão ativa
            </span>
          )}
        </p>
      </header>

      <div className="flex items-center gap-3">
        <Label
          htmlFor="turma-filtro"
          className="text-[11px] uppercase tracking-[0.18em] text-sepia"
        >
          Visão
        </Label>
        <Select value={turmaFiltroRaw} onValueChange={setTurmaFiltroRaw}>
          <SelectTrigger
            id="turma-filtro"
            className="w-[260px] bg-paper border-border"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TODAS}>Todas as turmas</SelectItem>
            {turmasQuery.data
              ?.filter((t) => t.ativa)
              .map((t) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.nome} — {t.ano_letivo}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <MetricCard
          titulo="Ocorrências em aberto"
          valor={ocorrenciasAbertas.total}
          sublinha={
            ocorrenciasAbertas.total > 0 ? (
              <span>
                {ocorrenciasAbertas.abertas} abertas
                <span className="mx-1.5 text-border">·</span>
                {ocorrenciasAbertas.emAndamento} em andamento
              </span>
            ) : (
              "Nenhuma pendente"
            )
          }
          href={linkOcorrencias}
          carregando={ocorrenciasQuery.isLoading}
          tomDestaque={ocorrenciasAbertas.total > 0}
        />

        <MetricCard
          titulo="Alunos ativos"
          valor={totalAlunos}
          sublinha={
            turmaFiltro
              ? "Na turma selecionada"
              : turmasComAluno > 0
                ? `Em ${turmasComAluno} turma${turmasComAluno > 1 ? "s" : ""}`
                : "—"
          }
          href={linkAlunos}
          carregando={alunosQuery.isLoading}
        />

        <UltimasChamadasCard turmaFiltrada={turmaFiltro} />
        <UltimasOcorrenciasCard turmaFiltrada={turmaFiltro} />
      </div>

      {!turmasQuery.data?.length && !turmasQuery.isLoading && (
        <div className="bg-paper rounded-lg border border-border p-6">
          <p className="font-heading text-lg text-tinta mb-1">
            Nenhuma turma cadastrada
          </p>
          <p className="text-sm text-sepia">
            Cadastre uma turma em "Turmas" pra começar a popular o dashboard.
          </p>
        </div>
      )}
    </div>
  );
}
