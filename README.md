# dark

Ferramenta de linha de comando para quem usa o Claude Code. Ela lê as
transcrições que o Claude Code grava na sua máquina e mostra, para um
repositório, como está o harness dele (instruções, skills, subagentes,
hooks, servidores MCP, permissões): quanto ele pesa em cada pedido, o que
foi instalado e nunca é usado, quanto as sessões custaram, onde você
precisou intervir. O objetivo do projeto é também instalar e manter esse
harness; nesta versão (0.1.0), a ferramenta mede e indica o que mudar,
com evidência, mas ainda não instala nada. O que ela faz e o que ainda
não faz está no [registro de mudanças](CHANGELOG.md).

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

## Recomendações

O relatório traz uma seção "Recomendações", feita por regras fixas: sem nota
única e sem texto gerado. Cada linha dá a regra, o número ou o nome que a
disparou, uma ação que você mesmo faz e como conferir depois. Há cinco
regras: peça sem uso há semanas, arquivo de instruções grande, peso do
inventário que subiu, bloqueios repetidos de hook e commits sem hash. As
regras de peça sem uso e de peso do inventário dependem do banco de coleta
(`dark coletar`); as demais funcionam na leitura direta. Os limites (4 semanas, 200
linhas, 3 bloqueios) são padrões a confirmar, constantes em
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
agente sobre eles (`calibrar`, `rodar`, `resumir`). O formato dos casos
está em [evals/README.md](evals/README.md).

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

Dois pacotes ainda sem uso pelo `dark auditar`: o motor do scaffold
(`src/dark/scaffold/`, aplica e reverte módulos de harness com
manifesto; conferência com `python -m dark.scaffold
inspecionar|aplicar|reverter`) e o armazenamento de agregados
(`src/dark/store/`, números por sessão e por semana em SQLite, fora das
transcrições).

> **Atenção.** O venv de desenvolvimento tem o `dark` instalado em modo
> editável e pode vazar para a cópia validada em commits sem
> `pyproject.toml` (ver `evals/README.md`).

### Versão

A versão fica só em `pyproject.toml`; cada versão nova ganha uma entrada
no [registro de mudanças](CHANGELOG.md) (o teste
`tests/test_distribution.py` confere que as duas batem). Se o código
precisar da versão, ela é lida com `importlib.metadata.version("dark")`.
