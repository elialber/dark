# Goal 034 — Ablação de uma peça do harness

Texto do [lote 013b](../entrada/lote-013b.md), seção "Goal 034", com a
regra de decisão e o orçamento escritos aqui **antes** de qualquer medida
(regra "Tolerância em conferência" de `docs/roteiro.md`).

## 1. Comando

`python -m dark.evals ablacao` recebe a peça (tipo e nome, como o
inventário os chama) e:

1. localiza a peça no harness do commit `--harness` (padrão `HEAD`), pelo
   inventário (`dark.inventory`), só no escopo do projeto;
2. monta a cópia limpa na condição `project` (harness completo) e uma
   segunda, na condição nova `ablated`, igual à primeira menos a peça,
   retirada **na cópia**; o repositório de origem só é lido;
3. roda os mesmos casos e as mesmas repetições nas duas condições, pelo
   executor que já existe (`run_round`);
4. aplica a regra de decisão abaixo e imprime uma de quatro saídas, com
   os números;
5. respeita o orçamento da E17 e nunca roda sem credencial no ambiente
   (a "confirmação" que o executor já exige: sem ela, código 3).

Peças suportadas: `skill` (a pasta da skill), `subagent` (o arquivo do
agente) e `instruction` (um arquivo de instrução inteiro: `CLAUDE.md`,
`rules/x.md`). Recusadas, com mensagem: `hook`, `mcp` e `permission`,
porque vivem dentro de arquivos de configuração compartilhados com outras
peças (`settings.json`, `.mcp.json`); retirá-las pede editar JSON, e um
erro ali muda mais do que a peça.

## 2. Regra de decisão

Declarada antes de medir. Para cada condição, `n` é o número de execuções
válidas e `p` o de que passaram. Execução que termina em `erro` (falha de
preparação, do agente ou do aceite) não mede nada e sai da conta; tempo,
orçamento e turnos contam como falha (E17). `com` é a condição `project`,
`sem` a condição `ablated`; a queda é `p_com − p_sem`.

1. **`inconclusivo`**: `n_com` ou `n_sem` menor que 15, ou `n_com` diferente
   de `n_sem`. Não há execuções suficientes para a tolerância declarada.
2. **`mantenha`**: a queda passa da tolerância, isto é, `queda × 15 > 4 ×
   n` (4 em 15 execuções por condição, a tolerância de `docs/decisoes.md`
   e de `evals/README.md`, "Primeira rodada"; com outro `n`, a mesma
   proporção, 26,7 pontos percentuais).
3. **`não discrimina`**: a queda está dentro da tolerância, mas as duas
   condições estão em 100% (efeito teto) ou as duas em 0% (efeito piso).
   Sem perda medida, mas o caso não separa uma condição da outra.
4. **`pode remover`**: a queda está dentro da tolerância (inclusive
   negativa) e as condições não estão no teto nem no piso.

Limites exatos, com 15 execuções por condição: queda de 4 está dentro da
tolerância; queda de 5 passa dela; queda de 3 também está dentro.

## 3. Orçamento (E17)

Limites por execução: 150 turnos, 3600 s e 5 milhões de tokens; por
rodada, 100 milhões (`--max-turnos`, `--tempo`, `--tokens`,
`--teto-rodada`). `--simular` imprime o número de execuções e o máximo de
tokens que a rodada pode gastar, sem rodar nada e sem exigir credencial.
Uma rodada de ablação são `casos × execuções × 2` execuções; o mínimo para
um resultado que não seja `inconclusivo` são 15 por condição (por exemplo,
5 casos × 3 execuções).

## 4. Testes

Com o agente falso do executor, sem rede e sem Claude Code: a peça sai só
na cópia e o repositório de origem fica idêntico (hashes); cada uma das
quatro saídas sai de um caso construído, nos limites exatos; peça
inexistente e tipo não suportado dão mensagem em português; interrupção
no meio da rodada deixa registro legível; um teste de ponta a ponta pelo
comando.

## 5. Rodar de verdade

Só com credencial no ambiente, dentro do orçamento do lote (1 caso, 2
execuções por condição, uma peça deste repositório). Sem credencial, o
diário diz que não deu e mostra a mesma ablação com o agente falso.

## Critério de aceite

1. `python -m pytest -q` passa.
2. Conferência independente da cópia sem a peça contra a origem.
3. Tabela das quatro saídas, com os números e a saída do comando.
4. Sondagens: nome parecido, peça única instrução, peça ausente na cópia,
   interrupção por orçamento; nenhum traceback.
5. Regra e orçamento em `evals/README.md` e neste goal.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
