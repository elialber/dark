# Goal 025 — Endurecimento do laço

Origem: decisão D1 da [rodada 001](../rodadas/001.md), respondida pelo
usuário em 2026-11-18 com a opção (a): uma sessão fora do laço, entre
rodadas, corrige os defeitos que nenhum agente do laço pode corrigir
(`tools/pairloop/` é protegido).
Branch: `main`, sem rodada aberta.
Data: 2026-11-18

## Objetivo

Fechar os defeitos do laço listados na D1 (diário 021, "O que eu ainda
mudaria", e revisões da rodada 001) antes da segunda rodada.

1. **Git do orquestrador.** Os comandos git do orquestrador não executam
   configuração plantada no repositório: hooks, `core.fsmonitor`,
   `core.sshCommand`, conversões de diff. `.git/config` (fora `branch.*`
   e `user.*`, que o próprio laço grava), `.git/hooks/` e `.git/info/`
   entram na conferência por conteúdo.
2. **Arquivo de hooks.** Regerado antes de cada sessão.
3. **Bytecode.** O laço roda sem gravar bytecode, e `__pycache__` dos
   diretórios protegidos entra na conferência.
4. **Partida.** `iniciar` confere que o `claude` existe e que os testes
   passam antes de abrir a rodada.
5. **Caminhos do Git Bash** (`/c/Users/...`) entendidos no Windows.
6. **Rascunho do revisor.** O rascunho vale antes das raízes; o revisor
   escreve nele.
7. **Destino de `git clone`, `git init` e `git worktree add`** conferido
   como qualquer escrita.
8. **Variáveis** (`$PAIRLOOP_SCRATCH`, `${X}`, as atribuídas no próprio
   comando) expandidas pelo hook; `/dev/fd/*`, `/dev/stdout` e
   `/dev/stderr` aceitos.
9. **Worktrees do executor no rascunho.** O executor remove e move os
   worktrees que estão no próprio rascunho.

## Requisitos

Testes antes do código; nada além do listado.

## Critério de aceite

1. Os testes passam; o workflow passa nos seis jobs.
2. Um teste para cada item.
3. Diário em português com o que mudou e o que continua de fora.
