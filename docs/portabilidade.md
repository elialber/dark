# Portabilidade: suposições de ambiente

Levantamento do goal 015 ([lote 007b](../pair/entrada/lote-007b.md)),
feito em 2026-11-17 a partir da leitura do código em `origin/main`
(`3b78fcd`, antes da renomeação para inglês) e da primeira execução do
workflow `.github/workflows/tests.yml` em Ubuntu, macOS e Windows. O
resultado dos testes por sistema está no [diário 015](../pair/diario/015.md).

O ambiente de construção é um só: uma máquina, Linux sob WSL2, Claude Code
em linha de comando, versões 2.1.295 a 2.1.326, repositórios no disco Linux
e no disco do Windows montado em `/mnt/c`. Este documento lista o que o
código supõe sobre esse ambiente. O levantamento não corrigiu nada; as
correções são do [goal 019](../pair/goals/019-portability-fixes.md), e a
situação de cada item depois dele está no campo "Situação".

## Como ler

Cada suposição tem quatro campos:

- **Supõe:** o que o código supõe e em que módulo. O nome do módulo vem
  como está hoje e, entre parênteses, o nome depois da renomeação do
  lote 007 (`leitor` → `reader` e assim por diante).
- **Origem:** *documentação* (documentação oficial do Claude Code, do git
  ou do Python) ou *observação* (visto nesta máquina, na amostra de
  transcrições ou num experimento). *Escolha* quando é decisão do projeto,
  sem relação com o que foi observado.
- **Em outro ambiente:** *bloqueia* (o comando falha ou não dá para usar),
  *degrada* (roda, mas o resultado fica incompleto ou errado sem aviso) ou
  *cosmético*.
- **Proposta:** *configurável*, *detectar em tempo de execução* ou
  *degradar com aviso*. Quando faz sentido, mais de uma.
- **Situação (goal 019):** *resolvido* (com o commit), *com aviso* (o
  relatório passa a dizer o limite; com o commit) ou *em aberto* (com o
  motivo).

Quando a leitura do código não basta para saber o efeito, o item diz
"não verificado". A lista do que ficou sem verificação está no diário.

Os identificadores (S1.1, S1.2…) servem para citar o item em goals
futuros.

---

## 1. Sistema e caminhos

### S1.1 Regra que converte o diretório no nome da pasta de projeto

- **Supõe:** a pasta de um repositório sob `<config>/projects/` é o
  caminho absoluto com todo caractere fora de `[A-Za-z0-9]` trocado por
  `-`. A regra está duplicada: `inventario.pasta_projeto`
  (`inventory`) e `auditoria.pasta_de_projeto` (`audit`). Usos: achar a
  memória automática (`projects/<pasta>/memory/MEMORY.md`) no inventário,
  e atribuir falhas de leitura ao repositório auditado na auditoria. O
  leitor não depende dela: o repositório de cada sessão vem do `cwd`
  registrado (E3).
- **Origem:** observação. Não há regra documentada. O teste
  `test_inventario.py` fixa o caso `/mnt/c/Repos/Ex_1` → `-mnt-c-Repos-Ex-1`.
- **Em outro ambiente:** degrada.
  - Windows: `C:\Users\x\repo` daria `C--Users-x-repo`. Não verificado se
    o Claude Code faz o mesmo.
  - Caminho com caractere fora do plano básico do Unicode (emoji, alguns
    ideogramas): o Python troca um ponto de código por um `-`; se o
    Claude Code trocar por unidade UTF-16 (o que é provável, por ser
    JavaScript), sai `--`. Não verificado.
  - Caminho muito longo: o Claude Code pode encurtar o nome da pasta.
    Não verificado.
  - Em todos os casos o efeito é o mesmo: a memória do projeto some do
    inventário e falhas de leitura deixam de ser atribuídas ao
    repositório, sem aviso.
- **Proposta:** detectar em tempo de execução. As transcrições trazem o
  `cwd`; a pasta onde está o arquivo de uma sessão com aquele `cwd` é a
  pasta real. A regra fica como último recurso, com aviso quando a pasta
  calculada não existe e há sessões do repositório. Uma função só, em um
  módulo.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S1.2 Barra como separador ao analisar texto

- **Supõe:**
  - `leitor.analisar_commit` (`reader`) reconhece o executável do git por
    `tokens[i].rsplit("/", 1)[-1] == "git"`. `git.exe`,
    `C:\Program Files\Git\cmd\git.exe` ou `/usr/bin/git.exe` não são
    reconhecidos.
  - `evals/caso` (`evals/case`) recusa `aceite.arquivos` absoluto só por
    `caminho.startswith("/")`. `C:\x` e `\x` passam por essa verificação
    (`..` é pego por `Path.parts` nos dois sistemas).
  - `inventario.importacoes` (`inventory`) só aceita `@caminho` com `.` no
    nome ou com `/`. `@docs\guia` sem extensão não é reconhecido.
  - `relatorio` (`report`) escreve caminhos com `str(Path)`: no Windows,
    com barra invertida (`.claude\skills\x\SKILL.md`), e o repositório
    auditado no cabeçalho também. Os nomes do inventário usam `as_posix`.
    O mesmo relatório mistura as duas barras (confirmado no CI).
- **Origem:** observação (comandos do Bash do Claude Code em Linux).
- **Em outro ambiente:** degrada, pouco. No Windows o Claude Code roda os
  comandos pelo Git Bash, e o modelo costuma escrever `git`; o caso de
  `git.exe` é raro. A verificação de caminho absoluto não abre brecha: o
  `git checkout -- <caminho>` recusa caminho fora do repositório.
- **Proposta:** detectar: comparar o nome sem extensão, com `PureWindowsPath`
  e `PurePosixPath`; usar `Path.is_absolute()` e `drive` na validação do
  caso.
- **Situação (goal 019):** resolvido no relatório (`50d4ba1`):
  `report.path_text` escreve todo caminho com barra normal, em qualquer
  sistema. Em aberto, pelo mesmo motivo dos outros itens que só degradam:
  o reconhecimento de `git.exe` no leitor, a verificação de caminho
  absoluto do caso e o `@caminho` com barra invertida no inventário.

### S1.3 Maiúsculas e minúsculas, letra de unidade

- **Supõe:** caminhos iguais se escrevem igual.
  - `auditoria.selecionar` (`audit`) compara a raiz do repositório
    auditado com a raiz das sessões como `Path`. Em `PosixPath` (Linux e
    macOS) a comparação diferencia maiúsculas; em `WindowsPath`, não.
  - `inventario._Coleta.mcp` (`inventory`) procura o repositório nas
    chaves de `projects` do `~/.claude.json` por `str(repo)` e
    `str(repo.resolve())`, texto exato.
- **Origem:** observação (Linux, sistema de arquivos que diferencia
  maiúsculas).
- **Em outro ambiente:** degrada.
  - macOS: o sistema de arquivos padrão não diferencia maiúsculas, mas o
    `PosixPath` diferencia. `~/Repos/App` e `~/repos/app` são o mesmo
    diretório e duas raízes para o código. A seleção se salva pela
    identidade do repositório (E15, commit inicial), quando o repositório
    existe e tem commits.
  - Windows: não se sabe em que forma o Claude Code grava as chaves de
    `projects` (barra normal ou invertida, letra de unidade maiúscula ou
    minúscula). Se não bater, os servidores MCP locais do projeto somem
    do inventário. Não verificado.
- **Proposta:** detectar: normalizar dos dois lados (`os.path.normcase`,
  barra única, letra de unidade) antes de comparar; no `.claude.json`,
  comparar contra todas as chaves normalizadas.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S1.4 Links simbólicos

- **Supõe:** o mesmo diretório tem uma forma só. O código mistura
  caminhos resolvidos (`Path.resolve()` em `inventario`, `historico`
  (`git_history`), `evals/validacao` (`evals/validation`)) e não
  resolvidos (`leitor.raiz_git_de`, `cli`).
- **Origem:** observação (os repositórios desta máquina não passam por
  link simbólico).
- **Em outro ambiente:** degrada.
  - macOS: `/tmp` → `/private/tmp`, `/var` → `/private/var`; diretórios de
    trabalho sob links são comuns (pastas sincronizadas, `~/Developer`
    apontando para outro volume).
  - Se o `cwd` gravado pelo Claude Code e o caminho passado ao `dark
    auditar` diferirem pelo link, a seleção depende da identidade E15;
    a ligação de commits não sofre (usa `git rev-parse --git-common-dir`
    resolvido). Não verificado em que forma o Claude Code grava o `cwd`.
- **Proposta:** detectar: resolver os dois lados quando o caminho existe,
  e guardar as duas formas quando não existe.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S1.5 Discos montados e tamanho do repositório

- **Supõe:**
  - `inventario._subpastas` (`inventory`) percorre o repositório inteiro
    com `os.walk` atrás de `CLAUDE.md` aninhado, ignorando ocultos e
    `PASTAS_IGNORADAS = {node_modules, venv, __pycache__, dist, build}`.
  - `historico` e `ligacao` (`commit_linking`) chamam o git por processo,
    várias vezes por repositório.
- **Origem:** observação. A lista de pastas é a dos repositórios desta
  máquina (Python e JavaScript). O custo do disco montado foi medido no
  diário 013 (8 s só no inventário de um repositório em `/mnt/c`; 0,1 a
  0,2 s por processo git).
- **Em outro ambiente:** degrada (tempo, e às vezes resultado).
  - Monorepo grande, `target/` (Rust, Maven), `vendor/` (Go, PHP),
    `Pods/` (iOS), `.venv` fica de fora por ser oculto, mas `env/` não:
    a busca fica lenta e pode achar `CLAUDE.md` de dependência.
  - Disco de rede, pasta sincronizada (OneDrive, iCloud), WSL lendo
    `/mnt/c`: cada processo git custa mais.
  - Windows nativo: criar processo é mais caro que em Linux.
- **Proposta:** detectar: listar os `CLAUDE.md` com `git ls-files` (respeita
  o `.gitignore`), com `os.walk` como reserva; configurável: pastas
  ignoradas extras. Degradar com aviso quando a leitura passar de um
  tempo.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S1.6 Diretório do usuário e diretório de configuração

- **Supõe:** a configuração está em `CLAUDE_CONFIG_DIR` ou
  `Path.home() / ".claude"`; o `.claude.json` fica ao lado de `.claude`
  ou dentro de `CLAUDE_CONFIG_DIR`. A função existe duas vezes, com uma
  diferença: `leitor.diretorio_config` (`reader`) não expande `~`, e
  `inventario.diretorio_config` (`inventory`) expande.
- **Origem:** documentação (local da configuração e da variável).
- **Em outro ambiente:**
  - Windows: `Path.home()` usa `USERPROFILE`, que é o que a documentação
    indica. Funciona.
  - `CLAUDE_CONFIG_DIR` com `~` literal (definido por ferramenta que não
    expande, como um arquivo `.env` ou a configuração de uma IDE): o
    leitor procura uma pasta chamada `~` e não acha nenhuma sessão,
    enquanto o inventário acha a configuração. Degrada, sem aviso.
- **Proposta:** uma função só, que expande `~` e variáveis; degradar com
  aviso quando o diretório não existe ou não tem `projects/`.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S1.7 Diretório da política gerenciada

- **Supõe:** `inventario.GERENCIADO_PADRAO` (`inventory`):
  `/etc/claude-code` (Linux), `/Library/Application Support/ClaudeCode`
  (macOS), `C:/Program Files/ClaudeCode` (Windows). Sistema não listado
  cai no de Linux.
- **Origem:** documentação (consultada no goal 009). Nesta máquina o
  diretório não existe; nada foi lido de verdade.
- **Em outro ambiente:** degrada.
  - Windows com o sistema em outra unidade ou `Program Files` em outro
    lugar: a letra `C:` está fixa.
  - Política entregue por outro canal (perfil de gerenciamento no macOS,
    registro no Windows, se a versão em uso aceitar): não é lida.
    Não verificado se a documentação atual descreve esses canais.
  - É justamente o ambiente de empresa, onde a política pesa mais.
- **Proposta:** detectar: `%ProgramFiles%` no Windows; degradar com aviso
  quando o relatório roda em máquina com sinais de gerenciamento e o
  inventário não achou política.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019. A letra `C:`
  continua fixa em `inventory.DEFAULT_MANAGED`.

---

## 2. Claude Code

### S2.1 Versões fora do intervalo observado

- **Supõe:** `leitor` (`reader`) conhece os campos, tipos de registro,
  tipos de anexo, subtipos de sistema e tipos de bloco das versões
  2.1.295 a 2.1.326. Campo desconhecido é contado; campo de que o leitor
  depende ausente ou com outro tipo é `ErroDeFormato` e a sessão inteira
  vira falha (E1 revista, E12). Os obrigatórios: `type`, `uuid`,
  `timestamp`, `sessionId`; `message`, `message.content`, `message.id`,
  `usage.input_tokens`, `usage.output_tokens`; os `id`/`name`/`input` do
  `tool_use`; `tool_use_id` do resultado; `attachment.type`. Não há
  verificação de versão.
- **Origem:** observação (amostra de um mês, um usuário). A documentação
  diz que o formato é interno e muda entre versões
  ([formato-transcricoes.md](formato-transcricoes.md)).
- **Em outro ambiente:** depende da versão.
  - Versão futura que renomeie um campo obrigatório: todas as sessões
    viram falha. Bloqueia, com aviso (as falhas aparecem no relatório).
  - Versão antiga sem `api-request-shape`, `promptSource`, `origin` ou
    `gitOperation`: a repartição do peso fixo some, a separação entre
    pedido humano e automático fica pior, o hash de commit não aparece.
    Degrada, sem aviso específico.
  - O diário 013 já viu duas sessões de versão antiga sem a forma da
    requisição.
- **Proposta:** degradar com aviso: o relatório diz o intervalo de versões
  lido e o intervalo testado, e quais indicadores ficaram sem dado por
  versão. Detectar: uma tabela de "a partir de que versão existe cada
  campo", alimentada pelas próprias transcrições.
- **Situação (goal 019):** com aviso (`50d4ba1`): o cabeçalho do relatório
  diz quantas sessões vêm de versão fora do intervalo testado
  (`reader.TESTED_VERSIONS`, 2.1.295 a 2.1.326) e quais versões. A
  renomeação de campo obrigatório já aparecia como falha de leitura. Em
  aberto: dizer quais indicadores ficaram sem dado por versão.

### S2.2 Pontos de entrada além da linha de comando

- **Supõe:** as sessões são de `entrypoint: "cli"`. O campo é lido e não é
  usado.
- **Origem:** observação. Toda a amostra é `cli`; os experimentos do goal
  004 mostraram `sdk-cli` em `claude -p`, sem `session_id`.
- **Em outro ambiente:** degrada. Não verificado:
  - extensão de IDE e aplicativo de desktop: se gravam no mesmo
    `~/.claude/projects` e no mesmo formato;
  - SDK do agente: se o usuário roda automações, as sessões entram como
    se fossem de pessoa (pedidos humanos, intervenções);
  - sessões na web (claude.ai/code) ou em nuvem: não ficam na máquina;
    somem do relatório.
- **Proposta:** detectar: contar sessões por `entrypoint` no cabeçalho do
  relatório; separar `sdk-*` dos indicadores de pessoa; degradar com
  aviso para valor nunca visto.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S2.3 Locais de configuração por sistema

- **Supõe:** os locais do inventário (CLAUDE.md, `.claude/`, skills,
  subagentes, comandos, hooks, `.mcp.json`, plugins) são os mesmos em
  todo sistema, relativos ao diretório do usuário e ao repositório; só a
  política gerenciada muda (S1.7).
- **Origem:** documentação (tabela do diário 009).
- **Em outro ambiente:**
  - macOS e Windows nativo: os locais relativos valem.
  - Quem usa o Claude Code no Windows e no WSL tem duas configurações
    (`C:\Users\x\.claude` e `/home/x/.claude`), duas pastas de
    transcrições e dois `.claude.json`. O `dark` lê uma por vez. Degrada,
    sem aviso.
- **Proposta:** configurável: aceitar mais de um `--config` e juntar as
  sessões; detectar: no WSL, sugerir o diretório do Windows quando
  existir.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S2.4 O comando `/context` (módulo `contexto`)

- **Supõe:** `contexto` (`context_usage`) roda
  `["claude", "-p", "/context", "--no-session-persistence"]` sem shell,
  com limite de 120 s, e analisa um texto em inglês, com milhar separado
  por vírgula e sufixo `k`/`m`.
- **Origem:** observação (Claude Code 2.1.326, diário 010).
- **Em outro ambiente:**
  - Windows com o Claude Code instalado pelo npm: o executável é
    `claude.cmd`, e `subprocess.run(["claude", ...])` sem shell não acha
    `.cmd`. Bloqueia este módulo. Com o instalador nativo (`claude.exe`)
    funciona. Não verificado qual dos dois é o mais comum.
  - Versão que mude o texto: as linhas vão para `nao_reconhecido`; sem
    nenhuma categoria, `SaidaInvalida`. Degrada com aviso.
  - O módulo não é chamado por `dark auditar`; o efeito fica restrito a
    `python -m dark.contexto`.
- **Proposta:** detectar: `shutil.which("claude")`, que acha `.cmd` no
  Windows; degradar com aviso já existe para o texto.
- **Situação (goal 019):** resolvido (`7db668a`): o executável é resolvido
  com `shutil.which`, que acha `claude.cmd` no Windows; a saída é lida
  como UTF-8. Não exercitado com o Claude Code real no Windows.

---

## 3. Listas e limiares tirados da amostra

### S3.1 Campos, tipos de registro, anexos e blocos conhecidos

- **Supõe:** `leitor.CAMPOS_CONHECIDOS`, `ANEXOS_CONHECIDOS`,
  `SUBTIPOS_DE_SISTEMA`, `BLOCOS_CONHECIDOS` (`reader`) e
  `indicadores.PARTE_DO_ANEXO` (`indicators`).
- **Origem:** observação (a amostra de um mês).
- **Em outro ambiente:** degrada.
  - Campo ou tipo novo: só aparece na contagem de desconhecidos.
    Cosmético.
  - Anexo de tipo novo que é do harness (uma nova forma de instrução, por
    exemplo) vai para "outros anexos", que é da plataforma. A repartição
    do peso fixo pende para a plataforma sem aviso.
  - Bloco novo de assistente (uma ferramenta executada no servidor, por
    exemplo) não vira chamada de ferramenta; o peso morto de
    ferramentas conta como nunca usada uma ferramenta que foi usada.
- **Proposta:** degradar com aviso: quando houver anexo ou bloco
  desconhecido, o relatório diz quantos caracteres ficaram em "outros
  anexos" por tipo, e quantos blocos não foram lidos.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S3.2 Chaves de anexo que repetem conteúdo

- **Supõe:** `leitor._ANEXO_IGNORA` (`reader`) diz, por tipo de anexo,
  quais chaves repetem o texto de outra e não contam no tamanho.
- **Origem:** observação (goal 013).
- **Em outro ambiente:** degrada. Uma chave nova que repete conteúdo
  infla a parte do harness; o "não explicado" absorve o erro nos dois
  sentidos (diário 013, parte mais frágil 2).
- **Proposta:** detectar: calibrar contra o `usage` da primeira resposta
  (S3.5) e avisar quando a soma das partes passar do medido.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S3.3 "Sem arquivo e sem prefixo é embutida"

- **Supõe:** `origem.classificar` (`provenance`): skill anunciada sem
  arquivo no inventário e sem prefixo `algo:` é da plataforma (embutida).
- **Origem:** observação. Os 16 nomes desta máquina batem com os
  embutidos do diário 009.
- **Em outro ambiente:** degrada, sem aviso.
  - Skill de usuário apagada durante o período auditado vira "embutida"
    e sai de "O que chama atenção".
  - Período longo, ou máquina com muitas trocas de skill, piora.
  - Skill entregue por outro canal que o inventário não lê (política
    gerenciada fora do diretório, S1.7) também vira embutida.
- **Proposta:** detectar: guardar, por versão do Claude Code, os nomes
  embutidos vistos (a lista anunciada numa sessão sem nenhuma skill
  instalada é a referência); fora dessa lista, `sem_arquivo`. Degradar
  com aviso: mostrar quantas foram classificadas pela regra.
- **Situação (goal 019):** com aviso (`50d4ba1`): o cabeçalho lista as
  skills classificadas como embutidas só pela regra "sem arquivo e sem
  prefixo" (as cinco primeiras; com mais, a lista completa vai para o
  Apêndice) e diz que uma skill do usuário apagada no período cai na mesma
  regra. A classificação não mudou.

### S3.4 Prefixos que marcam origem na conta

- **Supõe:** `origem` (`provenance`): servidor MCP `claude_ai_*` é
  conector da conta; skill com prefixo que não é nome de plugin instalado
  é da conta; servidor de plugin aparece como `plugin_<plugin>_<nome>`.
- **Origem:** observação (uma conta, um plano).
- **Em outro ambiente:** degrada.
  - Usuário com chave de API, ou por um provedor de nuvem: não tem
    conectores da conta; um servidor que por acaso comece com
    `claude_ai_` seria mal classificado (raro).
  - Conta de organização: não verificado se os conectores têm o mesmo
    prefixo.
  - Plugin removido depois: as skills dele, com prefixo, viram "da conta".
- **Proposta:** configurável (lista de prefixos); degradar com aviso
  quando a contagem `sem_arquivo` ou `conta` for alta em relação ao total.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S3.5 Fator de 3,6 caracteres por token

- **Supõe:** `indicadores.FATOR_CARACTERES_POR_TOKEN = 3.6` (`indicators`)
  converte tamanhos em tokens na repartição do peso fixo.
- **Origem:** observação (duas partes medidas no diário 010: prompt de
  sistema 3,64 e lista de skills 3,57; conteúdo em inglês e português).
- **Em outro ambiente:** degrada. Instruções em chinês, japonês ou
  coreano dão bem menos caracteres por token; instruções com muito
  código, outros valores; outro modelo pode ter outro tokenizador. O
  relatório já diz que é estimativa.
- **Proposta:** detectar: calcular o fator por sessão, dividindo os
  caracteres do primeiro pedido pelos tokens de entrada da primeira
  resposta (os dois já são lidos); usar a mediana do período e mostrar o
  valor usado.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S3.6 Modos de permissão que suprimem rejeições

- **Supõe:** `auditoria.MODOS_SEM_REJEICAO = {bypassPermissions, dontAsk}`
  (`audit`). `auto` fica de fora. Modo desconhecido conta como se
  pudesse haver rejeição.
- **Origem:** documentação (nomes dos modos) e observação (o
  comportamento de `auto`).
- **Em outro ambiente:** degrada.
  - Modo novo que não pergunta: as sessões dele entram como "sem
    rejeição" e baixam a taxa de intervenção sem explicação.
  - Regras `allow` amplas no `settings.json` têm o mesmo efeito de um modo
    sem consulta e não são consideradas.
  - Política gerenciada que proíbe `bypassPermissions`: sem efeito
    negativo.
- **Proposta:** degradar com aviso para modo nunca visto; detectar: usar
  as permissões do inventário (`DetalhePermissoes`) como contexto da
  taxa.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S3.7 Prefixos de comando reconhecidos antes de `git commit`

- **Supõe:** `leitor._PREFIXOS` e `_PALAVRAS_DO_SHELL` (`reader`):
  `sudo`, `env`, `command`, `time`, atribuições `VAR=valor` e as palavras
  `then`, `do`, `else`, `elif`, `if`, `while`, `until`, `{`, `!`. Só a
  ferramenta `Bash` é examinada. `bash -c` e `eval` não são vistos
  (limite declarado).
- **Origem:** observação (comandos da amostra) e conhecimento do shell.
- **Em outro ambiente:** degrada (commits não contados, sem aviso).
  - `nice`, `nohup`, `timeout`, `xargs`, `exec`, `doas`: não reconhecidos.
  - Alias do git (`git ci`), função de shell, script que faz o commit:
    não reconhecidos.
  - Windows: se a versão em uso tiver uma ferramenta de PowerShell, os
    commits feitos por ela não são examinados. Não verificado.
  - `git.exe` (S1.2).
- **Proposta:** configurável (lista de prefixos e de aliases; ler
  `git config --get-regexp alias.` do repositório); detectar: commit na
  janela de uma chamada de ferramenta qualquer, não só de `Bash`,
  aparece como "commit sem chamada reconhecida".
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S3.8 Outras listas e limites

- **Supõe:**
  - `inventario.PROFUNDIDADE_IMPORTACAO = 4` (`inventory`): saltos de
    `@import`;
  - `inventario.PASTAS_IGNORADAS` (S1.5);
  - `evals/mineracao.PADROES_TESTE` (S4.1);
  - `auditoria.QUANTOS_CAROS = 5` e o corte de 5 nomes no corpo do
    relatório;
  - `evals/validacao._SAIDA_GUARDADA = 4000` caracteres.
- **Origem:** documentação (profundidade de importação); escolha (os
  cortes de exibição); observação (as pastas e os padrões).
- **Em outro ambiente:** cosmético para os cortes de exibição; os demais
  estão nos itens citados.
- **Proposta:** configurável, quando houver arquivo de configuração do
  `dark`; até lá, nada.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

---

## 4. Repositório auditado

### S4.1 Padrões de arquivo de teste (mineração de casos)

- **Supõe:** `evals/mineracao.PADROES_TESTE` (`evals/mining`):
  `tests/*`, `test/*`, `test_*.py`, `*_test.py`, `*_test.go`,
  `*.test.[jt]s(x)`, `*.spec.[jt]s(x)`, com `fnmatchcase` (diferencia
  maiúsculas).
- **Origem:** observação (Python, JavaScript e Go).
- **Em outro ambiente:** degrada. Não reconhece `spec/` e `*_spec.rb`
  (Ruby), `*Test.java` fora de `test/`, `*Test.php`, `*Tests.cs` e pastas
  `Tests/` (C#, maiúscula), `__tests__/` (JavaScript), `*_test.exs`
  (Elixir), `*Spec.scala`, `*_test.dart`. Repositório nessas linguagens
  gera poucos ou nenhum candidato, sem aviso.
- **Proposta:** configurável (padrões por repositório); detectar: escolher
  padrões pela linguagem dominante dos arquivos; degradar com aviso
  quando a mineração não achar nenhum arquivo de teste.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S4.2 Comando de aceite

- **Supõe:** `evals/caso` e `evals/validacao` aceitam qualquer comando, em
  texto (passado a `sh -c`) ou em lista (sem shell). O minerado sai sem
  comando.
- **Origem:** escolha.
- **Em outro ambiente:** a parte da linguagem não depende do ambiente; a
  parte do shell está em S5.1. Um comando escrito numa máquina
  (`.venv/bin/pytest`) não roda em Windows (`.venv\Scripts\pytest.exe`).
  Degrada: o caso fica preso ao sistema de quem escreveu.
- **Proposta:** configurável: permitir comando por sistema no caso; o
  diário 012 já anotou o problema do venv editável.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S4.3 Versão do git

- **Supõe:** git 2.36 ou mais recente (`worktree list -z` em `historico`
  (`git_history`)); `%cI`/`%aI`, `for-each-ref --contains`,
  `diff-tree -z`. Não há verificação de versão; git ausente é tratado
  (`GIT_AUSENTE`).
- **Origem:** documentação do git (registrada em `docs/decisoes.md`).
- **Em outro ambiente:** degrada. Git mais antigo (distribuições Linux de
  suporte longo, macOS com o git da Apple antigo) faz o subcomando falhar;
  o repositório vira `ERRO` e os commits ficam "sem ligação", com o
  detalhe só no apêndice.
- **Proposta:** detectar: `git --version` uma vez; degradar com aviso no
  cabeçalho do relatório.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S4.4 Remoto, branch padrão

- **Supõe:** `historico._branch_padrao` (`git_history`): a branch padrão
  é a de `refs/remotes/origin/HEAD`; senão `main`; senão `master`. Ela
  decide "o commit está na branch padrão" e o `git cherry` da reversão.
- **Origem:** observação (repositórios com remoto `origin`) e convenção.
- **Em outro ambiente:** degrada. Remoto com outro nome (`upstream`,
  `github`), branch padrão `develop` ou `trunk`, ou `origin/HEAD` não
  configurado (comum em clone por `git init` + `remote add`): sem branch
  padrão, essas perguntas ficam sem resposta.
- **Proposta:** detectar: `git remote` e `git symbolic-ref
  refs/remotes/<remoto>/HEAD` para cada remoto; configurável
  (`--branch-padrao`, que a função já aceita como parâmetro).
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S4.5 Histórico disponível

- **Supõe:**
  - identidade do repositório = commits raiz (E15; `cli.identidade_git`);
  - amend detectado por reflog e estrutura; commits alcançáveis por ref,
    HEAD de worktree ou reflog (`historico`);
  - o commit da sessão ainda está no repositório quando a auditoria roda.
- **Origem:** observação (repositórios desta máquina, histórico completo,
  reflog ativo, branches de goal apagadas só depois da junção).
- **Em outro ambiente:** degrada.
  - Clone raso (`--depth`): o commit raiz é o da fronteira; dois clones do
    mesmo repositório têm identidades diferentes.
  - Reflog desligado ou expirado, ou repositório recém-clonado: amend só
    pela estrutura.
  - Fluxo de squash-merge com branch apagada: os commits da sessão saem
    do histórico e a chamada fica "sem ligação".
  - Repositório sem commits: identidade nula, seleção só por caminho.
- **Proposta:** degradar com aviso (o relatório já separa os motivos de
  "sem ligação"; falta dizer "clone raso" e "reflog vazio"). Detectar:
  `git rev-parse --is-shallow-repository`. A ligação feita na coleta
  (E2, E10) resolve o caso do squash.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S4.6 Repositório da sessão pelo `cwd`

- **Supõe:** `leitor.raiz_git_de` (`reader`) acha a raiz pelo `.git` no
  disco; em worktree, devolve o principal se o `gitdir` contiver
  `worktrees` e `.git`. `inventario._raiz_principal` (`inventory`) faz o
  mesmo pela forma `<repo>/.git/worktrees/<nome>`.
- **Origem:** documentação do git (layout de worktree) e observação.
- **Em outro ambiente:** degrada pouco. `--separate-git-dir`, submódulo
  e `GIT_DIR` externo não seguem a forma; a sessão fica com o diretório
  do próprio worktree ou submódulo como repositório. Comando com `cd` para
  outro repositório fica no do `cwd` (limite da E3).
- **Proposta:** detectar: `git rev-parse --git-common-dir`, quando o
  caminho existe, no lugar da leitura do arquivo.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

---

## 5. Execução de processos

### S5.1 `sh -c` no comando de aceite

- **Supõe:** `evals/validacao.rodar_aceite` (`evals/validation`) roda
  comando em texto com `["sh", "-c", comando]`, e trata os códigos 126 e
  127 como "o comando não rodou".
- **Origem:** observação (Linux) e convenção POSIX.
- **Em outro ambiente:**
  - macOS: `sh` existe. Funciona.
  - Windows nativo: `sh` só existe se a pasta `bin` do Git for Windows
    estiver no `PATH`. A instalação padrão do Git coloca só `cmd`. Sem
    `sh`: `OSError`, o caso sai como "comando não roda". Bloqueia a
    validação de caso com comando em texto. Com o comando em lista,
    funciona.
  - No Windows, `cmd` sinaliza comando inexistente com 9009, não 127.
- **Proposta:** detectar: procurar `sh` com `shutil.which`; no Windows,
  procurar o `bash` do Git; sem nenhum, degradar com aviso e pedir comando
  em lista. Configurável: campo `shell` no caso.
- **Situação (goal 019):** resolvido (`b76532d`). Decisão: o comando em
  texto continua rodando com `sh -c`. No Windows, o `sh` é procurado no
  `PATH` e, se não estiver, ao lado do git (`<Git>\cmd\git.exe` →
  `<Git>\bin\sh.exe`), que é a instalação padrão do Git for Windows. Sem
  nenhum, o caso sai como "comando não roda" com a mensagem do que
  instalar, ou de escrever o comando em lista. Em Linux e macOS, nada
  muda.

### S5.2 Encerramento do grupo de processos

- **Supõe:** `evals/validacao.rodar_aceite` (`evals/validation`) cria o
  processo com `start_new_session=True` e, no estouro de tempo, mata o
  grupo com `os.killpg(proc.pid, signal.SIGKILL)`.
- **Origem:** documentação do Python (POSIX).
- **Em outro ambiente:**
  - macOS: funciona.
  - Windows: `start_new_session` é ignorado e `os.killpg` e
    `signal.SIGKILL` não existem. No primeiro estouro de tempo a
    validação levanta `AttributeError`, que não é capturado: o comando
    termina com erro em vez de "tempo esgotado". Bloqueia o uso do limite
    de tempo, que é o caso comum de teste que trava.
  - Mesmo corrigida a chamada, `proc.kill()` no Windows não mata os
    filhos; o diretório temporário pode não ser apagado por arquivo
    aberto.
- **Proposta:** detectar o sistema: no Windows, criar com
  `CREATE_NEW_PROCESS_GROUP` e encerrar a árvore (`taskkill /T /F /PID`
  ou objeto de job); degradar com aviso se a limpeza do temporário falhar.
- **Situação (goal 019):** resolvido (`b76532d`): no Windows o processo
  nasce com `CREATE_NEW_PROCESS_GROUP` e, no estouro, a árvore é encerrada
  com `taskkill /T /F`, e o filho direto com `kill`. Em POSIX continua
  `killpg`. Se o diretório temporário não puder ser apagado (arquivo ainda
  em uso), a validação tenta de novo e, persistindo, termina com aviso em
  vez de exceção.

### S5.3 Limites de tempo

- **Supõe:**
  - `contexto` (`context_usage`): 120 s fixos para `claude -p /context`;
  - `evals/validacao`: o `tempo_limite` do caso (padrão do módulo
    `caso`), medido com `time.monotonic`;
  - git em `historico`, `cli` e `evals/git`: sem limite.
- **Origem:** escolha; os tempos de git observados no diário 013.
- **Em outro ambiente:** degrada. Em máquina lenta ou disco de rede, o
  primeiro `claude` pode passar de 120 s (atualização automática,
  autenticação). Um git travado (repositório em disco que caiu, `fsmonitor`
  de outra ferramenta) trava o `dark auditar` sem limite.
- **Proposta:** configurável (limites); degradar com aviso: limite por
  chamada de git, e o repositório que estourar vira `ERRO` com motivo.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S5.4 Executáveis pelo `PATH`

- **Supõe:** `git` e `claude` são achados pelo `PATH` do processo.
- **Origem:** observação.
- **Em outro ambiente:** `git` funciona nos três sistemas (`git.exe`).
  `claude` no Windows: ver S2.4. IDE que lança o `dark` com `PATH`
  reduzido (aplicativo de macOS aberto pelo Finder) não acha nenhum dos
  dois. Degrada, com a situação `GIT_AUSENTE` já relatada.
- **Proposta:** detectar com `shutil.which` e dizer no cabeçalho qual
  executável foi usado.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

---

## 6. Localidade

### S6.1 Formato de números no relatório

- **Supõe:** `relatorio.n` e `relatorio.pct` (`report`) escrevem número no
  formato brasileiro (1.234.567 e 12,5%), e o texto é em português.
- **Origem:** escolha.
- **Em outro ambiente:** cosmético. Para quem lê em inglês, `1.234` parece
  "um vírgula dois".
- **Proposta:** configurável, junto com o idioma do relatório, quando
  houver.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019 (cosmético).

### S6.2 Datas e fuso

- **Supõe:** tudo em UTC. Horário sem fuso é tomado como UTC
  (`leitor.instante`); o relatório escreve `AAAA-MM-DD HH:MM UTC`
  (`relatorio.quando`); `--dias` conta a partir de agora em UTC.
- **Origem:** documentação (as transcrições gravam `Z`) e escolha.
- **Em outro ambiente:** cosmético. Quem está em UTC−3 vê as sessões da
  noite no dia seguinte. `--ate` sem fuso é UTC, não hora local, o que
  pode surpreender.
- **Proposta:** configurável: mostrar também no fuso local
  (`datetime.astimezone()`), mantendo UTC no cálculo.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019 (cosmético).

### S6.3 Texto do `/context` em inglês

- **Supõe:** `contexto.analisar` (`context_usage`) procura rótulos em
  inglês ("Free space", "Autocompact buffer"…) e números com vírgula de
  milhar.
- **Origem:** observação (2.1.326).
- **Em outro ambiente:** se o Claude Code passar a traduzir a saída, ou
  formatar número pelo idioma do sistema, as categorias não são achadas.
  Degrada com aviso (`SaidaInvalida`). Não verificado se o Claude Code
  tem saída traduzida.
- **Proposta:** degradar com aviso (já existe).
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019; o aviso já
  existia.

### S6.4 Codificação de arquivos

- **Supõe:** transcrições, instruções, skills, `settings.json` e
  `.claude.json` em UTF-8 (`errors="replace"` nos textos; `json` nos
  objetos). O cabeçalho `---` precisa estar na primeira linha, exata.
- **Origem:** documentação (o Claude Code grava JSON em UTF-8) e
  observação (arquivos de harness feitos nesta máquina).
- **Em outro ambiente:** degrada.
  - Arquivo salvo com marca de ordem de bytes (BOM), comum em editores no
    Windows: `"\ufeff---".strip()` não é `---`, então o cabeçalho da skill
    não é lido e a descrição conta zero; JSON com BOM falha no
    `json.loads` e vira falha de leitura.
  - Arquivo em UTF-16 (o Bloco de Notas antigo, redirecionamento do
    PowerShell 5): ilegível, vira texto com caracteres trocados.
  - Quebra de linha CRLF: tratada (`splitlines`, `rstrip("\r\n")`).
- **Proposta:** detectar: ler com `utf-8-sig`; reconhecer BOM de UTF-16;
  degradar com aviso quando houver caracteres de substituição.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S6.5 Codificação da saída dos processos

- **Supõe:**
  - `historico.executor_padrao` (`git_history`) força `LC_ALL=C` e decodifica
    a saída do git como UTF-8. Correto em todo sistema.
  - `cli._git` e `evals/git.executor_padrao` (`evals/git`) usam
    `text=True` sem `encoding`: o Python decodifica com a codificação da
    localidade.
  - `evals/validacao._final` decodifica a saída do aceite como UTF-8 com
    substituição.
- **Origem:** observação (Linux, localidade UTF-8).
- **Em outro ambiente:**
  - Windows: a codificação da localidade é `cp1252` (ou outra página de
    código). `evals/git.assunto` lê a mensagem do commit, que o git
    entrega em UTF-8; um assunto com "Á" (bytes `C3 81`) tem um byte que
    não existe em `cp1252` e levanta `UnicodeDecodeError`. Bloqueia a
    mineração em repositório com mensagens acentuadas. Outros acentos
    viram texto trocado (cosmético).
  - Linux com localidade `C` ou `POSIX` (contêiner mínimo): Python 3.12
    já usa UTF-8 nesse caso. Funciona.
  - Saída do aceite em `cp1252` (ferramentas nativas do Windows): vira
    caracteres de substituição. Cosmético.
- **Proposta:** detectar: passar `encoding="utf-8", errors="replace"` em
  todas as chamadas ao git (o git escreve UTF-8 por padrão).
- **Situação (goal 019):** resolvido (`7db668a`): toda leitura de saída de
  processo em modo texto passa `encoding="utf-8"` (`cli._git`,
  `evals/git`, `context_usage`); `git_history` já fazia isso. Um teste
  (`test_process_output_is_never_decoded_with_the_locale`) percorre o
  código e falha se aparecer chamada nova sem `encoding`.

### S6.6 Codificação do terminal

- **Supõe:** `cli._auditar` (`cli`) escreve o relatório com
  `sys.stdout.write`; o texto tem acentos, `—` e `→`. Os módulos com
  `main` imprimem nomes de skills e de arquivos.
- **Origem:** observação (terminal Linux em UTF-8).
- **Em outro ambiente:**
  - Windows, saída para o console: o Python usa a API Unicode do console.
    Funciona.
  - Windows, saída redirecionada (`dark auditar > relatorio.md`, pipe,
    IDE, agendador de tarefas): o Python usa `cp1252`, que não tem `→`.
    `UnicodeEncodeError` no meio do relatório. Bloqueia o uso com
    redirecionamento; `--saida` funciona, porque grava em UTF-8. Com
    `PYTHONUTF8=1`, funciona.
  - macOS e Linux com localidade UTF-8: funciona.
- **Proposta:** detectar: `sys.stdout.reconfigure(encoding="utf-8")`
  quando a saída não é terminal, ou trocar os caracteres fora de
  `cp1252`; degradar com aviso.
- **Situação (goal 019):** resolvido (`7db668a`): todo comando (`dark`,
  `dark.reader`, `dark.indicators`, `dark.inventory`,
  `dark.context_usage`, `dark.evals`, `dark.scaffold`) passa a saída
  padrão e a de erro para UTF-8 quando elas não estão em UTF-8
  (`dark.console.utf8_output`), salvo se o usuário definiu
  `PYTHONIOENCODING`. Terminal UTF-8 e console do Windows ficam como
  estão.

### S6.7 Resposta da confirmação

- **Supõe:** `cli._confirmar` aceita "s" ou "sim".
- **Origem:** escolha.
- **Em outro ambiente:** cosmético; quem responde "y" recebe "nada foi
  gravado".
- **Proposta:** configurável com o idioma; aceitar também "y" e "yes".
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019 (cosmético).

---

## 7. Dados por máquina

### S7.1 As transcrições são locais

- **Supõe:** todo o histórico de uso está em `<config>/projects/` desta
  máquina. O relatório diz "todo o histórico" quando não há `--dias`.
- **Origem:** documentação (local das transcrições) e observação.
- **Em outro ambiente:** degrada, sem aviso.
  - Quem usa duas máquinas (trabalho e casa, notebook e servidor remoto
    por SSH, contêiner de desenvolvimento) tem o histórico repartido; o
    relatório de cada uma mostra uma parte e chama de todo.
  - Contêiner de desenvolvimento ou máquina efêmera (Codespaces, CI):
    as transcrições somem com o ambiente.
  - Windows e WSL na mesma máquina são dois históricos (S2.3).
  - Sessões na web ou na nuvem não estão em nenhuma máquina (S2.2).
- **Proposta:** configurável: aceitar vários diretórios de configuração e
  juntar por identidade de repositório (E15 já permite caminhos
  diferentes); degradar com aviso: o cabeçalho diz de que máquina e de
  quais diretórios vieram as sessões.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

### S7.2 Limpeza automática das transcrições

- **Supõe:** as transcrições do período estão no disco. O código não lê
  o ajuste de limpeza do Claude Code.
- **Origem:** documentação: o Claude Code apaga transcrições antigas
  (`cleanupPeriodDays`, 30 dias por omissão). A amostra desta máquina tem
  um mês, compatível com isso.
- **Em outro ambiente:** degrada, sem aviso. "Todo o histórico" é, na
  prática, o último mês, a menos que o usuário tenha mudado o ajuste.
  `--dias 90` devolve 30 dias sem dizer.
- **Proposta:** detectar: ler `cleanupPeriodDays` do `settings.json` do
  inventário e avisar quando `--dias` passar dele ou quando a sessão mais
  antiga estiver perto do limite. A coleta (E2, E10) resolve de vez.
- **Situação (goal 019):** com aviso (`50d4ba1`): o relatório lê
  `cleanupPeriodDays` (política gerenciada, depois configurações do
  usuário), mostra o valor quando definido e avisa quando o recorte pedido
  (`--dias`) começa antes do limite de retenção. Sem `--dias`, a linha
  "Alcance" continua dizendo que sessões antigas podem ter sido apagadas.

### S7.3 O repositório auditado está na mesma máquina

- **Supõe:** a ligação de commits e o inventário leem o repositório no
  caminho gravado na sessão.
- **Origem:** observação.
- **Em outro ambiente:** degrada. Sessões feitas em outra máquina, com as
  transcrições copiadas, apontam para caminhos que não existem aqui; o
  `cwd` de Windows (`C:\…`) lido em Linux nem é um caminho absoluto para
  o `Path` de Linux. A seleção por identidade (E15) não acontece, porque
  a raiz não existe.
- **Proposta:** configurável: mapa de caminhos (prefixo de lá → prefixo
  daqui); detectar: reconhecer `cwd` de outro sistema com
  `PureWindowsPath`.
- **Situação (goal 019):** em aberto: degrada e não está entre os três
  mais perigosos do diário 015; fora do escopo do goal 019.

---

## Fechamento: o que impede e o que só reduz

A lista junta a leitura do código com a primeira execução do workflow.
Os números da execução estão no [diário 015](../pair/diario/015.md).

### Impede hoje o uso em macOS

Nenhum bloqueio achado. A leitura não encontrou chamada exclusiva de
Linux, e os 385 testes passam no macOS, em Python 3.12 e 3.13. O que
muda no macOS é qualidade: S1.3 (maiúsculas), S1.4 (links simbólicos de
`/tmp` e `/var`) e S4.3 (git antigo da Apple). Os testes não exercitam
nenhum dos três.

### Impede hoje o uso em Windows nativo

Em ordem de quanto afeta o uso comum. "Confirmado" quer dizer que um
teste do CI no Windows falhou por esse motivo.

1. **S6.6** (confirmado): `dark auditar` com a saída redirecionada ou em
   pipe quebra com `UnicodeEncodeError` (o `→` do relatório). Contorno:
   `--saida` ou `PYTHONUTF8=1`. É o caminho principal da ferramenta.
   **Resolvido** (`7db668a`).
2. **S5.2** (confirmado): validação de caso com estouro de tempo levanta
   `AttributeError` (`os.killpg`), e o diretório temporário fica preso
   pelo processo que não morreu. **Resolvido** (`b76532d`).
3. **S5.1**: validação de caso com comando em texto falha sem `sh` no
   `PATH`. No executor do GitHub o `sh` existe (é o do Git); numa
   instalação padrão do Git, não. **Resolvido** (`b76532d`): acha o `sh`
   do Git for Windows ou diz o que instalar.
4. **S6.5** (confirmado, em parte): a mineração entrega o assunto do
   commit com acentos trocados (`cálculo` vira `cÃ¡lculo`). Com certos
   caracteres (`Á`, por exemplo), o mesmo defeito vira
   `UnicodeDecodeError`; esse caso não foi exercitado. **Resolvido**
   (`7db668a`).
5. **S2.4**: `python -m dark.contexto` não acha o `claude` instalado pelo
   npm (`claude.cmd`). **Resolvido** (`7db668a`), sem teste com o Claude
   Code real no Windows.

Depois do goal 019, nenhum item desta lista está em aberto. A situação
medida no CI está no [diário 019](../pair/diario/019.md).

Das outras 22 falhas do Windows, 3 mostram a barra invertida nos
caminhos do relatório (S1.2, cosmético; **resolvido** em `50d4ba1`). As 19 restantes são dos testes,
não do código: montam JSON com caminho do Windows sem escapar a barra
invertida, usam caminho do Windows dentro de comando de `sh`, usam
caminho POSIX como chave de dicionário ou criam arquivo com `*` no nome.
Detalhe no diário.

### Só reduz a qualidade do resultado

Em ordem de dano provável, do maior para o menor:

1. **S7.2**: a limpeza automática corta o histórico em 30 dias, e o
   relatório não diz. **Com aviso** (`50d4ba1`).
2. **S3.3**: skill de usuário apagada vira embutida e sai de "O que chama
   atenção". **Com aviso** (`50d4ba1`).
3. **S2.1**: versão fora do intervalo: indicadores somem sem aviso
   específico, ou todas as sessões viram falha. **Com aviso** (`50d4ba1`).

Os itens 4 a 14 seguem em aberto: o goal 019 pediu só os três primeiros.
A exceção é a parte de S1.2 que toca o relatório, corrigida.
4. **S7.1 / S2.3**: histórico repartido entre máquinas, ou entre Windows
   e WSL, tratado como completo.
5. **S3.7**: commits feitos por prefixo, alias ou script não reconhecidos
   não entram na contagem.
6. **S4.5 / S4.4**: clone raso, squash-merge, remoto que não é `origin`,
   branch padrão fora de `main`/`master`.
7. **S1.1**: pasta de projeto calculada errada; a memória some do
   inventário.
8. **S3.5**: fator de 3,6 em instruções de outro idioma.
9. **S3.4 / S3.6**: prefixos de conta e modos de permissão de outro
   plano ou versão.
10. **S6.4**: arquivos de harness com BOM ou em UTF-16.
11. **S4.1**: padrões de teste de outras linguagens na mineração.
12. **S1.5**: tempo em repositório grande ou em disco montado.
13. **S1.3 / S1.4 / S1.2**: maiúsculas, links simbólicos e separadores.
14. **S6.1 / S6.2 / S6.7**: número, data e confirmação (cosméticos).
