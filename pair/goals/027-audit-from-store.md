# Goal 027 — Auditoria sobre o banco, "o que mudou" e `dark --versao`

Texto do goal, como veio no [lote 011](../entrada/lote-011.md), seção
"Goal 027".

## 1. Registro de coleta perdido (correção)

A tabela `collections` tem `started_at` em segundos com `UNIQUE`; três
coletas dentro do mesmo segundo deixam uma linha só. Corrija sem apagar o
registro de uma coleta anterior. Teste antes do código: três coletas
seguidas, com relógio fixo, deixam três registros e as somas de
`sessions_written` batem. Um banco criado antes da correção continua
abrindo.

## 2. A auditoria lê do banco

Padrão a confirmar: `dark auditar` **não coleta sozinho**.

- Com banco existente que conhece o repositório auditado, a auditoria lê
  as sessões, os indicadores e as ligações de commit do banco, e o
  cabeçalho diz a data da última coleta.
- Sem banco, com banco que não conhece o repositório, ou com banco
  ilegível: a auditoria direta roda como está e o cabeçalho diz por que
  não usou o banco. Nunca traceback; a mensagem do erro de `dark.store`
  sai em português por uma tabela de rótulos na camada de apresentação.
- `--direto` força a auditoria direta; `--coletar` coleta antes de
  auditar; `--banco` escolhe o arquivo, com a mesma recusa de `dark
  coletar`.
- Sessões que o Claude Code já apagou, mas que o banco guarda, entram na
  auditoria pelo banco. Exemplo no diário.

## 3. Seção "O que mudou desde a última semana"

Com os dados do banco: a semana ISO mais recente com dados contra a
anterior, em números (pedidos, tokens, intervenções, peças que passaram a
ser usadas, peças sem uso há N semanas, mudança de peso do inventário).
Sem duas semanas com dados, a seção diz em uma linha que ainda não há
comparação. Sem texto de conversa (E14), sem nota única, sem
recomendação.

## 4. `dark --versao`

Imprime `dark <versão>` (`0+unknown` fora de instalação) e sai com 0.
Funciona sem subcomando.

## 5. README

Seção "Coleta" e uma frase em "Auditoria" sobre o banco, `--direto`,
`--coletar` e `--versao`.

## Critério de aceite

1. `python -m pytest -q` passa.
2. Conferência independente, tabela "esperado, obtido": `dark coletar`
   seguido de `dark auditar` dá os mesmos números que `dark auditar
   --direto`; cada diferença, com explicação.
3. Sondagens adversas: banco vazio; de outro repositório; não SQLite;
   versão nova; uma semana só; sessões do banco que não existem em disco;
   `--banco` dentro de repositório git sem ignorá-lo. Mensagem em
   português, código de saída coerente, nenhum traceback.
4. A coleta no mesmo segundo mantém os três registros.
5. `dark --versao` bate com `importlib.metadata.version("dark")`.
6. A auditoria pelo banco leva segundos nos dados reais (mediana de 5).
7. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
