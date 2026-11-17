# Goal 004 — Experimentos controlados

Texto do goal, como veio no [lote 003](../entrada/lote-003.md):


Objetivo: responder, com testes pequenos e reproduzíveis, às perguntas
que a análise do histórico não consegue responder. Não é código de
produção.

Ambiente: um diretório descartável fora deste repositório, com um
repositório git próprio e configuração de projeto própria. Sessões em
modo não interativo. Não altere a configuração do usuário
(`~/.claude/settings.json` e afins). Apague o diretório ao terminar.

Experimentos:

1. **Hook silencioso.** Um hook `PreToolUse` que roda e não imprime nada
   deixa algum registro na transcrição?
2. **Outros eventos e falhas.** Como aparecem `PostToolUse`,
   `SessionStart`, `UserPromptSubmit` e um hook que termina com código
   diferente de zero sem bloquear?
3. **Hash do commit.** `git commit` sem `-q` deixa o hash no resultado da
   ferramenta? E um `--amend` logo depois: o que a janela de horário
   devolve?
4. **Retomada de sessão.** Como `--continue` e `--resume` aparecem no
   arquivo: mesmo arquivo, arquivo novo, algum marcador?
5. **Decomposição do contexto.** Existe forma não interativa de obter
   quanto do contexto inicial vem de cada componente (instruções, skills,
   ferramentas, servidores MCP)? Se não houver, meça por diferença: a
   mesma sessão mínima com e sem um componente, comparando o `usage` da
   primeira resposta.

Entregue `docs/experimentos-001.md` com, para cada experimento: o que foi
feito, o que foi observado, a conclusão e o grau de confiança. Diga quais
decisões de `docs/decisoes.md` cada resultado confirma ou contradiz.

Restrições: o documento é público; exemplos sintéticos; nada de dados de
outros repositórios. Mantenha o gasto de tokens baixo: sessões mínimas,
uma ou duas chamadas de ferramenta cada.

