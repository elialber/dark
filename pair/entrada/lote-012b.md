# Lote 012b (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 2),
sobre a `main` em `e49466f`. Roda ao mesmo tempo que os lotes 012 (goal
030, executor de evals) e 012c (goal 032, recomendações), cada um no seu
worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 031. O orquestrador já criou o seu worktree, na
branch `goal-031`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`,
`plugin/` (inteiro), `tests/test_plugin.py`, `pair/diario/027.md` e
`pair/diario/028.md`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
README, skills (texto lido pelo usuário), diário e goal em português.

## Por que este goal

A direção é tornar a ferramenta utilizável em outros ambientes. Os goals
027 e 028 entraram na `main`, mas ficaram faltando as pontas, que os
lotes não deixavam tocar: o README não fala do plugin, o `CHANGELOG.md`
não tem a linha dele, e as skills do plugin ainda não conhecem o que o
goal 027 trouxe (`dark --versao`, a auditoria pelo banco, `--coletar`,
`--direto`, `--banco`). Uma skill que descreve opções que o comando não
tem, ou ignora as que tem, engana o agente.

## Goal 031: plugin conectado ao README e ao comando real

Crie `pair/goals/031-plugin-wiring.md` com o texto desta seção.

### 1. Skills em dia com o comando

- `plugin/skills/auditar/SKILL.md`: `dark --versao` agora existe; ajuste
  o passo 1 (continue tratando o caso de versão sem `--versao`, mas como
  exceção). Descreva o que o relatório diz de "Fonte" (banco ou leitura
  direta), as opções `--direto`, `--coletar` e `--banco`, e quando usar
  cada uma, sem inventar: confira cada opção em `dark auditar --help`.
  Diga que a seção "O que mudou desde a última semana" só aparece pelo
  banco e com duas semanas de dados.
- `plugin/skills/coletar/SKILL.md`: confira as opções contra `dark
  coletar --help`.
- **Teste de deriva** (em `tests/test_plugin.py`, escrito antes): toda
  opção `--xxx` citada nas skills existe na saída de `dark auditar
  --help` ou de `dark coletar --help` (o que a skill atribui a cada
  comando), e `dark --versao` funciona. Um teste que a pessoa que muda o
  CLI tem de ver falhar quando esquece a skill.

### 2. README e CHANGELOG

- `README.md`: seção "Plugin" depois de "Evals" (texto proposto no
  diário 028, ajustado: o plugin não é instalado pelo pip; uso por
  `claude --plugin-dir <caminho>/plugin`). Não repita o que o
  `plugin/README.md` diz.
- `CHANGELOG.md`: na entrada "Não lançado", a linha do plugin (goal 028)
  e a das skills em dia com o comando (goal 031), no mesmo estilo das
  linhas que já existem.

### 3. Rodar, se der

**Só se** `CLAUDE_CODE_OAUTH_TOKEN` ou `ANTHROPIC_API_KEY` estiver no
ambiente (só a presença; o valor nunca é impresso nem gravado): rode
`claude --plugin-dir plugin -p` com `CLAUDE_CONFIG_DIR` num diretório sob
`$PAIRLOOP_SCRATCH` (regra do `CLAUDE.md`), pedindo para a skill
`dark:auditar` auditar o repositório sintético montado de
`tests/fixtures/` num diretório temporário, e registre no diário a saída
resumida e o custo. Sem credencial, escreva que não deu; não é falha do
goal.

### Arquivos que você pode criar ou alterar

- `pair/goals/031-plugin-wiring.md` e `pair/diario/031.md` (novos);
- `plugin/` e `tests/test_plugin.py`;
- `README.md` e `CHANGELOG.md`.

Nada mais. Em especial, não toque em `src/`, `evals/`, `pyproject.toml`,
`docs/`, `.github/` nem `pair/ESTADO.md`: os lotes 012 e 012c e o revisor
mexem neles. O `plugin.json` só muda se a versão do pacote mudar, o que
este goal não faz.

### Critério de aceite

1. `python -m pytest -q` passa.
2. `claude plugin validate plugin` passa (mesmos avisos do diário 028 ou
   menos); mostre a saída.
3. **Conferência independente**, tabela "esperado, obtido": para cada
   opção citada nas skills, a saída de `--help` do comando respectivo
   (ou do código de `src/dark/cli.py`) mostra a opção; para cada frase
   das skills sobre o que o relatório traz ("Fonte", "O que mudou"),
   rode `dark auditar` num banco sintético (veja `tests/test_audit_store.py`
   para montar um) e mostre o trecho do relatório que a confirma.
4. Sondagens próprias, com a saída no diário: citar `--inexistente` numa
   skill faz o teste de deriva falhar; tirar a seção "Plugin" do README
   não quebra nada (diga se um teste deveria cobrir: se achar que sim,
   acrescente).
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Teste antes do código.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/031.md`, faça commit, `git push -u
  origin goal-031` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
