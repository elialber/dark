# Revisão 3 da rodada 002

Revisor do laço, ciclo 3, 2026-11-18. Base: `main` em `7df2db4`.

## O que conferi

Clone limpo em `$PAIRLOOP_SCRATCH`, com as três branches juntadas em
sequência (030, 031, 032): sem conflito, 981 testes passam (nenhum
`xfail`). Depois da junção real na `main`, 981 passam de novo.

| Branch | Arquivos dentro do permitido | Merge de ensaio |
|---|---|---|
| `goal-030` | sim | sem conflito |
| `goal-031` | sim | sem conflito |
| `goal-032` | quase: mexeu em `tests/test_integration.py` (ordem das seções), fora da lista, mas é o ajuste do esperado que o lote previa | sem conflito |

Sondagens minhas:

- 030: no pytest 9.2.0, num diretório limpo, `.pytest.ini` com `[pytest]`
  e `addopts = --co` faz um teste que falha "passar"; `pytest.toml` e
  `.pytest.toml` são lidos do mesmo modo (o erro de `addopts` como texto
  prova que foram lidos). Os três **não** estão em `PYTEST_CONFIG_NAMES`.
- 032: arquivo de instruções com 200 linhas (silêncio) e com 201 (dispara,
  com o número de linhas e caracteres), pela CLI, na auditoria direta;
  conferi a seção inteira. Sem traceback.
- 031: `claude plugin validate plugin` passa com o aviso de marketplace
  (sem efeito); busca de privacidade em plugin, README, CHANGELOG,
  `recommend.py`, `evals/` e diários: nada. O trecho da skill sobre
  "Fonte" e "O que mudou" bate com o diário e com o código do goal 027.

## Veredito

- **030: aceito com correções.** Entrega tudo o que o lote pedia, com
  testes, tabelas e sondagens; mas a lista de nomes envelheceu: o pytest
  9 lê três arquivos que ela não cobre. Correção no goal 033 (nova
  pesquisa da lista, com a fonte, e teste que acompanha o pytest). O
  lote 012 mandava listar cinco nomes; a lacuna é minha (a lista saiu do
  `CLAUDE.md` do goal 029, de memória), não do executor.
- **031: aceito.** Teste de deriva funciona (o executor o viu pegar um erro
  dele mesmo), README e CHANGELOG em dia, sondagens feitas. Sessão real
  pendente por falta de credencial.
- **032: aceito.** Cinco regras com limites exatos testados, nenhuma
  recomendação sem evidência, três adiadas com o dado que falta.

## Meus erros

- Escrevi o lote 012 com uma lista fechada de cinco nomes de configuração
  do pytest sem conferir a versão em uso. Registrado.

## Planejado (ciclo 3)

- Lote 013 (goal 033): nomes de configuração do pytest 9.
- Lote 013b (goal 034): ablação (item 4), com o agente falso; medição real
  fica como pedido (credencial).
- Lote 013c (goal 035): `docs/metodo.md` (item 7) e as recomendações no
  README e no CHANGELOG.
Fora desta rodada: módulos do scaffold (item 6), que pedem decisão do
usuário sobre Langfuse (instância); piloto (item 9).
