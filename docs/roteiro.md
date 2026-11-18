# Roteiro

Escrito pelo revisor externo em 2026-11-17 e mantido pelo revisor do
laço. Diz **o que falta fazer e em
que ordem**. O revisor mantém este arquivo atualizado a cada ciclo:
marca o que foi concluído, ajusta a ordem com o motivo e acrescenta o
que descobrir. O porquê do projeto está em `docs/visao.md`.

## Feito

- **Fase 1, piloto manual.** Formato das transcrições, viabilidade dos
  indicadores e experimentos controlados (goals 001, 002, 004).
- **Fase 2, auditoria e placar.** Leitor de transcrições, indicadores,
  inventário do harness, histórico git, ligação de sessão a commit,
  origem das peças, repartição do peso fixo e o comando `dark auditar`,
  com relatório (goals 005 a 013).
- **Fase 3, início.** Formato, validação e mineração de casos de eval,
  sem executar o agente (goal 012).
- **Código em inglês** (goal 014). Código, testes e commits em inglês;
  interface em português, com tabelas de rótulos na camada de
  apresentação (decisão E18).
- **Testes em três sistemas** (goal 015). Workflow em Ubuntu, macOS e
  Windows, Python 3.12 e 3.13, e o levantamento das suposições de
  ambiente em `docs/portabilidade.md`.
- **Motor do scaffold** (goal 016). Operações reversíveis com manifesto,
  plano e códigos de saída; base do item 6.
- **Armazenamento de agregados** (goal 017). Banco local com os
  agregados, retratos do inventário e comparação semanal; base do item
  2.
- **Laço de par** (goal 018). Orquestrador em `tools/pairloop`, revisor
  do laço, hook de limites e `docs/laco-de-par.md`.
- **Correções de portabilidade** (goal 019; era o item 1 da fila).
  Saída em UTF-8, encerramento de processos e `sh` no Windows, caminhos
  com barra normal, avisos de retenção, versão e skill embutida. Os seis
  jobs do workflow passam e nada que impede o uso está em aberto em
  `docs/portabilidade.md`.
- **Executor de evals, construção** (goal 020). Cópia limpa sem
  histórico posterior à base, condições `bare` e `project`, limites,
  aceite, registro em JSON Lines e rodadas. A calibração ficou
  bloqueada por credencial (item 3).
- **Laço pronto para rodar** (goal 021). Push só pelo orquestrador,
  configuração do git bloqueada para os agentes, conferência dos
  arquivos protegidos por conteúdo, defeitos de Windows corrigidos, e o
  executor de evals nos subcomandos de `python -m dark.evals`. Aceito
  com correções na rodada 001: os defeitos do laço que restam só o
  usuário pode corrigir (D1 da rodada 001); os erros da CLI de evals
  entram no goal 022.

- **Casos de eval deste repositório** (goal 022). Onze casos válidos,
  de nove módulos, os cinco da primeira rodada e a tolerância (4 em 15
  execuções por condição) declarada antes de medir; CLI de evals sem
  traceback diante de entrada ruim. Parte do item 3; a calibração
  continua esperando a credencial.
- **Instalação e README** (goal 023). Instalação por `pip install
  "git+<URL>"`, versão 0.1.0, `CHANGELOG.md`, README para quem chega de
  fora e um job que instala o wheel fora do checkout nos três sistemas.
  Parte do item 8; falta o plugin.
- **Comando `dark coletar`** (goal 024). Coleta idempotente para o
  banco de agregados, conferida contra `dark.indicators`. Primeira parte
  do item 2.

- **Endurecimento do laço** (goal 025) e **calibração e rodada completa
  dos evals** (goal 026), feitos fora do laço a pedido do usuário e
  aceitos na revisão 1 da rodada 002. A rodada completa deu 30 de 30 e
  a calibração dos casos médios 4 de 4: efeito teto.

- **Auditoria sobre o banco** (goal 027). `dark auditar` lê do banco,
  com "o que mudou desde a última semana", `--direto`, `--coletar`,
  `--banco`, `dark --versao`, e a correção do registro de coleta no mesmo
  segundo. Fecha o item 2.
- **Plugin do Claude Code** (goal 028). `plugin/` com as skills
  `auditar` e `coletar`; validado por `claude plugin validate`. Faltam
  as pontas (goal 031), a licença e uma sessão real (pedidos ao usuário).
- **Casos de eval difíceis** (goal 029). 16 casos válidos; falta rodá-los
  com credencial.
- **Aceite do executor contra configuração do pytest** (goal 030) e
  **plugin ligado ao README e ao comando** (goal 031), este com teste de
  deriva entre as skills e o `--help`. O 030 deixou de fora arquivos que
  o pytest 9 lê (goal 033).
- **Recomendações por regras fixas** (goal 032, item 5). Cinco regras
  (peça sem uso, arquivo de instruções longo, peso fixo subiu, bloqueio
  de hook repetido, commits sem hash) e três adiadas por falta de dado
  (evals em 100%, modelo mudou, módulo de terceiro). Faltam README e
  CHANGELOG (goal 035); a recomendação "uma seguida produz melhora
  medida" depende da ablação.

- **Nomes de configuração do pytest 9** (goal 033), **ablação de uma
  peça** (goal 034, item 4: comando `python -m dark.evals ablacao`,
  quatro saídas, testado só com o agente falso; a medição real espera
  credencial) e **documento do método** (goal 035, item 7, com
  recomendações no README).

- **`dark iniciar` e `dark remover`** (goal 036, item 6, módulo `base`
  sem terceiros), **documentos da ablação** (goal 037) e **resultados de
  evals no banco** (goal 038: tabela `eval_runs`, `guardar`, regra
  `evals_at_100_percent`).

- **Limites do `guardar`, modelo das sessões e `coletar --evals`** (goals
  039 e 041): inteiro acima de 64 bits recusado com a linha e o motivo;
  banco no esquema 3 com `sessions.model`; regra
  `model_changed_since_last_evals` ligada (só `third_party_module_without_gain`
  segue adiada); `dark coletar --evals` e a recusa de banco dentro de
  repositório git também no `guardar`.

- **Módulo Langfuse e documentos de 036 a 042** (goals 043 e 045, rodada
  004): `dark adicionar langfuse` com o compose oficial da v4.82.0
  (imagens fixas, segredos por variável) e o plugin oficial fixado em
  v1.2.2; README, método, CHANGELOG, skill `coletar` e
  `FUNCIONALIDADES.md` em dia com 036 a 042. Parte do item 6.

- **Módulo Graphify e documentos do Langfuse** (goals 044 e 046, rodada
  004): `dark adicionar graphify` com a skill oficial da 0.9.112 copiada
  sem alteração, hooks `PreToolUse` e `SessionStart`, `graphify-out/` no
  `.gitignore`; os dois módulos aplicados e removidos no mesmo
  repositório deixam a árvore igual; README, método, CHANGELOG,
  glossário e `FUNCIONALIDADES.md` em dia com o Langfuse, com os avisos
  de conteúdo de conversas e de telemetria. Parte dos itens 6 e 7.

- **Documentos do Graphify e correções do motor** (goals 047 e 048,
  rodada 004): subseção do Graphify no README, Anexo A do método,
  glossário e testes de deriva; a linha que um módulo pôs no
  `.gitignore` fica enquanto o caminho literal que ela ignora existir (o
  `remover langfuse` deixava o `.env` com segredos fora do git), e
  nenhum `[aplicado]` quando há conflito. Parte dos itens 6 e 7.

- **Documentos do 048 e medição de ganho de um módulo** (goals 049 e
  050, rodada 004): README e CHANGELOG dizem que a linha do `.gitignore`
  fica enquanto o caminho existir; testes de deriva pegam versão no fim
  de frase; ida e volta com módulo de terceiro marcada ✅ (testes byte a
  byte dos goals 043, 044 e 048). `python -m dark.evals modulo`: condição
  `with_module`, preparação declarada pelo módulo só na cópia, regra de
  ganho em custo e passos, testada com agente e `graphify` falsos; o
  banco ainda não guarda `with_module`. Parte dos itens 5, 6 e 7.

- **Documentos e correções da medição de ganho** (goals 051 e 052,
  rodada 004): seção "Ganho de um módulo" no `evals/README.md`, parágrafo
  no README, método, glossário e CHANGELOG, com teste de deriva contra as
  constantes da regra; a preparação de um módulo que muda, apaga ou troca
  arquivo rastreado da cópia, ou move o `HEAD`, é recusada (código 1,
  nada rodado), e a saída diz quando o acerto sobe com o módulo. Parte
  dos itens 6 e 7.

- **Workflow de testes verde nos três sistemas** (goal 053, rodada 005):
  as quatro falhas da `main` (Docker Compose no Linux e no Windows; três
  só no Windows) corrigidas na camada certa; dois defeitos de produto
  (arquivo de módulo que só difere em CRLF visto como conflito; saída do
  git lida na localidade em `workspace.git`); regra no `CLAUDE.md` de o
  executor conferir o workflow da branch. Os nove jobs da branch passaram.

- **`with_module` no banco e regra de módulo de terceiro** (goals 054 e
  055, rodada 005): esquema 4 (`turns`, `applied_module`,
  `harness_commit`), `guardar` e `coletar --evals` aceitam `with_module`,
  `module_history` lê a medição mais recente de cada `nome:versão`; regra
  `third_party_module_without_gain` (sem ganho ou piora, módulo de
  terceiro aplicado na mesma versão medida: `dark remover`). Nenhuma
  regra do item 5 fica adiada.

- **Documentos do 052, 054 e 055 e formato de `applied_module`** (goals
  056 e 057, rodada 005): README (abertura em dia: mede, indica e prepara
  com módulos), `evals/README.md` (recusa da preparação, esquema 4,
  migração com `.v3.bak`, auditoria), CHANGELOG, glossário e
  `FUNCIONALIDADES.md` (item 4 com 8 de 8), com testes de deriva; o
  `guardar` e o `dark coletar --evals` recusam, linha a linha,
  `applied_module` fora de `nome:versão`, e o esquema do registro diz o
  formato. Parte dos itens 5, 6 e 7.

## Em andamento

Rodada 005, ciclo 4:

- **goal 058** (lote 025): documentos do 057 e `validate_record` sem
  aceitar quebra de linha no fim de um `pattern` (achado da revisão 4).

Depois: a fila sem credencial fica vazia. Medição real dos módulos e da
ablação e calibração dos casos novos (pedem credencial); teste com uma
pessoa de fora (item 7); piloto (item 9).

## Fila, em ordem

Cada item traz o que entrega, do que depende e quando está pronto. Itens
sem dependência entre si podem rodar em paralelo. Os números dos itens
não mudam quando um sai da fila, para que as referências continuem
valendo; o item 1 (portabilidade) foi concluído pelo goal 019.

### 2. Coleta

- **Entrega:** `dark coletar`. Lê as transcrições, calcula os
  indicadores, liga os commits, tira o retrato do inventário e grava
  tudo no armazenamento. Idempotente; pensada para rodar toda semana.
  A auditoria passa a ler do armazenamento, deixa de consultar o git a
  cada execução e ganha a seção "o que mudou desde a última semana".
- **Depende de:** 014 e 017.
- **Pronto quando:** duas coletas seguidas deixam o banco igual; a
  auditoria sobre o banco dá os mesmos números da auditoria direta; e o
  comando leva segundos.
- **Situação:** concluído (goals 024 e 027).

### 3. Executor de evals

- **Situação:** construído no goal 020 (ligado ao comando no goal 021).
  Calibração e rodada completa feitas no
  [goal 026](../pair/goals/026-eval-calibration.md) (2026-11-18): 30
  execuções (5 casos, 2 condições, 3 execuções), 30 "concluiu", 30 aceites;
  4,38 milhões de tokens, 26 minutos. Efeito teto: `bare` e `project`
  acertaram 15/15, e os dois casos médios, que também foram calibrados,
  passaram 4/4. Limites aprovados: 1 milhão de tokens, 40 turnos e 600 s
  por execução, 10 milhões por rodada. Falta um conjunto de casos que o
  agente às vezes falhe; sem ele, a linha de base é só "100%" e os itens 4
  e a medição dos módulos do item 6 não têm o que medir.
  O goal 029 acrescentou cinco casos mais difíceis (16 no total), ainda
  sem rodada: precisa de credencial (pedido ao usuário). O goal 030
  fechou a lacuna do aceite por configuração do pytest (o 033 fecha os
  nomes que restaram).
- **Entrega:** roda o agente, em modo não interativo, sobre um caso de
  eval, em cópia limpa do repositório, várias vezes, em duas condições:
  sem harness e com harness. Aplica o orçamento da decisão E17, começando
  pela rodada de calibração. Grava o resultado de cada execução. Daí sai
  o indicador que ainda falta: acerto na primeira tentativa.
- **Depende de:** 014.
- **A decidir no goal, com registro:** o que é "sem harness" na prática
  (o que é retirado da cópia e do diretório de configuração); como
  isolar a execução do histórico real do usuário; modo de permissão.
- **Pronto quando:** duas rodadas iguais dão taxas de acerto dentro de
  uma tolerância declarada (critério da Fase 3), e a linha de base deste
  repositório está medida.

### 4. Poda por ablação

- **Entrega:** um comando que retira uma peça do harness na cópia de
  avaliação, roda os evals e diz se o resultado caiu. É o que transforma
  "candidato a revisar" em "pode remover" ou "mantenha".
- **Depende de:** 3.
- **Pronto quando:** aplicado a este repositório, classifica pelo menos
  uma peça como removível sem perda, com os números.
- **Situação:** comando entregue no goal 034 (peças: skill, subagente,
  instrução inteira; mínimo de 15 execuções por condição). Falta a
  medição real, que pede credencial e casos que discriminem (pedido ao
  usuário).

### 5. Recomendações do cockpit

- **Entrega:** regras fixas sobre os indicadores e sobre a comparação
  semanal, cada uma com a evidência e uma ação que os evals conseguem
  verificar. Regras previstas:
  - peça sem uso há N semanas com sessão: rodar a ablação;
  - instruções acima do teto de tamanho, ou com muitos itens sem motivo:
    mover procedimentos para skills, apagar o que não tem motivo;
  - peso fixo do harness subiu entre duas coletas: listar o que entrou;
  - hook bloqueia a mesma ação repetidamente: corrigir a causa na
    instrução ou na skill;
  - evals em 100% por várias rodadas: acrescentar casos de falhas
    recentes;
  - o modelo mudou desde a última rodada: rodar os evals com o harness
    reduzido;
  - módulo de terceiro sem ganho medido: desinstalar;
  - commits sem hash registrado: aplicar a regra do commit sem `-q`.
- **Depende de:** 2; as regras de ablação dependem de 4.
- **Situação:** o goal 032 entregou as regras que os dados de hoje
  sustentam; o 038 ligou `evals_at_100_percent`; `model_changed_since_last_evals`
  foi ligada no goal 039; a de módulo de terceiro foi ligada no goal 055,
  sobre a medição que o 054 guarda no banco. Todas as regras previstas
  estão ligadas; falta o critério (recomendação seguida com melhora
  medida), que pede uso real.
- **Pronto quando:** uma recomendação seguida produz melhora medida
  (critério da Fase 5).

### 6. Scaffold

- **Entrega:** `dark iniciar`, `dark adicionar <módulo>` e `dark
  remover <módulo>`, sobre o motor do goal 016. Em repositório novo:
  estrutura mínima e esqueleto dos evals, sem regras nem skills prontas.
  Em repositório existente: auditar antes, propor as mudanças item por
  item, nunca sobrescrever.
- **Módulos da primeira versão**, ambos opcionais e com o contrato
  instalar, verificar, medir, desinstalar:
  - **Langfuse:** rastros de sessão, pelo plugin oficial para Claude
    Code. Padrão a confirmar com o usuário: instância auto-hospedada. O
    módulo nunca grava chaves; indica onde colocá-las.
  - **Graphify:** grafo do repositório para o agente consultar, com
    skill e hook. Tem de provar ganho neste critério: custo e passos em
    tarefas de exploração de código, com e sem ele.
- **Situação:** o goal 036 entregou `dark iniciar` e `dark remover` com
  o módulo `base` (sem terceiros). O goal 042 entregou `dark adicionar`
  (com `--listar`), `dark verificar` e o registro de módulos, provados
  com módulo de teste. A decisão D1 da rodada 003 foi respondida pelo
  usuário: Langfuse auto-hospedado, embarcado como Docker Compose; origem,
  a edição community oficial de cada projeto; versão, a mais recente
  publicada quando o goal for feito, fixada.
- **Próximo:** Langfuse (goal 043) e Graphify (goal 044) estão na
  `main`, documentados (goals 046 e 047), com ida e volta byte a byte
  nos testes, também os dois juntos e com o `.env` ou o grafo do usuário
  no lugar (goal 048): o critério "idêntico ao inicial" está cumprido
  nos testes (goal 049). O "medir" do contrato está no goal 050
  (`python -m dark.evals modulo`), documentado no goal 051 e corrigido
  no goal 052 (preparação só cria arquivos); a medição vai para o banco
  (goal 054) e a auditoria recomenda remover o módulo sem ganho (goal
  055). Falta a medição real de ganho (pede credencial); o
  Langfuse só pode ser medido com as variáveis do `.env` na cópia.
- **Cuidado:** módulo de terceiro executa código na máquina do usuário.
  Versão fixada, e o que mudou é lido antes de atualizar.
- **Depende de:** 016 e do inventário; a medição dos módulos depende
  de 3.
- **Pronto quando:** instalar e desinstalar deixam o repositório
  idêntico ao inicial (critério da Fase 4).

### 7. Documento do método

- **Entrega:** `docs/metodo.md`, para quem vai usar a ferramenta: o
  ciclo de derivação, a tabela de falha para camada, o ciclo de poda e
  como ler o relatório. Em anexo datado, o catálogo de ferramentas por
  tema.
- **Depende de:** nada; fica melhor depois de 3 e 4, com exemplos reais.
- **Situação:** entregue no goal 035; o goal 037 atualiza o trecho da
  ablação. Falta o teste com uma pessoa de fora e um ciclo de derivação
  real.
- **Pronto quando:** uma pessoa que não participou do projeto consegue,
  só com ele e o README, auditar um repositório e fazer um ciclo de
  derivação.

### 8. Distribuição

- **Entrega:** instalação em um comando, em qualquer máquina; o plugin
  do Claude Code; versão e registro de mudanças; README para quem chega
  de fora.
- **Depende de:** 1 (concluído no goal 019).
- **Pronto quando:** instalado do zero em uma segunda máquina, `dark
  auditar` roda sem ajuste manual.
- **Situação:** o goal 023 entregou a instalação, a versão, o registro
  de mudanças, o README e a conferência da instalação no workflow (que
  faz o papel da segunda máquina nos três sistemas, com os arquivos
  sintéticos). Falta o plugin do Claude Code e a opção `dark --versao`
  (proposta no diário 023), num goal seguinte; a etiqueta `v0.1.0` é do
  usuário. Os goals 027 (`--versao`) e 028 (plugin) entregaram essas
  partes; faltam as pontas (goal 031) e a licença (usuário). Motivo da ordem: direção do usuário
  ("tornar a ferramenta utilizável em outros ambientes"), acima da ordem
  da fila.

### 9. Piloto final

- **Entrega:** a ferramenta aplicada a dois repositórios do usuário, com
  o critério de sucesso de `docs/visao.md` medido.
- **Depende de:** 2 a 5.
- **Observação:** é a única etapa que exige o usuário, porque são
  repositórios dele. Vai para o relatório da rodada como pedido, não
  como critério de aceite de um goal.

## Regras de operação

- **Numeração.** O próximo goal é o maior número existente mais um. O
  lote principal de um ciclo leva o próximo número de lote; os paralelos
  levam o mesmo número com uma letra (`010b`, `010c`).
- **Ordem de junção.** Uma branch só entra depois de aceita. Entre
  branches aceitas no mesmo ciclo, a ordem é a dos números dos goals.
- **"Aceito com correções".** Se a branch ainda não entrou: lote novo na
  mesma branch, só com as correções. Se já entrou: goal novo, pequeno.
  Correção de uma linha que o merge de ensaio revela pode ser feita na
  junção, em commit próprio, e fica registrada.
- **Tolerância em conferência.** Tabela "esperado, obtido" tem de bater
  exatamente, ou cada diferença tem explicação escrita. Para taxas de
  acerto de evals, a tolerância é declarada pelo goal que as mede, antes
  de medir.
- **Testes em três sistemas.** O revisor não roda Windows nem macOS.
  Confere pelo resultado do workflow de testes na `main` ou na branch,
  lido da execução, e registra a tabela.
  Toda revisão confere também o workflow da `main` (`gh run list
  --branch main`), não só o da branch: o da `main` ficou vermelho no
  Windows da rodada 002 à 005 sem registro (achado na revisão 1 da
  rodada 005). Job cancelado por falta de máquina do GitHub não é
  defeito; job vermelho bloqueia a junção, salvo falha que já existia
  na `main`, citada.
- **Itens que dependem do usuário** (credencial para evals, repositórios
  do piloto): vão para o relatório da rodada como pedido. Enquanto não
  forem atendidos, o revisor segue com os itens que não dependem deles.
- **Tamanho de lote.** Um lote que estoura o limite de turnos da sessão
  estava grande demais: o próximo revisor o divide, em vez de repetir.

## Guardado para depois

Ideias registradas, sem lugar na fila. Entram só por direção do usuário
ou quando destravarem um item acima.

- Critério para agrupar pedidos em tarefas (decisão E9, em aberto).
- Um comando para o usuário marcar, na hora, que corrigiu o agente.
- Explicar a parte "não explicada" do peso fixo (27% na última medida).
- Detalhe por arquivo de instrução, para dizer onde cortar.
- Marcar um item do relatório como revisado.
- Unificar o git do pacote de evals com o módulo de histórico.
- Histórico de mais de uma máquina.
- Interface gráfica para o cockpit.
- Endurecimento do laço de par: comandos git do orquestrador com
  configuração neutralizada, `.git/config` e `.git/hooks/` no retrato,
  arquivo de hooks regerado a cada sessão, bytecode, comando de testes
  conferido na partida, rascunho do revisor fora das raízes do hook,
  destino de `git clone` conferido pelo hook, executor remove os
  worktrees que criou no rascunho (diário 021, diário 022 e revisões da
  rodada 001). Só o usuário pode fazer: `tools/pairloop/` é protegido
  (D1 da rodada 001).

## Como manter este arquivo

- Ao concluir um item, mova-o para "Feito" com o goal que o entregou.
- Para mudar a ordem, registre o motivo em `docs/decisoes.md`.
- Item novo entra em "Guardado para depois", a menos que a direção do
  usuário diga outra coisa.
- `pair/DIRECAO.md` tem prioridade sobre a ordem daqui.
