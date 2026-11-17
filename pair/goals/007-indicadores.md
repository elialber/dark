# Goal 007 — Indicadores

Texto do goal, como veio no [lote 004](../entrada/lote-004.md):


Objetivo: calcular os indicadores que não dependem de evals, como funções
puras sobre o modelo interno do leitor. Sem armazenamento, sem relatório,
sem comando além de um mínimo de conferência.

Extensões do leitor necessárias (no próprio `leitor.py`):

- O que estava disponível na sessão: skills anunciadas, tipos de
  subagente, ferramentas e servidores MCP, pelas fontes descritas na seção
  C do documento de viabilidade.
- Os tokens de entrada da primeira resposta da sessão.
- Para cada chamada que executa `git commit`: o hash de
  `gitOperation.commit`, quando houver, e se foi amend.

Detecção de `git commit`: pelo comando analisado, não por busca de texto.
Tem de acertar comando encadeado (`&&`, `;`), `--amend` e `-q`, e não
pode disparar em comando que só menciona a expressão (por exemplo,
`echo "git commit"`). Um teste para cada caso.

Módulo novo `src/dark/indicadores.py`, com uma função por indicador, cada
uma recebendo sessões e devolvendo um resultado tipado:

- **Peso fixo:** por sessão e resumo (mediana, mínimo, máximo).
- **Peso morto:** para skills, tipos de subagente, ferramentas e
  servidores MCP: disponíveis, usados e nunca usados no período, com os
  nomes.
- **Intervenções:** pedidos humanos, interrupções, rejeições e mensagens
  no meio do turno, por sessão e por pedido.
- **Custo:** tokens por pedido e por sessão, com a parcela dos
  subagentes.
- **Hooks:** desfechos por tipo e por evento (E6 final).
- **Commits:** chamadas de commit com hash registrado, sem hash e amends.

Requisitos: testes antes do código, só com arquivos sintéticos; nenhuma
função lê disco ou relógio; nomes de skills e ferramentas reais nunca
entram no repositório.

Critério de aceite:

1. Os testes passam.
2. Sobre os dados reais, no corte do goal 002 e sem as pastas dos
   experimentos, os indicadores reproduzem os números do documento de
   viabilidade: skills anunciadas e acionadas, tipos de subagente
   anunciados e acionados, medianas de ferramentas e de servidores MCP,
   mediana e extremos do peso fixo, contagens de intervenção, tokens por
   sessão e por pedido, desfechos de hook.
3. O diário traz a tabela "esperado, obtido, diferença", com cada
   diferença explicada. No diário, só contagens.

No diário, relate também: qual indicador você considera menos confiável,
e o que um relatório de auditoria deveria dizer ao usuário sobre isso.
