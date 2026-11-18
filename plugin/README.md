# Plugin `dark` para o Claude Code

Duas skills que orientam o agente a rodar o `dark` instalado:

- `auditar`: roda `dark auditar` e resume o relatório;
- `coletar`: roda `dark coletar --todos` (só agregados são gravados) e,
  com `--evals`, importa os resultados de uma rodada de evals.

O plugin **não substitui o pacote**: o `dark` precisa estar instalado
(veja o README do repositório). As skills não instalam nada sozinhas.

## Instalar

Pelo caminho local do repositório, numa sessão:

```bash
claude --plugin-dir <caminho-do-repositório>/plugin
```

As skills aparecem como `dark:auditar` e `dark:coletar`.

## Atualizar

Atualize o repositório (`git pull`) e reinicie a sessão: o Claude Code
relê a pasta a cada início. A versão do plugin acompanha a do pacote
(`pyproject.toml`).

## Conferir o formato

```bash
claude plugin validate <caminho-do-repositório>/plugin
```
