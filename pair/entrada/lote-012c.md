# Lote 012c (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 2),
sobre a `main` em `e49466f`. Roda ao mesmo tempo que os lotes 012 (goal
030, executor de evals) e 012b (goal 031, plugin e README), cada um no
seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 032. O orquestrador já criou o seu worktree, na
branch `goal-032`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` (em especial
"Saúde se mede, não se sente", o cockpit e o que ficou de fora: sem nota
única, sem recomendação gerada por IA), `docs/roteiro.md` (item 5),
`docs/decisoes.md` (E14, E16 e os registros dos goals 007 e 027),
`pair/diario/027.md`, `src/dark/audit.py`, `src/dark/store_audit.py`,
`src/dark/report.py` e `src/dark/indicators.py`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
texto do relatório, mensagens, diário e goal em português; valor interno
que aparece na saída passa por tabela de rótulos.

## Por que este goal

O cockpit do usuário é "recomendações de melhoria e acompanhamento"
(`docs/visao.md`). Os dados já existem (indicadores, banco, "o que
mudou"); falta o relatório dizer o que fazer, por **regras fixas**, cada
uma com a evidência que a dispara e uma ação que dá para verificar. É o
item 5 do roteiro.

## Goal 032: recomendações por regras fixas

Crie `pair/goals/032-recommendations.md` com o texto desta seção.

### 1. Módulo de regras

`src/dark/recommend.py` (novo, funções puras sobre o `Audit` e, quando
houver, o `Changes` do goal 027): cada regra recebe os dados e devolve
zero ou mais `Recommendation` com: identificador estável da regra (inglês),
evidência (números e nomes que vêm do relatório, nunca inventados), ação
em uma frase (português) e como verificar a ação (um comando ou um
indicador que muda). Nada de nota única, de ordenação por "gravidade
total" nem de texto gerado.

Regras previstas no roteiro, das quais **implemente as que os dados de
hoje sustentam** (escolha e justifique no diário; no mínimo quatro) e
liste as demais como "adiadas, falta o dado X":

- peça com arquivo sem uso há N semanas, com sessão no período: candidata
  à ablação (o comando de ablação ainda não existe: diga "candidata à
  ablação (item 4 do roteiro)", sem prometer o comando);
- arquivo de instruções acima de um teto de tamanho: mover procedimento
  para skill, apagar o que não tem motivo. O teto **não existe** em
  `docs/`: adote um padrão, marque "padrão a confirmar", e deixe-o
  numa constante com nome, fácil de trocar;
- peso fixo subiu entre duas coletas: listar o que entrou
  (`inventory_diff`);
- hook que bloqueia a mesma ação repetidamente: corrigir a causa na
  instrução ou na skill (use o que `indicators.py` já mede de bloqueios);
- evals em 100% por várias rodadas: só se houver dado no banco ou
  recebido por opção; senão, adiada;
- modelo mudou desde a última rodada de evals: idem;
- módulo de terceiro sem ganho medido: adiada (não há módulo ainda);
- commits sem hash registrado: aplicar a regra do commit sem `-q` (o
  relatório já mostra esse indicador; a recomendação o liga à regra do
  `CLAUDE.md` deste projeto sem citá-lo: diga a regra em geral).

Regra só dispara com o dado que a sustenta; "sem dados" ou "não guardado
pelo banco" nunca vira recomendação (como na seção do goal 027, que diz
"o banco não guarda").

### 2. No relatório

Seção "Recomendações" em `src/dark/report.py`, depois de "O que mudou",
com uma linha por recomendação (regra, evidência, ação, verificação), ou
uma linha "Nenhuma regra disparou com os dados disponíveis" quando não
houver. A seção vale para a auditoria direta e para a pelo banco (as
regras que dependem de dados do banco dizem, quando não disparam por
falta do dado, que o banco é necessário: uma linha só para todas).

### 3. Testes

`tests/test_recommend.py` (novo), escritos antes do código: cada regra
implementada com um caso que dispara e um que não dispara, com limites
exatos (N-1 e N semanas; teto menos 1 e teto); auditoria sintética
completa ponta a ponta, pela CLI, mostrando a seção; auditoria sem dados
não dispara nada e não dá traceback.

### Arquivos que você pode criar ou alterar

- `pair/goals/032-recommendations.md` e `pair/diario/032.md` (novos);
- `src/dark/recommend.py` (novo), `src/dark/report.py`,
  `src/dark/audit.py` e `src/dark/store_audit.py` (só o necessário para
  passar os dados às regras);
- `tests/test_recommend.py` (novo) e, se for preciso ajustar a saída
  esperada, `tests/test_audit.py` e `tests/test_audit_store.py`.

Nada mais. Em especial, não toque em `src/dark/cli.py`,
`src/dark/evals/`, `README.md`, `CHANGELOG.md`, `plugin/`, `evals/`,
`docs/`, `.github/` nem `pair/ESTADO.md`: os lotes 012 e 012b e o revisor
mexem neles. Proponha no diário a linha do `CHANGELOG.md` e o texto do
README; o revisor os leva ao lote seguinte.

### Critério de aceite

1. `python -m pytest -q` passa.
2. **Conferência independente**, tabela "esperado, obtido": para cada
   regra implementada, o número que a evidência cita (semanas sem uso,
   tamanho do arquivo, bloqueios, peso) conferido contra uma fonte que
   não é a regra: `wc`, contagem direta no arquivo sintético, `sqlite3`
   no banco sintético. Sem diferença não explicada.
3. Relatório completo de uma auditoria sintética pelo banco e outra
   direta, com a seção nova, no diário.
4. Sondagens próprias, com a saída no diário: banco com uma semana só;
   repositório sem sessões; arquivo de instruções exatamente no teto;
   peça removida do disco depois de usada. Nenhum traceback; nenhuma
   recomendação sem evidência.
5. Cada ação recomendada tem de ser algo que o próprio usuário consegue
   fazer e verificar; diga no diário como se verifica cada uma.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Teste antes do código.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/032.md` (o que fez, tabelas, decisões
  "padrão a confirmar", regras adiadas e por quê), faça commit, `git push
  -u origin goal-032` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
