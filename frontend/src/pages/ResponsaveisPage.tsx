import { useEffect, useState } from "react";

import { Pagination } from "@/components/Pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { ConvidarDialog } from "@/features/responsaveis/ConvidarDialog";
import { NovoResponsavelDialog } from "@/features/responsaveis/NovoResponsavelDialog";
import { VinculosDialog } from "@/features/responsaveis/VinculosDialog";
import {
  PODE_CONVIDAR,
  SITUACAO_BADGE,
  SITUACAO_OPTIONS,
} from "@/features/responsaveis/constants";
import { useResponsaveisPaginated } from "@/features/responsaveis/hooks";
import { formatarDataHora } from "@/lib/datas";
import type { ResponsavelSituacao, ResponsavelStaff } from "@/types/api";

const FILTRO_TODOS = "__all__";
const PAGE_SIZE = 20;

export function ResponsaveisPage() {
  const [filtroSituacao, setFiltroSituacao] = useState<string>(FILTRO_TODOS);
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [page, setPage] = useState(1);
  const [convidarAlvo, setConvidarAlvo] = useState<ResponsavelStaff | null>(
    null,
  );
  const [vinculosAlvo, setVinculosAlvo] = useState<ResponsavelStaff | null>(
    null,
  );
  const [criando, setCriando] = useState(false);
  // O backend é nível-diretor nos três endpoints (listar, cadastrar,
  // vincular), então o gate de UI é o mesmo — mostrar botão que leva a
  // 403 é prometer o que não acontece.
  const { podeModificarCadastros } = usePermissoes();

  // A busca é server-side (inclui nome de aluno, que não está na linha), e
  // sai com atraso pra não disparar uma request por tecla. Filtro
  // server-side mudou → volta pra página 1 (a atual pode não existir no
  // novo subset). O reset fica no callback/handler, não num `useEffect`
  // com `setState` (regra `react-hooks/set-state-in-effect`).
  useEffect(() => {
    const t = setTimeout(() => {
      setBuscaAplicada(busca.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [busca]);

  function filtrarSituacao(valor: string) {
    setFiltroSituacao(valor);
    setPage(1);
  }

  const query = useResponsaveisPaginated(
    {
      ...(filtroSituacao !== FILTRO_TODOS
        ? { situacao: filtroSituacao as ResponsavelSituacao }
        : {}),
      ...(buscaAplicada ? { search: buscaAplicada } : {}),
    },
    { page, page_size: PAGE_SIZE },
  );

  const linhas = query.data?.results ?? [];
  const totalCount = query.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  // Mensagem do estado vazio por cenário — o "cadastro zerado" é o
  // primeiro que uma escola nova vê, então ele aponta as duas saídas
  // (cadastrar na hora ou semear a partir do cadastro dos alunos).
  function tituloVazio(): string {
    if (buscaAplicada) return "Nenhum responsável encontrado";
    if (filtroSituacao !== FILTRO_TODOS) return "Nenhum responsável aqui";
    return "Nenhum responsável cadastrado";
  }

  function detalheVazio(): string {
    if (buscaAplicada)
      return "A busca cobre nome, email e o nome do aluno. Tente outro termo.";
    if (filtroSituacao !== FILTRO_TODOS)
      return "Nenhuma conta nesta situação. Troque o filtro para ver as outras.";
    return 'Use "Novo responsável" para cadastrar um, ou rode o comando de semeadura para criar as contas a partir do cadastro dos alunos.';
  }

  // Convidar muda a situação da linha. Com um filtro de situação ativo, a
  // linha sai do subset; se era a única da página, ela deixa de existir e
  // o backend responde 404 (paginação do DRF) — a tela mostraria erro sem
  // os controles de página. Volta uma página antes do refetch.
  function aposConvidar() {
    if (filtroSituacao !== FILTRO_TODOS && linhas.length === 1 && page > 1) {
      setPage((p) => p - 1);
    }
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Responsáveis
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground max-w-xl">
            Contas de acesso ao portal. A semeadura cria uma conta por
            família a partir do cadastro do aluno; aqui você cadastra o
            segundo responsável, gerencia os vínculos e envia o convite.
          </p>
        </div>
        {podeModificarCadastros && (
          <Button onClick={() => setCriando(true)}>Novo responsável</Button>
        )}
      </header>

      <ConvidarDialog
        responsavel={convidarAlvo}
        onOpenChange={(aberto) => !aberto && setConvidarAlvo(null)}
        onConvidado={aposConvidar}
      />

      <VinculosDialog
        responsavel={vinculosAlvo}
        onOpenChange={(aberto) => !aberto && setVinculosAlvo(null)}
      />

      <NovoResponsavelDialog open={criando} onOpenChange={setCriando} />

      <div className="flex flex-wrap gap-3 items-end">
        <div className="space-y-1.5">
          <label
            htmlFor="busca-responsavel"
            className="block text-[11px] uppercase tracking-[0.18em] text-sepia"
          >
            Buscar
          </label>
          <Input
            id="busca-responsavel"
            placeholder="Nome, email ou aluno..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            className="w-64"
          />
        </div>
        <div className="space-y-1.5">
          <span className="block text-[11px] uppercase tracking-[0.18em] text-sepia">
            Situação
          </span>
          <Select value={filtroSituacao} onValueChange={filtrarSituacao}>
            <SelectTrigger className="w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={FILTRO_TODOS}>Todas as situações</SelectItem>
              {SITUACAO_OPTIONS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {query.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : query.isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar os responsáveis.
        </p>
      ) : linhas.length === 0 ? (
        <div className="rounded-lg border border-border bg-paper p-6 space-y-2">
          <p className="font-heading text-lg text-tinta">{tituloVazio()}</p>
          <p className="text-sm text-sepia max-w-xl">{detalheVazio()}</p>
        </div>
      ) : (
        <>
          <div className="rounded-lg border border-border bg-paper overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Responsável
                  </TableHead>
                  <TableHead className="hidden lg:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Alunos
                  </TableHead>
                  <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Situação
                  </TableHead>
                  <TableHead className="hidden xl:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Último acesso
                  </TableHead>
                  <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Ações
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {linhas.map((r) => (
                  <TableRow
                    key={r.id}
                    // A linha abre os vínculos — o §7.1 manda a linha levar
                    // ao detalhe, e aqui o dialog de vínculos É o detalhe
                    // (não existe página de detalhe de responsável). Só
                    // clicável pra quem pode gerir: o resto levaria a um
                    // dialog que o backend recusa.
                    className={[
                      podeModificarCadastros ? "cursor-pointer" : "",
                      // Conta desativada fica recuada visualmente (§7.1). Sem
                      // badge `[ inativo ]` extra: a coluna Situação já diz
                      // "Inativo", e repetir seria eyebrow em dobro (§8.6).
                      r.situacao === "inativo" ? "opacity-60" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    onClick={
                      podeModificarCadastros
                        ? () => setVinculosAlvo(r)
                        : undefined
                    }
                  >
                    {/* `whitespace-normal` desliga o `whitespace-nowrap` que
                        o TableCell do shadcn traz: sem isso nome e email
                        ficam numa linha só e esticam a tabela. */}
                    <TableCell className="whitespace-normal">
                      <span className="font-medium block">
                        {r.nome || "(sem nome)"}
                      </span>
                      <span className="text-sm text-muted-foreground break-all whitespace-normal">
                        {r.email}
                      </span>
                      {/* Em < lg a coluna "Alunos" não cabe, mas "de quem é
                          este responsável" é a pergunta central da tela —
                          esconder deixaria a linha sem sentido no celular.
                          Então os filhos descem pra cá, compactos.
                          `whitespace-normal` é obrigatório: o TableCell do
                          shadcn traz `whitespace-nowrap`, e sem desligar isso
                          dois filhos esticam a tabela além da viewport e
                          jogam Situação e Ações pra trás do scroll
                          horizontal — justo as duas colunas que a secretaria
                          usa pra agir. */}
                      {r.alunos.length > 0 && (
                        <span className="lg:hidden mt-1 block text-xs text-sepia whitespace-normal">
                          {r.alunos.map((a) => (
                            <span key={a.id} className="block">
                              {a.nome_completo}
                              {a.turma ? ` · ${a.turma}` : ""}
                            </span>
                          ))}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                      {r.alunos.length === 0
                        ? "—"
                        : r.alunos.map((a) => (
                            <span key={a.id} className="block">
                              {a.nome_completo}
                              {a.turma ? ` · ${a.turma}` : ""}
                              {!a.ativo ? " [ inativo ]" : ""}
                            </span>
                          ))}
                    </TableCell>
                    {/* `px-1` abaixo de sm: a 360px as tres colunas visiveis
                        somam 4px a mais que a viewport, e o piso e o badge
                        (nao quebra sem ficar ilegivel). Apertar o respiro
                        lateral da celula resolve sem mexer no rotulo. */}
                    <TableCell className="whitespace-normal px-1 sm:px-2">
                      <span
                        className={`inline-flex whitespace-nowrap items-center rounded-full px-2 py-0.5 text-xs font-medium ${SITUACAO_BADGE[r.situacao]}`}
                      >
                        {r.situacao_display}
                      </span>
                      {r.situacao === "convidado" && r.convite_expira_em && (
                        <span className="block text-xs text-muted-foreground mt-1">
                          expira {formatarDataHora(r.convite_expira_em)}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="hidden xl:table-cell text-sm text-muted-foreground">
                      {formatarDataHora(r.ultimo_acesso)}
                    </TableCell>
                    {/* `stopPropagation` na célula: clicar em Convidar não
                        deve abrir os vínculos por baixo (padrão do projeto). */}
                    <TableCell
                      className="text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {PODE_CONVIDAR.includes(r.situacao) && (
                        <Button
                          size="sm"
                          variant={
                            r.situacao === "convidado" ? "outline" : "default"
                          }
                          onClick={() => setConvidarAlvo(r)}
                        >
                          {r.situacao === "convidado" ? "Reenviar" : "Convidar"}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalLabel={`${totalCount} ${totalCount === 1 ? "responsável" : "responsáveis"} no total`}
          />
        </>
      )}
    </div>
  );
}
