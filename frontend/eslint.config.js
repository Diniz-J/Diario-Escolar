import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  // `react-refresh/only-export-components` é regra de DX do hot reload,
  // não de correção: ela avisa que o Fast Refresh perde o estado do
  // componente quando o arquivo exporta outra coisa junto. Nos dois
  // casos abaixo o formato é deliberado, então o ajuste é de
  // configuração — separar os arquivos só pra calar a regra mexeria em
  // código que funciona.
  {
    // shadcn gera os componentes exportando as `cva` variants ao lado do
    // componente (`buttonVariants`, `badgeVariants`...). É a forma que
    // vem do CLI deles, e vale pros que ainda forem adicionados — por
    // isso o override é da pasta, não de um arquivo.
    files: ['src/components/ui/**/*.tsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  {
    // Os dois contexts exportam o `createContext` ao lado do provider,
    // que é o que o `useAuth`/`usePortalAuth` consome. Aqui a regra
    // continua valendo: só estes dois nomes estão liberados, então
    // exportar qualquer outra coisa no arquivo volta a acusar.
    files: [
      'src/features/auth/AuthContext.tsx',
      'src/features/portal/PortalAuthContext.tsx',
    ],
    rules: {
      'react-refresh/only-export-components': [
        'error',
        { allowExportNames: ['AuthContext', 'PortalAuthContext'] },
      ],
    },
  },
])
