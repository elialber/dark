# Laço de par

O laço roda sozinho o ciclo que antes dependia de você como mensageiro:
um revisor lê o repositório, julga as branches, junta as aceitas e
escreve os próximos lotes; executores fazem os lotes, cada um na sua
branch; e o ciclo recomeça. Você entra ao fim de cada rodada, lê um
relatório de uma página e dá a direção.

## Como usar

Na raiz do repositório, na branch `main`, com o Claude Code autenticado
e um ambiente Python em que o comando de testes rode (por exemplo, o
`.venv` ativado):

```
python -m tools.pairloop iniciar     # começa uma rodada
python -m tools.pairloop estado      # mostra onde a rodada está
python -m tools.pairloop continuar   # retoma uma rodada interrompida
python -m tools.pairloop encerrar    # fecha a rodada aberta, com relatório
```

Opções gerais: `--repo CAMINHO` (padrão: o diretório atual) e `--config
ARQUIVO` (padrão: `pair/loop.toml`). `encerrar --sem-sessao` fecha sem
abrir a sessão final do revisor; o relatório sai do orquestrador, só com
os fatos do estado.

`iniciar` só abre a rodada se o `claude` estiver no `PATH` e os testes
passarem na branch base; sem isso, a primeira junção pararia a rodada
por um defeito que não é dela.

Ao fim, leia `pair/rodadas/NNN.md`. É o único arquivo de que você
precisa: o que foi entregue e que item do roteiro cada entrega avançou,
os vereditos, as decisões tomadas, as que esperam por você (com opções e
recomendação), o motivo da parada, o gasto e o que a próxima rodada
faria.

## Como uma rodada anda

1. **Revisão (ciclo k).** Uma sessão nova do revisor, como o agente
   `pair-reviewer`, na raiz do repositório. Revisa as branches do ciclo
   anterior, junta as aceitas, atualiza o roteiro e as decisões, escreve
   até quatro lotes e deixa duas saídas em `pair/rodadas/NNN/`: o
   diário de revisão (`revisao-k.md`) e a saída do ciclo (`ciclo-k.json`),
   que o orquestrador lê. O revisor não faz push: depois da sessão, o
   orquestrador roda os testes, confere o histórico e os arquivos
   protegidos e só então faz o push da `main` e apaga do remoto as
   branches juntadas.
2. **Execução (ciclo k).** Para cada lote, o orquestrador cria o worktree
   `../<repositório>-<branch>` e abre uma sessão de executor nele, em
   paralelo, até o limite. Cada executor escreve
   `pair/diario/<goal>.md`, faz commit e push da sua branch e para.
3. Depois do último ciclo, uma **revisão de fechamento** julga e junta o
   que falta e escreve o relatório da rodada.

Depois de cada sessão o orquestrador confere por conta própria, no git:
se o revisor só commitou em `pair/`, `docs/decisoes.md` e
`docs/roteiro.md`; se nenhum arquivo protegido mudou; se a `main` não
mudou durante a execução, nem a do remoto durante a revisão; se cada
executor deixou o diário; se há caminho pessoal nas linhas novas; e roda
os testes depois de cada junção. Confere também o conteúdo dos arquivos
protegidos na árvore de trabalho, comparado com o de antes da sessão,
para pegar a escrita que não passou pelo git. O push só acontece se tudo
isso passou; depois de uma parada por problema, a rodada não faz mais
push.

## O que cada papel pode fazer

| | Orquestrador | Revisor | Executor |
|---|---|---|---|
| O que é | programa, sem modelo | sessão nova por ciclo | sessão por lote |
| Onde trabalha | raiz do repositório | raiz, na `main` | o próprio worktree |
| Escreve | estado em `local/pairloop/` e o relatório de reserva | `pair/`, `docs/decisoes.md`, `docs/roteiro.md` | tudo do próprio worktree que o lote permitir |
| Merge na `main` | não | sim, só ele | nunca |
| Push | `main` e remoção de branches juntadas, depois das conferências | nunca | só a própria branch |
| Decide | quando parar | vereditos, decisões fora da lista abaixo, próximos lotes | o que o lote deixa em aberto, registrado como "padrão a confirmar" |

Nenhum agente faz push forçado, push para outro remoto, apaga a `main`,
escreve fora do repositório, dos worktrees e do próprio rascunho
(`$PAIRLOOP_SCRATCH`), altera a configuração do git (fora `user.name` e
`user.email` do repositório), nem edita `tools/pairloop/`,
`.claude/agents/pair-reviewer.md`, `pair/loop.toml`, `pair/DIRECAO.md`,
`docs/visao.md` ou `docs/origem/`. Configuração do git fica de fora
porque executa código depois, inclusive nos comandos do próprio
orquestrador (`core.hooksPath`, `core.fsmonitor`, `core.sshCommand`,
`alias.*`). Isso é garantido por código, em três camadas: o hook
`tools/pairloop/guard.py`, que o orquestrador instala em toda sessão por
`--settings` e que bloqueia a ação antes de ela rodar; as conferências do
orquestrador no histórico git depois de cada sessão, que pegam o que um
comando de shell conseguiu esconder do hook; e a conferência do conteúdo
dos arquivos protegidos na árvore de trabalho, que pega a escrita feita
por um programa do agente sem passar pelo git. Essa conferência inclui o
bytecode dos diretórios protegidos (o laço roda sem gravar bytecode) e,
do repositório, `.git/config` (fora `branch.*` e `user.*`, que o próprio
laço grava), `.git/hooks/` e `.git/info/`. Os comandos git do
orquestrador rodam com hooks, `core.fsmonitor` e ferramentas externas de
diff desligados, e com o ssh do ambiente ou da sua configuração global,
nunca do repositório. O arquivo que liga o hook é regravado antes de
cada sessão.

O hook expande variáveis (`$PAIRLOOP_SCRATCH` e as atribuídas no próprio
comando), confere o destino de `git clone`, `git init` e `git worktree
add` e deixa cada agente escrever no próprio rascunho, mesmo quando ele
fica dentro do repositório. O executor pode remover e mover os
worktrees que criou no rascunho.

O que nenhuma camada pega: um programa escrito por um agente pode gravar
fora do repositório. Fechar isso exige um ambiente isolado, fora do
escopo atual (risco aceito em `docs/decisoes.md`).

O revisor não decide, e leva ao relatório como decisão sua: mudança de
escopo (contrariar `docs/visao.md` ou reabrir o que ficou de fora),
dependência externa nova, regra de privacidade ou segurança, reescrita de
histórico e gasto acima do orçamento. O trabalho que depende delas para;
o resto segue.

## Quando a rodada para

Ao fim dos ciclos, ou antes, quando: os testes falham depois de uma
junção; há conflito de merge; o mesmo goal é rejeitado duas vezes; um
limite é atingido (tokens ou tempo da rodada, turnos ou tempo de uma
sessão); uma sessão termina sem diário ou sem a saída combinada; uma
conferência de limite falha; o revisor encontra violação de privacidade;
ou não sobra lote que não espere por você.

Ao parar, nada é descartado: branches e worktrees ficam como estão. Se a
parada foi por orçamento, o orquestrador escreve o relatório sem abrir
nova sessão.

Não faça commit na `main` com uma rodada aberta: o orquestrador não
distingue o seu commit do de um agente e para a rodada por violação de
limite. Mude a direção e os limites entre rodadas.

Para interromper na hora, `Ctrl+C`. O estado fica salvo em
`local/pairloop/round-NNN.json`; depois, `continuar` ou `encerrar`. Uma
revisão que já deixou a saída commitada não é repetida.

## Como mudar a direção

Edite `pair/DIRECAO.md`, seção "Direção atual", e faça commit na `main`
antes de iniciar a rodada. O revisor a lê no início de cada ciclo e a põe
acima do roteiro e do próprio plano. É também ali que você responde às
decisões do relatório.

## Como mudar os limites

Edite `pair/loop.toml`:

- `[round]`: ciclos por rodada, executores simultâneos, orçamento de
  tokens e tempo de sessão da rodada;
- `[session.reviewer]` e `[session.executor]`: turnos e minutos por
  sessão; `[session] model`, o modelo (vazio: o padrão do Claude Code);
- `[git]`: branch base, remoto e se o orquestrador faz push;
- `[checks] test_command`: os testes que o orquestrador roda depois das
  junções;
- `[claude]`: comando, diretório de configuração, modo de permissão,
  persistência das sessões e fontes de configuração;
- `[paths]`: onde ficam o estado e os relatórios.

O orçamento de tokens conta entrada, saída e cache de todas as sessões,
como o modo não interativo do Claude Code informa. Se alguma sessão não
informar o uso, o limite de tempo passa a ser o que vale.

## Os quatro documentos que o revisor lê além do código

- `docs/visao.md`: para que o projeto existe, o método e como você quer
  que ele seja conduzido. Só você altera.
- `docs/roteiro.md`: o que foi feito, o que está em andamento e a fila
  ordenada do que falta. O revisor mantém.
- `docs/origem/guia-harness-14-camadas.md`: texto integral do guia das
  camadas de um harness, com o catálogo de ferramentas. Registro
  histórico.
- `docs/origem/especificacao-original.md`: texto integral da
  especificação acordada antes do goal 001. Registro histórico; onde
  divergir de `docs/decisoes.md`, valem as decisões.
