# Goal 022 — Casos de eval deste repositório

Texto do [lote 010](../entrada/lote-010.md), seção "Goal 022: casos de
eval deste repositório", copiado sem alteração.

### 1. Casos

1. Rode `python -m dark.evals minerar --repo . --comando "python -m pytest -q"`
   (hoje dá 37 candidatos). Escolha **pelo menos 10** e grave cada um em
   `evals/cases/<id>.toml`, no formato de `evals/README.md`.
2. Na escolha:
   - cubra pelo menos quatro módulos diferentes (por exemplo: histórico
     git, casos de eval, motor do scaffold, armazenamento, executor,
     portabilidade);
   - prefira tarefas pequenas e médias; inclua no máximo três cujo
     commit de solução altere mais de 800 linhas fora de testes;
   - fique fora de casos cujo aceite dependa de dados reais da máquina
     (decisão "Casos de eval dos goals 006 e 007") e de commits que só
     renomeiam ou traduzem (os de "Rename..." e "Translate...");
   - `goal-005-leitor` continua e conta entre os 10.
3. O `prompt` de cada caso é escrito a partir do texto do goal
   correspondente em `pair/goals/` (ou da mensagem do commit, quando não
   houver goal), como um pedido de usuário: o que fazer e onde, sem
   copiar código da solução e sem mencionar o commit de solução. Diga
   nas `notes` de onde veio o pedido, o tipo de candidato e o tamanho da
   solução (linhas alteradas fora de testes, por `git diff --numstat`).
4. Comando de aceite: só os arquivos de teste que a solução trouxe ou
   mudou, com `-p no:cacheprovider`, e `files` com esses arquivos (e os
   sintéticos de que dependem), como no caso do goal 005. Tempo por
   caso: o menor múltiplo de 60 s acima do triplo da duração medida na
   validação.
5. Valide todos: `python -m dark.evals validar --repo . evals/cases/*.toml`
   num ambiente com pytest e **sem** o pacote `dark` instalado em modo
   editável a partir de outro checkout (ver `evals/README.md`). Caso
   inválido não fica em `cases/`; troque por outro candidato.

### 2. Conjunto da primeira rodada e tolerância

Em `evals/README.md`, seção nova "Primeira rodada":

- os 5 casos da primeira rodada (E17: 5 casos, 2 condições, 3
  execuções), escolhidos entre os menores, com o motivo da escolha;
- a tolerância com que duas rodadas iguais serão comparadas, declarada
  **antes** de medir (regra "Tolerância em conferência" de
  `docs/roteiro.md`), com o raciocínio: com 3 execuções por caso e
  condição, que diferença de taxa de acerto é ruído. Registre-a também
  no diário como decisão a confirmar.

### 3. Erros da CLI sem traceback

A revisão do goal 021 encontrou dois comandos que terminam em traceback
diante de entrada ruim:

- `python -m dark.evals resumir ARQ`, com uma linha que não é JSON:
  `JSONDecodeError` em `src/dark/evals/rounds.py` (`load_records`);
- `python -m dark.evals validar evals/cases/nao-existe.toml`:
  `FileNotFoundError` vindo de `src/dark/evals/__main__.py`.

Os dois passam a imprimir uma mensagem em português, com o arquivo (e,
no primeiro, o número da linha), e sair com código 2. Confira também
`calibrar`, `rodar` e `minerar --gravar` com arquivo de caso ausente, TOML
malformado e diretório sem permissão de escrita; corrija os que
terminarem em traceback. Testes antes do código, em
`tests/test_evals.py` ou `tests/test_evals_runner.py`.

### Arquivos que você pode criar ou alterar

- `pair/goals/022-eval-cases.md` e `pair/diario/022.md` (novos);
- `evals/cases/*.toml` (novos; o de `goal-005-leitor` só se a validação
  pedir) e `evals/README.md`;
- `src/dark/evals/` (só para o item 3);
- `tests/test_evals.py` e `tests/test_evals_runner.py`.

Nada mais. Em especial, não toque em `src/dark/cli.py`, `src/dark/store/`,
`pyproject.toml`, `README.md`, `.github/`, `docs/` nem `pair/ESTADO.md`:
os outros lotes deste ciclo e o revisor mexem neles.

### Critério de aceite

1. `python -m pytest -q` passa.
2. `evals/cases/` tem pelo menos 10 casos, de pelo menos quatro módulos,
   e `python -m dark.evals validar --repo . evals/cases/*.toml` diz
   VÁLIDO para todos. Mostre a saída no diário.
3. **Conferência independente**, em tabela "esperado, obtido": para pelo
   menos três casos, rode o comando de aceite à mão, sem a ferramenta,
   num worktree temporário fora do repositório (`git worktree add` em
   `$PAIRLOOP_SCRATCH`, checkout do commit, `git checkout <files_from> --
   <files>`, rodar o comando), no `base_commit` e no `solution_commit`.
   Os códigos de saída batem com os da validação (diferente de 0 na
   base, 0 na solução). Remova os worktrees depois.
4. Tabela com cada caso: id, módulo, tipo de candidato, linhas da
   solução fora de testes, duração na base e na solução, tempo
   declarado.
5. `evals/README.md` tem a seção "Primeira rodada" com os 5 casos e a
   tolerância.
6. As duas entradas ruins do item 3 dão mensagem e código 2, com teste
   para cada uma.

