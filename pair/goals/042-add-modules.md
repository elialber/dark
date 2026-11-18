# Goal 042: `dark adicionar`, `dark verificar` e registro de módulos

O item 6 do roteiro pede `dark adicionar <módulo>`. Hoje `iniciar` e
`remover` só conhecem o módulo `base`, e o contrato de módulo (instalar,
verificar, desinstalar) não tem comando para a parte "verificar" nem um
registro por onde um módulo novo entre. Os módulos de terceiros ficam fora
deste goal: aqui entra só a estrutura que eles vão usar, provada com um
módulo de teste.

1. **Registro.** `scaffold.base.MODULES` vira um registro único, com função
   para consultar (`get_module(nome)`) e listar. Só `base` é registrado de
   fábrica. Um teste registra e remove um módulo falso (apenas nos testes,
   nunca no pacote).
2. **`dark adicionar <módulo> [<caminho>] [--aplicar]`:** mesmo
   comportamento de `iniciar` (plano sem escrever, `--aplicar` aplica, tudo
   ou nada, só na raiz de um repositório git, conflito aborta), para
   qualquer módulo registrado. Módulo desconhecido: mensagem em português
   com os conhecidos e código 2. `dark iniciar` passa a ser `adicionar
   base`, com a saída atual inalterada. O código comum de `_init` é
   extraído, não duplicado.
3. **`dark verificar <módulo> [<caminho>]`:** roda `module.verify` e imprime
   `ok` ou o motivo; código 0 se ok, 1 se não, 2 se o módulo é desconhecido
   ou o caminho não é a raiz de um repositório. Só lê.
4. **`dark adicionar --listar`:** lista os módulos registrados com versão,
   indicador e se estão aplicados no repositório (lendo o manifesto).
5. **Ida e volta.** Teste: repositório temporário com `git init`;
   `adicionar` do módulo falso com `--aplicar`, `verificar` ok, `remover`; a
   árvore volta byte a byte ao estado inicial.

Critério de aceite: `python -m pytest -q` passa; tabela "esperado, obtido"
do `--help` e dos códigos de saída; sondagens sem traceback; saída de `dark
iniciar` byte a byte igual à da `main` em dois repositórios temporários;
nenhum nome real, caminho pessoal ou segredo versionado.
