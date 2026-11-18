# dark

Ferramenta de linha de comando para quem usa o Claude Code. Ela lê as
transcrições que o Claude Code grava na sua máquina e mostra, para um
repositório, como está o harness dele (instruções, skills, subagentes,
hooks, servidores MCP, permissões): quanto ele pesa em cada pedido, o que
foi instalado e nunca é usado, quanto as sessões custaram, onde você
precisou intervir. O objetivo do projeto é também instalar e manter esse
harness; nesta versão (0.1.0), a ferramenta mede e indica o que mudar,
com evidência, mas ainda não instala nada. O que ela faz e o que ainda
não faz está no [registro de mudanças](CHANGELOG.md); tudo o que está
planejado, com a marca de pronto ou não, está em
[FUNCIONALIDADES.md](FUNCIONALIDADES.md).

## Instalação

Um comando, sem dependência além do Python:

```bash
python -m pip install "git+<URL do repositório>"
```

Se você usa `pipx` ou `uv`, eles instalam o comando num ambiente
isolado, com a mesma URL (nenhum dos dois é necessário):

```bash
pipx install "git+<URL do repositório>"
uv tool install "git+<URL do repositório>"
```

Para fixar uma versão, acrescente a etiqueta ao fim da URL
(`git+<URL do repositório>@v0.1.0`), quando ela existir. Para conferir a
versão instalada: `python -m pip show dark`.

Se o comando `dark` não ficar no `PATH` (acontece com `pip install
--user` no Windows), `python -m dark` faz o mesmo.

## Primeiro uso

Dentro do repositório que você quer auditar:

```bash
dark auditar
```

Ou apontando para ele, e gravando o relatório num arquivo:

```bash
dark auditar <caminho-do-repositório> --saida <arquivo-fora-do-repositório>.md
```

O comando lê as transcrições do Claude Code (de `CLAUDE_CONFIG_DIR`, ou de
`~/.claude` se a variável não existir), junta as sessões que rodaram
naquele repositório e imprime um relatório em Markdown:

- **cabeçalho:** período coberto, número de sessões e de pedidos,
  versões do Claude Code;
- **o que chama atenção:** os pontos que mais pesam, primeiro;
- **peso fixo:** quanto do contexto cada pedido já começa ocupando, com a
  repartição estimada entre plataforma, harness e o pedido em si;
- **peso morto:** peças do harness carregadas e nunca usadas, com a
  origem de cada uma (projeto, usuário, plugin ou plataforma);
- **o que está instalado**, **custo**, **intervenções** (interrupções,
  rejeições), **hooks** e **commits** ligados às sessões;
- **apêndice** com as listas completas.

Num repositório sem sessões, o relatório diz isso e para: é um estado
normal, os números aparecem depois das primeiras sessões. O Claude Code
apaga transcrições com mais de 30 dias, por padrão; o relatório só
enxerga o que ainda está no disco.

O comando só lê. Não escreve no repositório auditado, e o git é usado só
para leitura. A ligação dos commits pode demorar em discos lentos (como
o do Windows montado no WSL); `--sem-git` a desliga.

Opções:

| Opção | O que faz |
|---|---|
| `--dias N` | só sessões iniciadas nos últimos N dias |
| `--ate <instante>` | ignora registros depois deste instante (ISO 8601) |
| `--todos` | todas as sessões, de qualquer repositório |
| `--saida <arquivo>` | grava o relatório no arquivo em vez de imprimir |
| `--sem-git` | não consulta o histórico git |
| `--config <dir>` | lê outro diretório de configuração do Claude Code |

`dark auditar --help` lista todas, inclusive as de conferência
(`--gerenciado`, `--excluir-pasta`).

Se já existe um banco de coleta que conhece o repositório (veja "Coleta"
abaixo), a auditoria lê as sessões dele em vez de reler as transcrições,
mostra a data da última coleta e traz a seção "O que mudou desde a última
semana"; sem banco, ou com banco que não serve, ela lê direto e diz por
quê. `--direto` força a leitura direta, `--coletar` coleta antes de
auditar e `--banco` escolhe o arquivo. `dark --versao` imprime a versão
instalada.

## Coleta

O Claude Code apaga as transcrições antigas (30 dias, por padrão). Para
comparar uma semana com a anterior por mais tempo, rode a coleta de vez
em quando, por exemplo uma vez por semana:

```bash
dark coletar --todos
```

Ela grava, num banco local fora dos seus repositórios (no macOS,
`~/Library/Application Support/dark/aggregates.sqlite3`; no Linux,
`~/.local/share/dark/`; no Windows, `%LOCALAPPDATA%\dark\`), os números
de cada sessão: pedidos, tokens, intervenções, desfechos de hook, peças
disponíveis e usadas, ligações de commits e um retrato do inventário.
Nenhum texto de conversa é gravado. Coletar de novo não duplica nada, e
as sessões que o Claude Code apagar continuam no banco.

Sem `--todos`, coleta só o repositório do diretório atual (ou o
caminho dado). `--banco` escolhe outro arquivo; o comando recusa um
arquivo dentro de um repositório git que não o ignore. `--sem-git` pula
a consulta ao histórico git (mais rápido; as ligações já gravadas ficam).
`dark auditar` não coleta sozinho; `dark auditar --coletar` coleta e
audita.

`dark coletar --evals <arquivo.jsonl>` também importa, depois da coleta,
os resultados de uma rodada de evals (a opção pode se repetir, um arquivo
por vez). Um arquivo que não existe, vazio, binário ou que é um diretório
faz o comando parar com código 2 antes de coletar: nada é gravado. Sem
coletar, `python -m dark.evals guardar <arquivo.jsonl>` faz só a
importação. As duas regras de recomendação sobre evals usam esses dados.

## Preparar o repositório

Quatro comandos aplicam, conferem e desfazem estrutura de harness num
repositório. Rode-os na **raiz** de um repositório git (com `git init`,
se for novo); em outro lugar eles recusam e dizem onde está a raiz. Nada
existente é sobrescrito.

`dark iniciar` prepara o mínimo. Sem opções, só mostra o plano e não
escreve nada; `--aplicar` aplica, tudo ou nada:

```bash
dark iniciar [<caminho>]            # mostra o que seria criado
dark iniciar --aplicar [<caminho>]  # cria
```

Ele usa o módulo `base`, que cria só o esqueleto: um `CLAUDE.md` com a
seção de regras vazia e `evals/cases/` com um `LEIAME.md` e um modelo de
caso comentado (que não vale como caso). O que já existe fica como está.
O módulo **não** cria regras, skills, subagentes nem hooks: isso nasce de
falhas que você observa (veja o ciclo em [docs/metodo.md](docs/metodo.md)).
O que foi criado fica registrado no manifesto `.dark-scaffold.json`, na
raiz.

`dark adicionar <módulo> [<caminho>]` faz o mesmo para qualquer módulo
registrado (`dark iniciar` é `dark adicionar base`), também com
`--aplicar`. `dark adicionar --listar [<caminho>]` lista os módulos, com
versão, indicador e se estão aplicados no repositório; é por ele que você
sabe quais módulos estão registrados na versão instalada.

`dark verificar <módulo> [<caminho>]` só lê e imprime `ok` ou o motivo
(por exemplo, um arquivo do módulo que sumiu).

`dark remover <módulo> [<caminho>]` desfaz o que o manifesto registra
para o módulo. O que você alterou depois fica no lugar e é relatado como
`mantido`, e o manifesto continua registrando o que ficou.

Códigos de saída:

| Comando | 0 | 1 | 2 |
|---|---|---|---|
| `dark iniciar`, `dark adicionar` | plano mostrado ou aplicado | conflito com um arquivo existente (nada é aplicado) ou erro ao gravar (o que foi gravado é desfeito) | módulo desconhecido, caminho que não é a raiz de um repositório git, manifesto ilegível |
| `dark verificar` | `ok` | o módulo não está aplicado ou falta algo dele (um arquivo; no `langfuse`, também variáveis; no `graphify`, também o executável no `PATH`) | módulo desconhecido, caminho que não é a raiz |
| `dark remover` | tudo desfeito (ou nada a desfazer) | remoção parcial: algo alterado depois ficou, ou a linha do `.gitignore` de um caminho que ainda existe | módulo desconhecido, caminho que não é a raiz |

### Módulo `langfuse`

Opcional. Liga o Claude Code a uma instância do
[Langfuse](https://langfuse.com) que roda na sua máquina, para ver os
rastros de cada sessão (turnos, chamadas de ferramenta, tokens e custo).
O indicador do módulo é `cost_per_task`.

```bash
dark adicionar langfuse            # mostra o plano e os passos seguintes
dark adicionar langfuse --aplicar  # cria
```

O que ele cria:

- `.dark/langfuse/docker-compose.yml`: o compose oficial do Langfuse
  4.82.0 (edição community, licença MIT), com toda imagem em etiqueta
  exata e toda senha e segredo exigidos do `.dark/langfuse/.env`, sem
  valor padrão;
- `.dark/langfuse/env.exemplo`: os nomes das sete variáveis do `.env`,
  sem valor, cada uma com o comando que a gera;
- a linha `.dark/langfuse/.env` no `.gitignore`, para os segredos
  ficarem fora do git;
- três entradas no `.claude/settings.json` do projeto: a marketplace do
  plugin oficial `langfuse-observability@langfuse-observability`,
  fixada na etiqueta `v1.2.2` (`extraKnownMarketplaces`), o plugin ligado
  (`enabledPlugins`) e o endereço da instância local
  (`env.LANGFUSE_BASE_URL`). As chaves de API **não** vão para esse
  arquivo, que é versionado.

Depois de aplicar (os mesmos passos que o comando imprime):

1. Crie o `.env` da instância e preencha cada valor:

   ```bash
   cp .dark/langfuse/env.exemplo .dark/langfuse/.env
   ```

2. Suba a instância (precisa de Docker; o `dark` não sobe nada):

   ```bash
   docker compose -f .dark/langfuse/docker-compose.yml --env-file .dark/langfuse/.env up -d
   ```

   A interface fica em `http://localhost:3000`; crie lá um projeto e as
   chaves de API.
3. Ponha as chaves, `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY`, no
   ambiente de onde o Claude Code é aberto, ou use `/plugin configure`
   no Claude Code (a secreta fica no chaveiro do sistema).
4. O gancho do plugin roda com `uv` no `PATH`; sem `uv`, com `python3`
   3.10 ou mais novo e `pip install "langfuse==4.18.0"`. O `dark` não
   instala nenhum dos dois.

`dark verificar langfuse` só lê, sem rede e sem Docker, e nunca mostra
um valor. Confere que o compose e o `env.exemplo` estão como foram
aplicados, que a linha do `.gitignore` e as três entradas do
`.claude/settings.json` estão lá, e que as variáveis existem: as sete do
compose no ambiente ou com valor no `.dark/langfuse/.env`; as duas chaves,
só no ambiente (ele não lê o chaveiro). O que faltar sai no motivo, por
exemplo `variáveis ausentes: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY`.
`dark remover langfuse` desfaz os arquivos e as entradas. O `.env` que
você criou não é do módulo e fica; enquanto ele existir, a linha que o
ignora também fica no `.gitignore`, a remoção sai como parcial (código
1) e o `remover` diz o que fazer: apague o `.env` e rode `dark remover
langfuse` de novo para tirar a linha.

> **Atenção.** O Langfuse guarda o **conteúdo das conversas** (pedidos,
> respostas, entradas e saídas de ferramentas) na sua instância. O `dark`
> continua sem guardar conteúdo de conversas, só agregados.
>
> O compose oficial liga por padrão a **telemetria anônima** do Langfuse:
> `TELEMETRY_ENABLED` vale `true` quando ausente. Para desligá-la, ponha
> `TELEMETRY_ENABLED=false` no `.dark/langfuse/.env`; a escolha é sua.
>
> O gancho do plugin grava estado e log em `~/.claude/state/`, ou na
> pasta de `CC_LANGFUSE_STATE_DIR`, se a variável existir.

O ganho do Langfuse ainda não pode ser medido com `python -m dark.evals
modulo` (veja o fim da subseção do Graphify): a cópia não leva o
`.dark/langfuse/.env`, que fica fora do git, e sem as variáveis no
ambiente o `verify` do módulo falha na cópia e a rodada é recusada antes
de rodar o agente.

### Módulo `graphify`

Opcional. Liga o Claude Code ao Graphify (edição open source, licença
Apache-2.0), que monta um grafo do repositório para o agente consultar
antes de explorar arquivo por arquivo. A versão fixada é a 0.9.112, do
pacote [`graphifyy`](https://pypi.org/project/graphifyy/) (com dois "y")
no PyPI; o endereço do repositório de origem fica no `ORIGEM.md` que o
módulo cria. O indicador do módulo é `cost_per_task`.

```bash
dark adicionar graphify            # mostra o plano e os passos seguintes
dark adicionar graphify --aplicar  # cria
```

O que ele cria, o equivalente no projeto de `graphify claude install
--project` dessa versão, sem o que essa instalação escreve no
`CLAUDE.md` e no `.claude/CLAUDE.md`:

- `.claude/skills/graphify/`: a skill oficial do Graphify, copiada **sem
  alteração** da versão fixada (`.claude/skills/graphify/SKILL.md` e os
  arquivos de `.claude/skills/graphify/references/`), com
  `.claude/skills/graphify/LICENSE` e `.claude/skills/graphify/NOTICE`
  da mesma versão (a licença os exige junto da cópia),
  `.claude/skills/graphify/ORIGEM.md` (de onde a cópia veio: projeto,
  pacote, versão e licença) e `.claude/skills/graphify/.graphify_version`,
  o marcador que a instalação oficial grava e que o Graphify lê para
  avisar quando skill e programa têm versões diferentes;
- os hooks oficiais no `.claude/settings.json` do projeto: dois em
  `PreToolUse` (antes de `Bash` e `Grep`, e antes de `Read` e `Glob`) e
  um em `SessionStart` (depois de uma compactação), todos chamando o
  executável `graphify`;
- a linha `graphify-out/` no `.gitignore`: é onde o Graphify grava o
  grafo.

O módulo **não** instala o Graphify, **não** gera o grafo e **não**
escreve no `CLAUDE.md`: a instalação oficial acrescenta lá regras de uso,
e regras aqui nascem de falhas observadas (veja
[docs/metodo.md](docs/metodo.md)). Sem elas, o agente chega ao grafo pela
descrição da skill e pelos lembretes dos hooks.

Depois de aplicar (os mesmos passos que o comando imprime):

1. Instale o Graphify na máquina, com a versão fixa:

   ```bash
   uv tool install "graphifyy==0.9.112"
   ```

   ou `pipx install "graphifyy==0.9.112"`, ou
   `python -m pip install "graphifyy==0.9.112"`. O `dark` não instala
   nada.
2. Gere o grafo pela primeira vez, na raiz do repositório:

   ```bash
   graphify extract . --code-only
   ```

   Esse comando lê só o código, localmente, sem chave de API. Numa
   sessão do Claude Code, `/graphify .` gera o grafo completo; para
   documentos, artigos e imagens, a skill copiada usa o modelo da própria
   sessão (o que gasta tokens) ou o Gemini, se `GEMINI_API_KEY` ou
   `GOOGLE_API_KEY` estiver no ambiente.
3. Confira com `dark verificar graphify`.

`dark verificar graphify` só lê e nunca executa o `graphify`. Confere que
os arquivos da skill estão como foram aplicados, que os três hooks estão
no `.claude/settings.json`, que a linha `graphify-out/` está no
`.gitignore` e que o executável `graphify` está no `PATH`. O que faltar
sai no motivo, um por linha, por exemplo:

```
o executável graphify não está no PATH (instale: uv tool install "graphifyy==0.9.112")
```

`dark remover graphify` desfaz o que o manifesto registra para o módulo;
o que você acrescentou ao `.claude/settings.json` fica. A linha
`graphify-out/` fica no `.gitignore` enquanto a pasta existir: a remoção
sai como parcial (código 1) e o `remover` diz o que fazer: apague a
pasta `graphify-out/` e rode `dark remover graphify` de novo para tirar
a linha.

O ganho do Graphify se mede com `python -m dark.evals modulo`, que roda
os seus casos de eval com o harness do projeto e com o mesmo harness mais
o módulo, aplicado só numa cópia (o seu repositório é só lido):

```bash
python -m dark.evals modulo --nome graphify --repo . --saida /tmp/evals/graphify.jsonl \
  --execucoes 3 --simular evals/cases/*.toml
```

Na cópia com o módulo, antes do agente, roda a preparação que o módulo
declara, `graphify extract . --code-only`; por isso o executável
`graphify` tem de estar no `PATH` (sem ele a rodada é recusada, e
`--simular` só avisa). A resposta é `ganho`, `sem ganho`, `piora` ou
`inconclusivo`: com pelo menos 15 execuções válidas por condição,
`ganho` pede que o acerto não caia mais que 4 em 15 execuções, que a
média de tokens com o módulo fique em no máximo 90% da média sem ele e
que a média de turnos não suba. A medição real roda o Claude Code e pede
credencial no ambiente, como `rodar`; ela ainda não foi feita, e o ganho
do Graphify continua sem número. A explicação completa está em
[evals/README.md](evals/README.md#ganho-de-um-módulo).

## Recomendações

O relatório traz uma seção "Recomendações", feita por regras fixas: sem nota
única e sem texto gerado. Cada linha dá a regra, o número ou o nome que a
disparou, uma ação que você mesmo faz e como conferir depois. Há sete
regras: peça sem uso há semanas, arquivo de instruções grande, peso do
inventário que subiu, bloqueios repetidos de hook, commits sem hash, evals
sempre em 100% e modelo que mudou desde a última rodada de evals. As
regras de peça sem uso, de peso do inventário e as duas de evals dependem
do banco de coleta (`dark coletar`; as de evals, também dos resultados
importados com `--evals` ou `guardar`); as demais funcionam na leitura
direta. Os limites (4 semanas, 200 linhas, 3 bloqueios, 3 rodadas) são
padrões a confirmar, constantes em
`src/dark/recommend.py`. Cada regra, o que fazer e como ler o resto do
relatório estão em [docs/metodo.md](docs/metodo.md), que também resume o
método (derivação e poda) em que a ferramenta se apoia.

## Ablação

Para decidir se uma peça sem uso pode sair, a ablação roda os seus casos
de eval com o harness completo e com ele menos essa peça, e responde
`pode remover`, `mantenha`, `inconclusivo` ou `não discrimina`, com os
números. O comando é `python -m dark.evals ablacao`; `--simular` mostra,
sem gastar nada, quantas execuções e quantos tokens a rodada pode custar.
A medição real roda o Claude Code e pede credencial no ambiente e
orçamento de tokens; nenhuma ablação real foi rodada ainda. Como ler cada
resposta e o que fazer com ela está em [docs/metodo.md](docs/metodo.md);
as opções, em [evals/README.md](evals/README.md#ablação).

## Requisitos

- Python 3.12 ou mais recente.
- git 2.36 ou mais recente (para a ligação dos commits; sem git, use
  `--sem-git`).
- Claude Code instalado e usado na máquina: é dele que vêm as
  transcrições.
- Sistemas testados a cada mudança: Linux, macOS e Windows (Python 3.12
  e 3.13), e a instalação pelo pacote nos três. O que ainda funciona com
  limite em algum ambiente está em
  [docs/portabilidade.md](docs/portabilidade.md).

## Privacidade

O relatório traz nomes reais: de skills, ferramentas, servidores MCP,
arquivos e caminhos da sua máquina. Ele é para ficar com você. Nada é
enviado para fora: `dark auditar` não usa rede. Se `--saida` cair dentro
de um repositório git sem estar ignorado, o comando avisa antes de
gravar, para o relatório não ir parar num commit.

## Evals

`python -m dark.evals` monta casos de avaliação a partir do histórico git
de um repositório (`minerar`), confere cada caso (`validar`) e roda o
agente sobre eles (`calibrar`, `rodar`, `resumir`). `python -m dark.evals
guardar <arquivo.jsonl>` grava no banco de coleta os resultados de uma
rodada, sem duplicar ao repetir (o mesmo que `dark coletar --evals`). O
formato dos casos está em [evals/README.md](evals/README.md).

> **Atenção.** `validar`, `calibrar` e `rodar` executam o comando de
> aceite do repositório avaliado, e os dois últimos rodam um agente que
> edita arquivos e executa comandos. Use só em repositórios seus.

## Plugin

A pasta `plugin/` é um plugin do Claude Code com duas skills, `auditar` e
`coletar`, que orientam o agente a rodar o `dark` instalado. O plugin não
é instalado pelo pip, não substitui o pacote e não o instala; para usar
numa sessão, aponte o Claude Code para a pasta:
`claude --plugin-dir <caminho-do-repositório>/plugin`. Detalhes em
[plugin/README.md](plugin/README.md).

## Desenvolvimento

Esta seção é para quem trabalha no próprio `dark`.

O código, os testes e as mensagens de commit são em inglês; a interface
(relatório, mensagens, ajuda, nomes de comandos e opções) e a
documentação são em português (E18). O [glossário](docs/glossario.md)
traz as traduções e o mapa dos nomes antigos, usados nos diários até o
goal 013. O estado do projeto, os goals e o diário estão em
[pair/ESTADO.md](pair/ESTADO.md); o laço de par (revisor e executor em
sessões separadas) está em [docs/laco-de-par.md](docs/laco-de-par.md).

### Ambiente e testes

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

O workflow `.github/workflows/tests.yml` roda os testes em Linux, macOS e
Windows e, num job separado, gera o wheel, instala-o num venv fora do
checkout e roda `dark` de um diretório temporário, como um usuário.

### Comandos de conferência

O leitor (`src/dark/reader.py`) tem um comando mínimo de conferência, que
só lê:

```bash
.venv/bin/python -m dark.reader            # usa CLAUDE_CONFIG_DIR ou ~/.claude
.venv/bin/python -m dark.reader --config tests/fixtures/config
```

Os indicadores (`src/dark/indicators.py`) são funções puras sobre o que o
leitor devolve. O comando de conferência imprime só contagens; com
`--nomes`, imprime também nomes de skills e ferramentas, e essa saída não
deve ser publicada.

```bash
.venv/bin/python -m dark.indicators --config tests/fixtures/config
```

O inventário (`src/dark/inventory.py`) lista o harness instalado
(instruções, skills, subagentes, hooks, servidores MCP e permissões) por
escopo, só lendo arquivos. Sem `--nomes`, imprime só a tabela de
contagens; com `--nomes`, imprime nomes e falhas, e essa saída não deve
ser publicada.

```bash
.venv/bin/python -m dark.inventory <repo> [--config DIR] [--gerenciado DIR] [--nomes]
```

A repartição do contexto (`src/dark/context_usage.py`) roda `claude -p
/context --no-session-persistence` no repositório e analisa a saída.
Serve de conferência do peso de skills, memória e subagentes; não entra
no relatório (E11, terceira versão).

```bash
.venv/bin/python -m dark.context_usage [repo] [--arquivo F] [--usage N] [--nomes]
```

Os casos de eval (`src/dark/evals/`):

```bash
.venv/bin/python -m dark.evals minerar --repo . --ref origin/main
.venv/bin/python -m dark.evals validar --repo . evals/cases/goal-005-leitor.toml
```

Mais dois pacotes: o motor do scaffold (`src/dark/scaffold/`, aplica e
reverte módulos de harness com manifesto; é ele que `dark iniciar`, `dark
adicionar`, `dark verificar` e `dark remover` usam; conferência com
`python -m dark.scaffold inspecionar|aplicar|reverter`) e o armazenamento
de agregados (`src/dark/store/`, números por sessão e por semana em
SQLite, fora das transcrições; é o banco de `dark coletar`, lido por
`dark auditar`).

> **Atenção.** O venv de desenvolvimento tem o `dark` instalado em modo
> editável e pode vazar para a cópia validada em commits sem
> `pyproject.toml` (ver `evals/README.md`).

### Versão

A versão fica só em `pyproject.toml`; cada versão nova ganha uma entrada
no [registro de mudanças](CHANGELOG.md) (o teste
`tests/test_distribution.py` confere que as duas batem). Se o código
precisar da versão, ela é lida com `importlib.metadata.version("dark")`.
