# Goal 032 — Recomendações por regras fixas

Item 5 do roteiro. O cockpit do usuário é "recomendações de melhoria e
acompanhamento" (`docs/visao.md`): os dados já existem (indicadores, banco,
"o que mudou"); falta o relatório dizer o que fazer, por **regras fixas**,
cada uma com a evidência que a dispara e uma ação que dá para verificar.

## 1. Módulo de regras

`src/dark/recommend.py` (novo): funções puras sobre o `Audit` e, quando
houver, o `Changes` do goal 027. Cada regra devolve zero ou mais
`Recommendation`: identificador estável da regra (inglês), evidência (números
e nomes que vêm do relatório, nunca inventados), ação em uma frase
(português) e como verificar (um comando ou um indicador que muda). Sem nota
única, sem ordenação por "gravidade total", sem texto gerado.

Regras do roteiro; implementar as que os dados de hoje sustentam (mínimo
quatro) e listar as demais como "adiadas, falta o dado X":

- peça com arquivo sem uso há N semanas, com sessão no período: candidata à
  ablação (item 4 do roteiro; o comando ainda não existe);
- arquivo de instruções acima de um teto de tamanho (o teto não existe em
  `docs/`: padrão a confirmar, numa constante com nome);
- peso fixo subiu entre duas coletas: listar o que entrou;
- hook que bloqueia repetidamente: corrigir a causa na instrução ou na skill;
- evals em 100% por várias rodadas; modelo mudou desde a última rodada;
  módulo de terceiro sem ganho medido: só com dado;
- commits sem hash registrado: commit sem `-q`.

Regra só dispara com o dado que a sustenta; "sem dados" ou "não guardado pelo
banco" nunca vira recomendação.

## 2. No relatório

Seção "Recomendações" em `src/dark/report.py`, depois de "O que mudou": uma
linha por recomendação (regra, evidência, ação, verificação), ou "Nenhuma regra
disparou com os dados disponíveis". Vale para a auditoria direta e para a pelo
banco; as regras que dependem do banco dizem, numa linha só, que o banco é
necessário quando não puderam rodar.

## 3. Testes

`tests/test_recommend.py`, antes do código: cada regra com um caso que dispara
e um que não dispara, com limites exatos; auditoria sintética ponta a ponta
pela CLI; auditoria sem dados sem recomendação e sem traceback.

## Critério de aceite

1. `python -m pytest -q` passa.
2. Conferência independente (esperado, obtido) dos números da evidência.
3. Relatório completo de uma auditoria pelo banco e de uma direta, no diário.
4. Sondagens: banco com uma semana; repositório sem sessões; arquivo
   exatamente no teto; peça removida do disco depois de usada.
5. Cada ação é algo que o usuário faz e verifica.
6. Nenhum nome real, caminho pessoal ou segredo versionado.
