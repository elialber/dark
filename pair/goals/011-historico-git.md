# Goal 011 — Histórico git

Texto do goal, como veio no [lote 004d](../entrada/lote-004d.md):

Objetivo: um módulo que lê o histórico git de um repositório e responde
às perguntas de que a auditoria precisa sobre commits. É o lado git da
decisão E7 (ligar chamada a commit) e do indicador de retrabalho. Não lê
transcrições e não importa `dark.leitor`: recebe hashes e intervalos de
horário como parâmetros.

### O que o módulo responde

1. **Commits em uma janela.** Dado um repositório e dois instantes,
   quais commits têm data de commit entre eles, incluindo os que só
   existem no reflog. O resultado distingue nenhum, um e mais de um; mais
   de um é "ambíguo" e o módulo não escolhe.
2. **Situação de um commit.** Dado um hash: existe? É alcançável a
   partir de alguma branch? Da branch padrão? Ou só pelo reflog?
3. **Amend.** O commit foi substituído por outro logo em seguida?
4. **Reversão.** O commit foi revertido por um commit posterior?
5. **Retoque.** Os arquivos que o commit alterou foram alterados de novo
   por outro commit dentro de N dias? Este é um sinal fraco de
   retrabalho. Proponha a definição mais defensável que conseguir medir,
   justifique no diário e marque a confiança. Não o apresente como
   "correção": o módulo não sabe a intenção do segundo commit.

Limite conhecido, a relatar e não a resolver: commit incorporado por
squash some da branch padrão e aparece como não alcançável. Diga no
resultado quando esse pode ser o caso.

### Requisitos

- Só biblioteca padrão; o git é chamado como processo, por um executor
  injetável.
- **Somente leitura.** Nenhum comando que altere o repositório ou a rede:
  sem `fetch`, `gc`, `checkout`, `commit` ou equivalente.
- Horários comparados como instantes, com fuso tratado de forma
  explícita.
- Repositório inexistente, sem commits ou que não é git: resultado
  explícito, não exceção solta.

### Testes

Antes do código. Os repositórios de teste são criados dentro do
diretório temporário de cada teste, com datas controladas pelas
variáveis de ambiente do git. No mínimo: um commit na janela; dois
commits no mesmo segundo; amend; reversão; branch apagada (commit só no
reflog); retoque dentro e fora do prazo; worktree; diretório que não é
repositório.

Os testes criam repositórios só em diretório temporário e não tocam em
nenhum repositório real.

### Critério de aceite

1. Os testes passam, junto com os já existentes.
2. Conferência cruzada neste repositório, cujos hashes são públicos: a
   busca por janela recupera os commits `cd16451`, `b473041` e `8d7a5fd`
   a partir dos horários deles, como relatado na seção A de
   `docs/viabilidade-indicadores.md`. Mostre a tabela no diário.
3. Para cada uma das cinco perguntas, o diário diz o que foi observado
   neste repositório, só com contagens e hashes públicos.

No diário, além do padrão: a definição de retoque que você adotou e por
quê; o que no módulo depende de estado que muda com o tempo; e o que
precisaria mudar em arquivos existentes, se houver.
