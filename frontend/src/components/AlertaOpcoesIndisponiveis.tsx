import { Alert, AlertDescription } from "@/components/ui/alert";

interface AlertaOpcoesIndisponiveisProps {
  /** Verdadeiro quando alguma query que popula os selects falhou. */
  falhou: boolean;
}

/**
 * Aviso de que as opções do formulário não carregaram.
 *
 * No TanStack Query o `isLoading` volta a false quando a query **falha**,
 * então o select renderiza vazio e o dialog fica indistinguível de "a
 * escola não tem turma cadastrada". Pior: a validação de submit então
 * responde "Selecione uma turma", culpando o usuário por uma falha de
 * rede. Este aviso diz o que de fato aconteceu.
 *
 * Mora em `components/` porque são quinze dialogs mostrando a mesma
 * frase — quinze cópias divergiriam, como divergiram as catorze cópias
 * de formatador de data antes do `lib/datas.ts`.
 */
export function AlertaOpcoesIndisponiveis({
  falhou,
}: AlertaOpcoesIndisponiveisProps) {
  if (!falhou) return null;
  return (
    <Alert variant="destructive">
      <AlertDescription>
        Não foi possível carregar as opções deste formulário. Feche e abra de
        novo; se continuar, recarregue a página.
      </AlertDescription>
    </Alert>
  );
}
