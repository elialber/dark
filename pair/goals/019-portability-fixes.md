# Goal 019 — Correções de portabilidade

Texto do [lote 008](../entrada/lote-008.md), seção "Goal 019: correções
de portabilidade", copiado sem alteração.


Objetivo: a ferramenta passa a rodar em Linux, macOS e Windows. É o
item que responde à exigência do usuário de usar a ferramenta em outros
ambientes.

## O que corrigir

1. **Os três defeitos que impedem o uso no Windows**, descritos no diário
   015 e em `docs/portabilidade.md`:
   - a saída dos comandos falha quando o terminal não é UTF-8;
   - o encerramento de processos por tempo esgotado usa uma chamada que
     não existe no Windows, e deixa processos filhos vivos;
   - a saída do git é lida com a codificação da localidade.
   Corrija a causa em todo lugar em que ela aparece, não só onde um teste
   falhou: toda leitura de saída de processo e toda escrita em terminal.
2. **Os três defeitos cosméticos:** o relatório escreve caminhos sempre
   com barra normal, em qualquer sistema.
3. **Os 19 testes que falham por causa do próprio teste:** caminhos
   inseridos em JSON sem escapar, caminho do interpretador sem aspas, e
   nome de arquivo proibido no Windows. Corrija o teste; nenhum é
   apagado. Onde o caso não existe em um sistema, o teste é pulado nesse
   sistema, com o motivo.
4. **A dependência de `sh` na validação de casos de eval:** decida,
   registre e implemente. Ou a ferramenta deixa de precisar dele, ou
   detecta a ausência e diz ao usuário o que instalar.
5. **De `docs/portabilidade.md`:** todo item marcado como "bloqueia"; e,
   dos marcados como "degrada", os três que o diário 015 aponta como
   mais perigosos, que passam a degradar com aviso no relatório.

## O que não fazer

Não altere o comportamento em Linux. Não refatore além do necessário.
O que você notar pelo caminho vai para o diário, como sugestão.

## Requisitos

- Testes antes do código, para cada defeito de código corrigido.
- Só biblioteca padrão.
- `docs/portabilidade.md` ganha, em cada item, a situação: resolvido
  (com o commit), com aviso, ou em aberto (com o motivo).

## Critério de aceite

1. O workflow de testes, agora na `main`, passa nos seis jobs (três
   sistemas, duas versões de Python). Leia o resultado da execução e
   mostre a tabela no diário. Se um job falhar por problema do executor
   do GitHub, e não dos testes, diga isso e mostre a execução anterior em
   que ele passou.
2. Em Linux, a saída dos comandos sobre as mesmas entradas é idêntica à
   de antes do goal: a auditoria sobre os arquivos sintéticos e sobre os
   dados reais (corte do goal 002, sem as pastas dos experimentos, com
   `--sem-git`), o inventário e a validação do caso de eval gravado.
   Qualquer diferença, explicada.
3. A lista do que "impede o uso" em `docs/portabilidade.md` não tem item
   em aberto, ou o diário explica o que ficou e por quê.

No diário, em português: o que ainda não foi exercitado em Windows e
macOS por falta de teste que rode lá (por exemplo, dados reais do Claude
Code nesses sistemas), e o que você recomenda para cobrir.
