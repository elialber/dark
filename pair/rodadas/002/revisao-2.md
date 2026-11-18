# Revisão 2 da rodada 002

Revisor do laço, ciclo 2, 2026-11-18. Base: `main` em `134ca98`.

## O que conferi

Três worktrees limpos em `$PAIRLOOP_SCRATCH`, um por branch.

| Branch | Arquivos dentro do permitido | Testes | Merge de ensaio |
|---|---|---|---|
| `goal-027` | sim (`tests/conftest.py` e `src/dark/store/` estão na lista) | 932 passam | sem conflito |
| `goal-028` | sim | 918 passam | sem conflito |
| `goal-029` | sim | 909 passam, 1 `xfail` | sem conflito |

Depois do merge (ordem 027, 028, 029, sem squash): 941 testes passam e 1
`xfail` na `main`.

Sondagens minhas, além dos diários:

- 027: `dark --versao` (`0+unknown` fora de instalação, código 0); `--banco`
  apontando para um diretório; arquivo com cabeçalho SQLite e lixo
  (`auditar` cai na leitura direta com o motivo; `coletar` recusa em
  português); `--direto` com `--coletar` (recusa); arquivo com permissão
  000; caminho de banco inexistente. Nenhum traceback. Detalhe menor: o
  arquivo sem permissão de leitura é descrito como "corrompido ou de outro
  formato"; é impreciso, não é erro grave.
- 028: `claude plugin validate plugin` (2.1.325): passou com avisos
  (autor, licença, linha de instalação por marketplace), como o diário
  diz. Padrões de privacidade do teste conferidos por leitura.
- 029: `validar` rodado por mim em dois casos novos (`goal-024-collect`,
  `goal-017-aggregate-store`): VÁLIDOS, base falha e solução passa, com as
  mesmas durações do diário. Busca por caminho pessoal, chave e nome em
  `evals/`, nos diários e nos goals: nada.
- Busca de privacidade em `src`, `tests`, README e CHANGELOG: só padrões
  de detecção.

## Veredito

- **027: aceito.** A conferência "esperado, obtido" do diário bate
  (sessões, pedidos, tokens, intervenções, peças, ligações); as
  diferenças restantes estão todas explicadas (o banco não guarda custo
  por pedido, nomes de tipos desconhecidos etc.) e o relatório diz "use
  `--direto`" em vez de mostrar zero. O executor admitiu que escreveu
  código e testes juntos nos itens 2 e 4, contra o lote: registro, sem
  reprovar, porque os testes existem e cobrem as sondagens.
- **028: aceito.** Plugin mínimo, sem método embutido; falta a sessão real
  (sem credencial) e a licença; as pontas vão no goal 031.
- **029: aceito.** Cinco casos, três acima de 800 linhas, um de
  convenção; a conferência do aceite foi feita à mão em dois casos. A
  rodada não foi feita (sem credencial), é pedido ao usuário. O achado do
  `conftest.py` é real e vira o goal 030.

## Decisões

Registradas em `docs/decisoes.md` ("Goals 027, 028 e 029: aceitos").
Todas as marcadas "padrão a confirmar" pelos executores foram adotadas
como padrão.

## Meus erros

Nenhum a registrar neste ciclo. Observação sobre o processo: o lote 011
pedia teste antes do código também para os itens 2 e 4; o executor não
cumpriu e disse. Não vira regra no `CLAUDE.md` (uma ocorrência).

## O que planejei

- Lote 012 (goal 030): fechar a lacuna do `conftest.py` no executor.
- Lote 012b (goal 031): README e CHANGELOG do plugin, skills em dia com o
  comando, teste de deriva.
- Lote 012c (goal 032): recomendações por regras fixas (item 5).
- Ablação (item 4) fica para o ciclo seguinte: mexe no executor, que o
  030 está alterando.
- Pedidos ao usuário: rodar a calibração dos casos novos, a sessão real
  do plugin, e escolher a licença.
