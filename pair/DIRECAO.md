# Direção

Texto livre do usuário. O revisor do laço de par lê este arquivo no
início de cada ciclo e o trata como prioridade sobre `docs/roteiro.md` e
sobre o próprio plano. Só o usuário edita; os hooks do laço bloqueiam
qualquer agente.

## Como escrever

Diga o que importa agora, em poucas linhas. Exemplos do que cabe aqui:

- uma prioridade: "antes de tudo, o item 3 do roteiro";
- uma restrição: "nenhuma dependência nova nesta rodada";
- uma resposta a uma decisão do relatório: "D2 da rodada 001: opção b";
- um pedido: "quero ver o executor de evals rodando, mesmo que parcial".

Quando a direção mudar, substitua a seção abaixo. O histórico fica no git.

## Direção atual

Concluir a Fase 3 (evals) e tornar a ferramenta utilizável em outros
ambientes.

**Mudança de escopo (usuário, 2026-11-18): agnóstico de agente.** O
`dark` não deve ser só do Claude Code. O usuário trabalha com agentes
híbridos, a maior parte com Codex (OpenAI) e parte com Claude Code. Isso
reabre o item "Outros agentes além do Claude Code" de `docs/visao.md`
("O que foi negociado e ficou de fora"). Os próximos goals definem como
verificar e medir de forma agnóstica: primeiro o desenho (o que é comum
aos agentes, o que é próprio de cada um, como ler as sessões do Codex em
`~/.codex/sessions` e o `AGENTS.md` ao lado de `CLAUDE.md`), com decisão
registrada, antes de qualquer código. O piloto (item 9) usa dois
repositórios privados do usuário, `AIStoteles` e `mrvr`, com Codex e
Claude Code; o caminho fica fora do repositório (só o usuário e a sessão
do piloto o recebem) e nos registros entram só números e o nome.

Respostas às decisões da rodada 003 (usuário, 2026-11-18):

- **D1 (Langfuse e Graphify):** opção (a), com um ajuste. O Langfuse é
  auto-hospedado e vem embarcado no módulo como arquivos Docker (Docker
  Compose, já que o Langfuse auto-hospedado precisa de mais de um
  serviço). Origem: a edição community (open source) oficial de cada
  projeto. Versão: a mais recente publicada quando o goal for feito,
  fixada no módulo (nada de `latest`).
- **Goal 040 (documentos):** opção (a). Um goal novo refaz os documentos
  sobre a `main` atual, incluindo 039, 041 e 042.
