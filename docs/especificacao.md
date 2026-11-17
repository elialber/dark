# Especificação

Núcleo da especificação, como entregue pelo revisor externo no
[lote 003](../pair/entrada/lote-003.md) em 2026-11-17. Esta cópia é a
referência do projeto. Onde este texto e uma decisão divergirem, vale a
decisão mais recente.

**Objetivo.** Aplicada a um repositório, a ferramenta instala e mantém o
harness do Claude Code, mede a saúde dele e indica o que mudar, com
evidência. Uso individual, só Claude Code, dados locais.

**Forma.** Plugin do Claude Code mais uma CLI pequena em Python. O
cockpit é um relatório local gerado sob demanda.

**Princípios.**

- Medir antes de gerar: nenhuma peça entra no harness sem forma de saber
  se ajudou.
- Fiação, não conteúdo: o scaffold conecta ferramentas e cria estrutura;
  regras e skills nascem de falhas observadas.
- Toda peça prova o próprio valor: fica se a taxa de acerto cai quando é
  removida.
- Não destrutivo: nada é sobrescrito; rodar de novo não duplica;
  desinstalar deixa o repositório limpo.
- Local primeiro: serviço externo é opcional.
- Git como fonte da verdade: o harness mora no repositório e o desfecho
  das tarefas é lido do histórico.

**Componentes.**

1. Auditoria: lê o harness existente e as transcrições, sem alterar nada,
   e produz achados com evidência.
2. Evals: tarefa é um commit, um pedido e testes de aceite; casos
   minerados do histórico; execução em sessão limpa, N vezes; linha de
   base sem harness.
3. Scaffold e módulos: estrutura mínima e integrações de terceiros com
   contrato único (instalar, verificar, medir, desinstalar). Módulos
   previstos: Langfuse e Graphify, ambos opcionais.
4. Cockpit: indicadores separados, sem nota única, e recomendações por
   regras determinísticas.
5. Método: ciclo de derivação (tarefas, linha de base, classificar a
   falha, corrigir na camada certa, medir de novo) e ciclo de poda.

**Indicadores.** Acerto na primeira tentativa, retrabalho, intervenções,
peso fixo de contexto, peso morto, aderência, frescor e custo por tarefa.

**Fora do escopo.** Criar projetos ou gerar código de aplicação; outros
agentes; uso em time; monitoramento em tempo real; recomendações geradas
por IA; nota única de saúde; guardar conteúdo de conversas; harness de
agentes embutidos em produtos.

**Fases.**

1. Piloto manual, sem código de produção.
2. Auditoria e placar. Pronto quando o relatório de um repositório do
   usuário apontar um achado que ele não conhecia.
3. Evals. Pronto quando duas rodadas iguais derem taxas dentro da
   tolerância.
4. Scaffold e módulos. Pronto quando instalar e desinstalar deixarem o
   repositório idêntico ao inicial.
5. Recomendações. Pronto quando uma recomendação seguida produzir melhora
   medida.

**Critério de sucesso.** Em dois repositórios do usuário: o acerto na
primeira tentativa sobe e as intervenções caem; pelo menos uma peça é
removida por ablação sem perda; a auditoria revela pelo menos um problema
que o autor não havia notado.

## Decisões

Registradas em [decisoes.md](decisoes.md), com data e motivo.

- [E1. Leitor isolado](decisoes.md#e1-leitor-isolado) — superada; vale a versão mais recente abaixo
- [E1 revista. Leitor isolado e tolerante](decisoes.md#e1-revista-leitor-isolado-e-tolerante)
- [E2. Agregados persistidos](decisoes.md#e2-agregados-persistidos)
- [E3. Repositório pelo `cwd`](decisoes.md#e3-repositório-pelo-cwd)
- [E4. Tokens](decisoes.md#e4-tokens)
- [E4, complemento. Unicidade global de `message.id`](decisoes.md#e4-complemento-unicidade-global-de-messageid)
- [E5. Intervenções por sinais estruturais](decisoes.md#e5-intervenções-por-sinais-estruturais) — superada; vale a versão mais recente abaixo
- [E5 revista. Intervenções](decisoes.md#e5-revista-intervenções)
- [E6. Aderência pelas transcrições](decisoes.md#e6-aderência-pelas-transcrições) — superada; vale a versão mais recente abaixo
- [E6 revista. Aderência](decisoes.md#e6-revista-aderência) — superada; vale a versão mais recente abaixo
- [E6, versão final. Aderência por desfechos visíveis](decisoes.md#e6-versão-final-aderência-por-desfechos-visíveis)
- [E7. Ligação sessão a commit (hipótese)](decisoes.md#e7-ligação-sessão-a-commit-hipótese) — superada; vale a versão mais recente abaixo
- [E7 revista. Sessão a commit por janela de horário](decisoes.md#e7-revista-sessão-a-commit-por-janela-de-horário) — superada; vale a versão mais recente abaixo
- [E7, terceira versão. Hash registrado, depois janela](decisoes.md#e7-terceira-versão-hash-registrado-depois-janela)
- [E8. Linguagem](decisoes.md#e8-linguagem)
- [E9. Unidade de medida](decisoes.md#e9-unidade-de-medida)
- [E9, exceção. Registros copiados por fork](decisoes.md#e9-exceção-registros-copiados-por-fork)
- [E10. Coleta periódica](decisoes.md#e10-coleta-periódica)
- [E11. Peso fixo](decisoes.md#e11-peso-fixo) — superada; vale a versão mais recente abaixo
- [E11 revista. Peso fixo: total e repartição](decisoes.md#e11-revista-peso-fixo-total-e-repartição)
- [E12. Falha isolada por sessão](decisoes.md#e12-falha-isolada-por-sessão)
- [E13. Última linha cortada](decisoes.md#e13-última-linha-cortada)
- [E14. Armazenamento por lista explícita](decisoes.md#e14-armazenamento-por-lista-explícita)
- [Goal 003 cancelado](decisoes.md#goal-003-cancelado)
- [Decisões dos goals 006 e 007](decisoes.md#decisões-dos-goals-006-e-007) — confirmadas no lote 005; duas alteradas pelo revisor
- [E15. Identidade do repositório](decisoes.md#e15-identidade-do-repositório)
