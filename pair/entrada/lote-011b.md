# Lote 011b (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 1),
sobre a `main` em `5136991`. Roda ao mesmo tempo que os lotes 011
(goal 027, auditoria sobre o banco) e 011c (goal 029, casos de eval),
cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 028. O orquestrador já criou o seu worktree,
na branch `goal-028`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `README.md`, `docs/roteiro.md`
(item 8), o diário 023 (distribuição) e `docs/portabilidade.md`.

Idioma (E18): código, comentários, nomes de teste, nomes de arquivos e
mensagens de commit em inglês; texto que o usuário lê (descrição da
skill, README do plugin), o diário e o goal em português.

## Por que este goal

A direção é tornar a ferramenta utilizável em outros ambientes. O goal
023 entregou `pip install`; falta o plugin do Claude Code, que o item 8
do roteiro prevê, para que quem usa o Claude Code chame a auditoria
dentro da sessão. O plugin não substitui o pacote: orienta o agente a
rodar o `dark` instalado.

## Goal 028: plugin do Claude Code

Crie `pair/goals/028-plugin.md` com o texto desta seção.

### 1. O plugin

Em `plugin/` (pasta nova, que é a raiz do plugin), com o formato de
plugins do Claude Code (manifesto `.claude-plugin/plugin.json` dentro de
`plugin/`, skills em `plugin/skills/<nome>/SKILL.md`). Confira o formato
na documentação oficial do Claude Code e, se houver `claude plugin
validate` na máquina, use-o; registre no diário a fonte e a versão do
Claude Code. Conteúdo mínimo:

- manifesto com nome, versão igual à de `pyproject.toml` (um teste
  garante que as duas batem), descrição e licença conforme o repositório;
- uma skill `auditar`: quando o usuário pedir para auditar o harness,
  ver o uso das peças ou o peso do contexto, o agente confere se `dark`
  está instalado (`dark --versao`; se o comando não existir ainda, a
  skill diz como instalar, por `pip install "git+<URL>"` como no README,
  e não instala sozinha), roda `dark auditar` com as opções que o
  usuário pediu, e resume o relatório sem inventar números. Informa que
  o relatório fica fora do repositório por padrão (ver README);
- uma skill `coletar`: orienta `dark coletar --todos` e explica o que
  é gravado (só agregados).
- **Nenhuma** regra, hook ou skill com conteúdo de método além disso
  (o scaffold não gera conteúdo: `docs/visao.md`). Nenhum comando
  arbitrário do usuário embutido; nenhuma chave ou caminho pessoal.
- `plugin/README.md`: como instalar o plugin (pelo caminho local do
  repositório, que é o que dá para verificar offline) e como atualizar.

### 2. Testes

`tests/test_plugin.py`: manifesto é JSON válido com os campos
obrigatórios; versão igual à do `pyproject.toml`; cada skill tem o
cabeçalho (`name`, `description`) e o `name` bate com a pasta; a
descrição não passa do limite documentado; nenhum arquivo do plugin
casa com os padrões de privacidade de `tests/test_distribution.py`
(reaproveite os padrões importando de lá ou copiando, o que for mais
simples); o wheel/pacote não precisa levar o plugin (registre a decisão).

### 3. Algo que roda

Carregue o plugin numa sessão real **só se** houver credencial no
ambiente (`CLAUDE_CODE_OAUTH_TOKEN` ou `ANTHROPIC_API_KEY`), com
`CLAUDE_CONFIG_DIR` num diretório sob `$PAIRLOOP_SCRATCH` e
`claude --plugin-dir plugin -p` (ou o equivalente da versão instalada),
pedindo uma auditoria do repositório sintético montado de
`tests/fixtures/`, e registre o resultado no diário. Sem credencial,
registre que não deu e o motivo; o critério 3 abaixo passa a valer só
com a validação estática. Sessão de teste segue a regra do `CLAUDE.md`:
nunca grava no histórico real do usuário.

### Arquivos que você pode criar ou alterar

- `pair/goals/028-plugin.md` e `pair/diario/028.md` (novos);
- `plugin/` (novo, tudo dentro) e `tests/test_plugin.py` (novo).

Nada mais. Em especial, não toque em `src/`, `README.md`,
`CHANGELOG.md`, `pyproject.toml`, `.github/`, `docs/` nem
`pair/ESTADO.md`: o lote 011 mexe em `src/`, `README.md` e
`CHANGELOG.md`, e o revisor nos demais. Proponha no diário o texto para
o README (uma seção "Plugin") e a linha do `CHANGELOG.md`; o revisor os
leva ao lote seguinte.

### Critério de aceite

1. `python -m pytest -q` passa.
2. O plugin passa na validação do Claude Code (`claude plugin validate`
   ou equivalente) ou, se a versão instalada não tiver o comando, na
   conferência manual do formato contra a documentação, com a fonte
   citada.
3. Sessão real carregando o plugin e usando a skill `auditar` sobre os
   arquivos sintéticos, com a saída no diário (ou o motivo de não ter
   rodado).
4. Sondagens próprias, com a saída no diário: manifesto com versão
   diferente da do `pyproject.toml` faz o teste falhar; skill com nome
   diferente da pasta faz o teste falhar; um arquivo do plugin com um
   caminho `/Users/x/...` faz o teste de privacidade falhar.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Teste antes do código.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/028.md`, faça commit, `git push -u
  origin goal-028` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
