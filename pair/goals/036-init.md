# Goal 036: `dark iniciar` e `dark remover`

Item 6 do roteiro: quem chega com um repositório novo ou existente precisa
de um comando que prepare a estrutura mínima, sem sobrescrever nada e sem
inventar conteúdo. O motor (goal 016) existe; este goal dá a ele um comando
de usuário e o primeiro módulo, o próprio esqueleto, sem terceiros.

## 1. O módulo `base`

Um `Module` (contrato do goal 016, versão fixada) que planeja, só com as
operações do motor e **só o que falta**:

- `CLAUDE.md` na raiz, se não existir: título, uma linha dizendo o que o
  arquivo é e a seção "Regras derivadas de falhas observadas" vazia, com um
  comentário dizendo que cada regra entra com o motivo. Nenhuma regra,
  nenhuma convenção inventada;
- `evals/cases/` com `LEIAME.md` curto (formato do caso, comandos
  `python -m dark.evals minerar` e `validar`) e um modelo de caso comentado
  que não vale como caso (extensão `.toml.modelo`);
- uma linha em `.gitignore` para o que a ferramenta grava localmente, se
  houver.

Não cria `.claude/`, skills, subagentes, hooks nem regras. Repositório que
já tem `CLAUDE.md` (mesmo vazio) ou `evals/cases/`: o item não entra no
plano.

## 2. Comandos

- `dark iniciar [CAMINHO]`: mostra o plano, sem escrever nada; antes dele,
  uma linha com o estado do harness (auditoria só de leitura). Com
  `--aplicar` aplica, tudo ou nada, pelo motor, registrando no manifesto
  sob o nome do módulo. Conflito: relatado, nada aplicado, saída 1; entrada
  ruim: 2.
- `dark remover MODULO [CAMINHO]`: reverte o que o manifesto registra,
  respeitando edição do usuário (o que o usuário mudou fica e é relatado).
- Ajuda e mensagens em português; nenhum traceback em entrada ruim.

## 3. Testes (antes do código)

Três repositórios de teste em diretório temporário: vazio (aplicar, aplicar
de novo, remover: árvore idêntica byte a byte); com `CLAUDE.md` e
`.gitignore` do usuário; com `evals/cases/x.toml` do usuário. Mais: o plano
não escreve; `CLAUDE.md` editado fica na remoção, com aviso; remover módulo
nunca instalado não dá traceback; ponta a ponta pela CLI.

## Critério de aceite

1. `python -m pytest -q` passa.
2. Conferência independente (`find` + `shasum`), tabela "esperado, obtido",
   nos três repositórios de teste.
3. Sondagens próprias (sem git, caminho que é arquivo, `CLAUDE.md` como
   diretório, manifesto inválido, `--aplicar` duas vezes): sem traceback.
4. Numa cópia deste repositório, `dark iniciar` propõe só o que falta e não
   escreve.
5. O que o módulo cria não contém regra, skill nem instrução inventada.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
