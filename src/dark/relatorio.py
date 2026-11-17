"""Apresentação da auditoria em Markdown (goal 008).

Recebe a `Auditoria` calculada em `dark.auditoria` e devolve texto. Não
calcula indicador nem lê nada: só formata. Em português, legível direto
no terminal. Cada seção termina com uma linha "Como ler".

O relatório traz nomes reais de skills, ferramentas e servidores: é o
propósito dele, e ele fica na máquina do usuário.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from dark import indicadores as ind
from dark import leitor
from dark import origem as org
from dark.auditoria import MODOS_SEM_REJEICAO, Achado, Auditoria

TITULO = "Auditoria do harness"

SECOES = {
    "cabecalho": TITULO,
    "peso-fixo": "Peso fixo",
    "peso-morto": "Peso morto",
    "custo": "Custo",
    "intervencoes": "Intervenções",
    "hooks": "Hooks",
    "commits": "Commits",
    "instalado": "O que está instalado",
    "apendice": "Apêndice",
}

# Quantos nomes uma lista mostra no corpo; o resto vai para o apêndice.
PRIMEIROS = 5

NOMES_DE_ORIGEM = {
    "projeto": "projeto",
    "usuario": "usuário",
    "plugin": "plugin",
    "gerenciado": "gerenciado",
    "conta": "plataforma, da conta",
    "embutida": "plataforma, embutida",
    "sem_arquivo": "sem arquivo encontrado",
}

TIPOS_DO_INVENTARIO = {
    "instrucao": "Instrução",
    "skill": "Skill",
    "subagente": "Subagente",
    "hook": "Hook",
    "mcp": "Servidor MCP",
    "permissao": "Permissões",
}
ESCOPOS_DO_INVENTARIO = ("projeto", "usuario", "plugin", "gerenciado")

CATEGORIAS = {
    "skills": "Skills",
    "tipos_subagente": "Tipos de subagente",
    "ferramentas": "Ferramentas",
    "servidores_mcp": "Servidores MCP",
}

TIPOS_DE_HOOK = {
    "sucesso": "saída registrada",
    "erro_sem_bloqueio": "falha sem bloqueio",
    "cancelado": "tempo esgotado",
    "bloqueio": "bloqueio",
    "confirmacao": "pediu confirmação",
    "decisao": "liberou",
    "parada": "resumo de parada",
}


# --------------------------------------------------------------------------
# Formatação
# --------------------------------------------------------------------------

def n(valor: float | int | None) -> str:
    """Número no formato brasileiro: 1.234.567 e 12,5."""
    if valor is None:
        return "—"
    if isinstance(valor, float) and not valor.is_integer():
        inteiro, decimal = f"{valor:,.1f}".split(".")
        return inteiro.replace(",", ".") + "," + decimal
    return f"{int(valor):,}".replace(",", ".")


def pct(parte: float, todo: float) -> str:
    if not todo:
        return "—"
    return f"{100 * parte / todo:.1f}".replace(".", ",") + "%"


def quando(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") + " UTC" if dt else "—"


def ancora(titulo: str) -> str:
    """Âncora no estilo do GitHub: minúsculas, sem pontuação, espaço vira hífen."""
    return "#" + re.sub(r"[^\w\- ]", "", titulo.lower()).replace(" ", "-")


def link(secao: str) -> str:
    titulo = SECOES[secao]
    return f"[{titulo}]({ancora(titulo)})"


def codigo(nomes) -> str:
    return ", ".join(f"`{x}`" for x in sorted(nomes))


def como_ler(texto: str) -> str:
    return f"*Como ler:* {texto}"


def plural(k: int, um: str, varios: str) -> str:
    return f"{n(k)} {um if k == 1 else varios}"


def primeiros(nomes, limite: int = PRIMEIROS) -> str:
    """Os primeiros nomes, em ordem, e quantos ficaram para o apêndice."""
    nomes = sorted(nomes)
    texto = codigo(nomes[:limite])
    if len(nomes) > limite:
        texto += f" e mais {n(len(nomes) - limite)} (lista completa no {link('apendice')})"
    return texto


# --------------------------------------------------------------------------
# Seções
# --------------------------------------------------------------------------

def _cabecalho(a: Auditoria) -> list[str]:
    linhas = [f"# {TITULO}", ""]
    if a.repositorio is None:
        linhas.append("- Repositório: todos os repositórios (`--todos`)")
    else:
        linhas.append(f"- Repositório: `{a.repositorio}`")
        juntados = [d for d in a.diretorios if d != a.repositorio]
        if juntados:
            linhas.append(f"- Diretórios juntados (mesmo commit inicial): "
                          f"{', '.join(f'`{d}`' for d in a.diretorios)}")
    linhas.append(f"- Período coberto: {quando(a.inicio)} a {quando(a.fim)}")
    recorte = []
    if a.desde:
        recorte.append(f"sessões iniciadas desde {quando(a.desde)}")
    if a.ate:
        recorte.append(f"registros até {quando(a.ate)}")
    if recorte:
        linhas.append(f"- Recorte pedido: {'; '.join(recorte)}")
    linhas.append(f"- Sessões: {n(a.sessoes)} · Pedidos: {n(a.pedidos)}")
    if a.versoes:
        faixa = (a.versoes[0] if len(a.versoes) == 1
                 else f"de {a.versoes[0]} a {a.versoes[-1]}")
        linhas.append(f"- Versões do Claude Code: {len(a.versoes)} ({faixa})")
    linhas.append("- Alcance: a retenção padrão das transcrições é de 30 dias; "
                  "sessões mais antigas podem já ter sido apagadas pelo Claude Code.")
    if a.falhas:
        linhas.append(f"- Falhas de leitura: {len(a.falhas)} arquivo(s) não lido(s)")
        linhas += [f"  - {f}" for f in a.falhas]
    if a.excluidas_comando_local:
        linhas.append(f"- Sessões de comando local, excluídas: {n(a.excluidas_comando_local)} "
                      f"(sem resposta de modelo; só comandos como `/context`)")
    if a.desconhecidos.tipos or a.desconhecidos.campos:
        linhas.append(f"- Formato desconhecido (contado, não é erro): "
                      f"{sum(a.desconhecidos.tipos.values())} registro(s) de tipo "
                      f"desconhecido, {sum(a.desconhecidos.campos.values())} campo(s) "
                      f"desconhecido(s); detalhe no {link('apendice')}")
    if not a.sessoes:
        linhas += ["", "Nenhuma sessão encontrada para este repositório no período. "
                   "Repositório sem histórico é um estado normal; o relatório passa a "
                   "ter números depois das primeiras sessões."]
    linhas += ["", como_ler(
        "uma sessão pertence ao repositório cuja raiz git contém o diretório em "
        "que ela rodou (E3); diretórios com o mesmo commit inicial são o mesmo "
        "repositório (E15). Sessão cujo arquivo não pôde ser lido fica fora de "
        "todos os números abaixo; ela é atribuída ao repositório pela pasta onde "
        "está, o que pode deixar alguma de fora.")]
    return linhas


def frase(x: Achado, a: Auditoria) -> str:
    v = x.valores
    if x.regra.startswith("peso_morto."):
        qual = " com arquivo" if v.get("so_com_arquivo") else ""
        texto = (f"{CATEGORIAS[v['categoria']]}: {n(v['nunca_usados'])} de "
                 f"{n(v['disponiveis'])} disponíveis{qual} sem nenhum uso no período.")
    elif x.regra == "peso_fixo":
        texto = (f"Mediana de {n(v['mediana'])} tokens carregados antes de qualquer "
                 f"trabalho, em {n(v['sessoes'])} sessões (de {n(v['minimo'])} a "
                 f"{n(v['maximo'])}).")
    elif x.regra == "commits_sem_hash":
        texto = (f"{n(v['sem_hash'])} de {n(v['chamadas'])} chamadas de commit não "
                 f"deixaram hash registrado (com `-q`: {n(v['silenciosas'])}).")
    elif x.regra == "modo_sem_rejeicao":
        texto = (f"{n(v['pedidos_no_modo'])} de {n(v['pedidos'])} pedidos "
                 f"({pct(v['pedidos_no_modo'], v['pedidos'])}) rodaram em modo de "
                 f"permissão que suprime rejeições ({codigo(v['modos'])}).")
    elif x.regra == "falhas_de_leitura":
        texto = f"{n(v['falhas'])} arquivo(s) de sessão não puderam ser lidos."
    elif x.regra == "formato_desconhecido":
        texto = (f"{n(v['tipos'])} registro(s) de tipo desconhecido e {n(v['campos'])} "
                 f"campo(s) desconhecido(s) nas transcrições.")
    else:
        texto = f"{x.regra}: {v}"
    return f"- {texto} → {link(x.secao)}"


def _atencao(a: Auditoria) -> list[str]:
    linhas = ["## O que chama atenção", ""]
    if a.achados:
        linhas += [frase(x, a) for x in a.achados]
    else:
        linhas.append("Nenhuma regra disparou.")
    if a.plataforma is not None:
        p = a.plataforma
        linhas += ["", "Custo fixo de plataforma, fora da contagem acima (anunciado sem "
                   "arquivo, vem da conta ou do Claude Code): "
                   f"{plural(p['skills'], 'skill', 'skills')}, "
                   f"{plural(p['tipos_subagente'], 'tipo de subagente', 'tipos de subagente')}, "
                   f"{plural(p['ferramentas'], 'ferramenta', 'ferramentas')} e "
                   f"{plural(p['servidores_mcp'], 'servidor MCP', 'servidores MCP')}. "
                   f"→ {link('peso-morto')}"]
    texto = ("cada linha sai de uma regra fixa e só diz um fato com número; não é "
             "nota nem recomendação. A seção indicada traz o detalhe e o limite.")
    if a.plataforma is not None:
        texto += (" As linhas de peso morto contam só o que tem arquivo, isto é, o que "
                  "você pode mudar (E16).")
    linhas += ["", como_ler(texto)]
    return linhas


def _resumo(r: ind.Resumo) -> str:
    return f"mediana {n(r.mediana)} · mínimo {n(r.minimo)} · máximo {n(r.maximo)}"


def _resumo_sem_minimo(r: ind.Resumo) -> str:
    return f"mediana {n(r.mediana)} · máximo {n(r.maximo)}"


def _peso_fixo(a: Auditoria) -> list[str]:
    pf = a.peso_fixo
    linhas = ["## Peso fixo", ""]
    if pf.resumo.n:
        linhas.append(f"Tokens de entrada da primeira resposta: {_resumo(pf.resumo)}.")
        linhas.append(f"Sessões com o dado: {n(pf.resumo.n)}; sem o dado: "
                      f"{n(len(pf.sem_dado))} (fork ou sem resposta do modelo).")
    else:
        linhas.append("Nenhuma sessão com o dado.")
    if a.peso_fixo_semanal:
        linhas += ["", "| Semana | Sessões | Mediana | Mínimo | Máximo |",
                   "|---|---:|---:|---:|---:|"]
        for semana, r in a.peso_fixo_semanal:
            linhas.append(f"| {semana} | {n(r.n)} | {n(r.mediana)} | {n(r.minimo)} | "
                          f"{n(r.maximo)} |")
    linhas += _reparticao(a)
    linhas += ["", como_ler(
        "é o `usage` da primeira resposta de cada sessão (E11): instruções, "
        "ferramentas, skills anunciadas e o primeiro pedido, que também entra e "
        "varia. Inclui cache: é tamanho de contexto, não custo em dinheiro. A "
        "repartição é estimativa: mede em caracteres as partes do primeiro pedido "
        "gravadas na transcrição e converte em tokens por um fator fixo.")]
    return linhas


GRUPOS_TITULO = {"plataforma": "Plataforma", "harness": "Harness", "pedido": "Pedido"}


def _reparticao(a: Auditoria) -> list[str]:
    r = a.reparticao
    if r is None or not r.medido:
        return ["", "Repartição: nenhuma sessão com a forma da requisição gravada."]
    fator = n(r.fator)
    linhas = ["", f"Repartição estimada, em {n(len(r.medido))} sessões com a forma da "
              f"requisição gravada ({fator} caracteres por token; é estimativa):", "",
              "| Grupo / parte | Tokens estimados, mediana por sessão | Parcela do peso fixo |",
              "|---|---:|---:|"]
    for grupo in ind.GRUPOS:
        linhas.append(f"| **{GRUPOS_TITULO[grupo]}** | **{n(round(r.resumo_grupo(grupo).mediana))}** "
                      f"| **{pct(r.soma_grupo(grupo), r.medido_total)}** |")
        for g, parte in ind.PARTES:
            if g == grupo and grupo != "pedido":
                linhas.append(f"| {parte} | {n(round(r.resumo(parte).mediana))} | "
                              f"{pct(r.soma(parte), r.medido_total)} |")
    linhas.append(f"| **Não explicado** | **{n(round(r.resumo_nao_explicado().mediana))}** "
                  f"| **{pct(r.nao_explicado, r.medido_total)}** |")
    if r.sem_forma:
        linhas += ["", f"Sessões com peso fixo e sem a forma da requisição, fora da "
                   f"repartição: {n(len(r.sem_forma))}."]
    linhas += ["", f"Plataforma é o prompt de sistema, as ferramentas embutidas e os anexos "
               f"do próprio Claude Code (ambiente, data, modelo). Harness é o que vem da "
               f"configuração: listas de skills e de subagentes, nomes das ferramentas "
               f"adiadas, ferramentas e instruções de servidores MCP, instruções e "
               f"memória, saída de hooks. O fator de {fator} caracteres por token vem do "
               f"diário 010; caracteres incluem o escape de JSON. O não explicado é o "
               f"medido menos a soma das partes: marcação das mensagens, diferença de "
               f"tokenização e o que a transcrição não grava."]
    return linhas


def _nunca_usadas_ferramentas(c: ind.Categoria) -> list[str]:
    """Ferramentas comuns por nome; as MCP agrupadas por servidor."""
    comuns = sorted(x for x in c.nunca_usados if not leitor.servidor_mcp(x))
    por_servidor_nunca = Counter(leitor.servidor_mcp(x) for x in c.nunca_usados
                                 if leitor.servidor_mcp(x))
    por_servidor_todas = Counter(leitor.servidor_mcp(x) for x in c.disponiveis
                                 if leitor.servidor_mcp(x))
    linhas = []
    if comuns:
        linhas.append(f"  - nunca usadas: {primeiros(comuns)}")
    if por_servidor_nunca:
        itens = [f"`{s}` {k} de {por_servidor_todas[s]}"
                 for s, k in sorted(por_servidor_nunca.items())]
        texto = ", ".join(itens[:PRIMEIROS])
        if len(itens) > PRIMEIROS:
            texto += (f" e mais {n(len(itens) - PRIMEIROS)} servidores "
                      f"(lista completa no {link('apendice')})")
        linhas.append("  - nunca usadas, MCP por servidor: " + texto)
    return linhas


def _por_origem(a: Auditoria, chave: str) -> list[str]:
    grupos = a.nunca_usados_por_origem.get(chave, {})
    if not grupos:
        return []
    partes = [f"{NOMES_DE_ORIGEM[o]} {n(len(grupos[o]))}" for o in org.ORIGENS if o in grupos]
    linhas = [f"  - nunca usados, por origem: {', '.join(partes)}"]
    com_arquivo = [x for o in org.ORIGENS if o in org.COM_ARQUIVO for x in grupos.get(o, [])]
    if com_arquivo and chave != "ferramentas":
        linhas.append(f"  - com arquivo (você pode mudar): {primeiros(com_arquivo)}; "
                      f"caminhos no {link('apendice')}")
    return linhas


def _peso_morto(a: Auditoria) -> list[str]:
    linhas = ["## Peso morto", "",
              f"Período: {quando(a.inicio)} a {quando(a.fim)}. Os itens nunca usados "
              f"são candidatos a revisar, não itens a remover.", ""]
    for chave, titulo in CATEGORIAS.items():
        c: ind.Categoria = getattr(a.peso_morto, chave)
        linhas.append(f"- **{titulo}**: disponíveis {n(len(c.disponiveis))} · usados "
                      f"{n(len(c.usados))} · nunca usados {n(len(c.nunca_usados))}")
        linhas.append(f"  - por sessão: disponíveis {_resumo_sem_minimo(c.resumo_disponiveis)}; "
                      f"usados {_resumo_sem_minimo(c.resumo_usados)}")
        linhas += _por_origem(a, chave)
        if chave == "ferramentas":
            linhas += _nunca_usadas_ferramentas(c)
        elif c.nunca_usados:
            linhas.append(f"  - nunca usados: {primeiros(c.nunca_usados)}")
        if c.usados_fora_da_lista:
            linhas.append(f"  - usados sem constar em nenhuma lista: "
                          f"{primeiros(c.usados_fora_da_lista)}")
    if a.nao_anunciados is not None:
        skills, tipos = a.nao_anunciados["skills"], a.nao_anunciados["tipos_subagente"]
        ocultas = sum(1 for p in skills if p.descricao and not p.descricao.invocavel_pelo_modelo)
        linhas += ["", f"Instaladas e não anunciadas: "
                   f"{plural(len(skills), 'skill', 'skills')} ({n(ocultas)} com "
                   f"`disable-model-invocation`) e "
                   f"{plural(len(tipos), 'tipo de subagente', 'tipos de subagente')}; não "
                   f"pesam na lista mostrada ao modelo; continuam acessíveis por `/comando` "
                   f"e ocupam espaço em disco."]
    texto = ("\"nunca usado\" vale só para o período acima; uma peça de uso raro "
             "parece morta. Uso inclui o que os subagentes chamaram; skill conta por "
             "chamada, por atribuição ou por `/comando`. O disponível é o que foi "
             "anunciado na sessão principal. Hooks e regras de instrução não entram: "
             "não há lista do disponível nas transcrições.")
    if a.origem_de is not None:
        texto += (" A origem cruza o anúncio com o inventário de agora (E16): o que tem "
                  "arquivo é de projeto, usuário, plugin ou gerenciado; sem arquivo, com "
                  "prefixo, é da conta; sem prefixo, embutido no Claude Code. Uma peça "
                  "apagada depois do período aparece como sem arquivo ou embutida.")
    linhas += ["", como_ler(texto)]
    return linhas


def _instalado(a: Auditoria) -> list[str]:
    i = a.instalado
    linhas = ["## O que está instalado", ""]
    if i is None:
        linhas += ["Inventário não disponível (repositório inexistente nesta máquina).", "",
                   como_ler("o inventário lê os arquivos do repositório e do diretório do "
                            "usuário; sem eles não há o que contar.")]
        return linhas
    cab = " | ".join(NOMES_DE_ORIGEM[e] for e in ESCOPOS_DO_INVENTARIO)
    linhas += [f"| Tipo | {cab} | Total |",
               "|---|" + "---:|" * (len(ESCOPOS_DO_INVENTARIO) + 1)]
    for tipo, titulo in TIPOS_DO_INVENTARIO.items():
        valores = [i.contagem[(tipo, e)] for e in ESCOPOS_DO_INVENTARIO]
        linhas.append(f"| {titulo} | " + " | ".join(n(v) for v in valores)
                      + f" | {n(sum(valores))} |")
    ins = i.instrucoes
    linhas += [
        "",
        f"- Instruções carregadas no início: {plural(ins.arquivos, 'arquivo', 'arquivos')}, "
        f"{n(ins.caracteres)} caracteres (cerca de "
        f"{n(round(ins.caracteres / ind.FATOR_CARACTERES_POR_TOKEN))} tokens), "
        f"{plural(ins.itens, 'item', 'itens')} de lista, {n(ins.com_motivo)} com motivo "
        f"(estimativa).",
        f"- Peças locais (pessoais, fora do controle de versão): {n(i.locais)} · "
        f"sob demanda (carregam só ao tocar a pasta): {n(i.sob_demanda)}",
        f"- Plugins: {n(i.plugins_ativos)} ativos de {n(i.plugins)} instalados",
    ]
    if i.falhas:
        linhas.append(f"- Arquivos de configuração que não puderam ser lidos: {n(i.falhas)}")
    linhas += ["", como_ler(
        "é o estado de agora, lido dos arquivos (repositório, diretório do usuário, "
        "plugins ativos e política gerenciada), não do período. \"Com motivo\" é "
        "estimativa: conta itens com `Motivo:`, `porque`, `para evitar` e afins, e "
        "erra nos dois sentidos. O tamanho em tokens usa o mesmo fator do peso fixo.")]
    return linhas


def _custo(a: Auditoria) -> list[str]:
    c = a.custo
    linhas = ["## Custo", "",
              f"- Total: {n(c.total.total)} tokens; subagentes {n(c.total.subagentes)} "
              f"({pct(c.total.subagentes, c.total.total)})",
              f"- Por sessão: {_resumo(c.resumo_sessao)}",
              f"- Por pedido: {_resumo(c.resumo_pedido)} ({n(c.resumo_pedido.n)} pedidos)",
              f"- Sem pedido atribuído: {n(c.sem_pedido)} tokens da sessão principal"]
    if a.caros:
        linhas += ["", f"Os {len(a.caros)} pedidos mais caros:", "",
                   "| Início do pedido | Tokens | Subagentes |", "|---|---:|---:|"]
        for p in a.caros:
            linhas.append(f"| {quando(p.inicio)} | {n(p.gasto.total)} | "
                          f"{pct(p.gasto.subagentes, p.gasto.total)} |")
    linhas += ["", como_ler(
        "soma de entrada, saída e cache (criado e lido), uma vez por resposta "
        "(E4). Cache lido entra com o mesmo peso: o número mede volume, não "
        "dinheiro. Trabalho disparado por aviso de tarefa em segundo plano entra "
        "no pedido humano anterior (E9).")]
    return linhas


def _intervencoes(a: Auditoria) -> list[str]:
    it = a.intervencoes
    t = it.total
    com_sinal = sum(1 for x in it.por_pedido.values() if x.sinais)
    modos = sorted(it.por_modo.items(), key=lambda kv: (-kv[1], kv[0]))
    linhas = ["## Intervenções", "",
              f"- Pedidos humanos: {n(t.pedidos)} em {n(a.sessoes)} sessões "
              f"(por sessão: {_resumo(it.resumo_pedidos)})",
              f"- Interrupções: {n(t.interrupcoes)} · rejeições de ferramenta: "
              f"{n(t.rejeicoes)} ({n(t.rejeicoes_com_comentario)} com comentário) · "
              f"mensagens no meio do turno: {n(t.mensagens_no_meio)}",
              f"- Pedidos com algum sinal: {n(com_sinal)} de {n(t.pedidos)} · sessões "
              f"sem nenhum sinal: {n(it.sessoes_sem_sinal)} de {n(a.sessoes)}",
              "- Modo de permissão dos pedidos: " + (", ".join(
                  f"`{m}` {n(k)}" for m, k in modos) or "—"),
              "", "Avisos:", ""]
    sem_rejeicao = a.pedidos_sem_rejeicao
    linhas += [
        "- São contagens cruas, ao lado do número de pedidos. Com tão poucos "
        "eventos, nenhuma taxa ou ordenação de sessões tem sentido.",
        f"- Nos modos {codigo(MODOS_SEM_REJEICAO)} o usuário não é consultado, e a "
        f"rejeição de ferramenta não tem como aparecer: {n(sem_rejeicao)} de "
        f"{n(t.pedidos)} pedidos rodaram assim.",
        "- Atenção: a ausência de sinais não indica ausência de correções. A "
        "correção digitada depois que o turno acaba é só mais um pedido.",
        "- \"Pedidos por tarefa\", a medida mais promissora, ainda não existe: o "
        "critério que agrupa pedidos em tarefa está em aberto (E9).",
        "", como_ler(
            "interrupção e mensagem no meio do turno medem também o hábito de "
            "acompanhar o agente enquanto ele trabalha, não só como ele se saiu.")]
    return linhas


def _hooks(a: Auditoria) -> list[str]:
    h = a.hooks
    linhas = ["## Hooks", ""]
    if not h.total:
        linhas.append("Nenhum desfecho visível de hook no período.")
    else:
        linhas += [f"Desfechos visíveis: {n(h.total)}, em {n(h.sessoes_com_hook)} sessões "
                   f"({n(h.em_subagentes)} em subagentes); bloqueios: {n(h.bloqueios)}.",
                   "", "| Evento | Desfechos visíveis | Por tipo |", "|---|---:|---|"]
        for evento, total in sorted(h.por_evento.items(), key=lambda kv: (-kv[1], kv[0])):
            tipos = sorted(((t, k) for (t, e), k in h.por_tipo_e_evento.items()
                            if e == evento), key=lambda tk: (-tk[1], tk[0]))
            detalhe = ", ".join(f"{TIPOS_DE_HOOK.get(t, t)} {n(k)}" for t, k in tipos)
            linhas.append(f"| `{evento}` | {n(total)} | {detalhe} |")
    linhas += ["", como_ler(
        "só aparece o que o hook deixou visível: saída, falha, bloqueio, tempo "
        "esgotado. Hook que roda bem e calado não deixa registro, então zero "
        "desfechos visíveis não quer dizer que o hook não roda (E6). Evento `?` é "
        "registro que não diz o evento.")]
    return linhas


def _commits(a: Auditoria) -> list[str]:
    c = a.commits
    linhas = ["## Commits", ""]
    if not c.chamadas:
        linhas.append("Nenhuma chamada de `git commit` no período.")
    else:
        linhas += [
            f"- Chamadas de `git commit`: {n(c.chamadas)}, em {n(c.sessoes_com_commit)} "
            f"sessões ({n(c.em_subagentes)} em subagentes)",
            f"- Com hash registrado: {n(c.com_hash)} · sem hash: {n(c.sem_hash)}",
            f"- Silenciosas (`-q` ou `--quiet`): {n(c.silenciosas)} · amends: "
            f"{n(c.amends)} · com erro: {n(c.com_erro)}"]
        if c.aproximadas:
            linhas.append(f"- Detectadas por padrão, sem análise do comando: "
                          f"{n(c.aproximadas)}")
        linhas += _ligacao(a)
        if c.silenciosas:
            linhas += [
                "", "Efeito das chamadas silenciosas: com `-q` o git não imprime o "
                "hash, e a transcrição não o registra. A ligação da sessão ao commit "
                "passa a depender da janela de horário (E7), que pode ser ambígua e "
                "se perde quando a branch é apagada.",
                "", "Regra que resolve, para o `CLAUDE.md` do repositório: "
                "\"Faça `git commit` sem `-q`.\""]
    linhas += ["", como_ler(
        "conta comandos `git commit` analisados, incluindo os de subagentes; "
        "dentro de `bash -c` ou `eval` não aparecem. Sem hash registrado não quer "
        "dizer que o commit não existe, só que a transcrição não diz qual foi. A "
        "ligação pela janela usa o repositório do diretório da chamada (E3): "
        "comando que faz `cd` para outro repositório fica sem ligação. O amend é "
        "o do comando; quando o commit foi ligado, o histórico git decide (E7).")]
    return linhas


def _ligacao(a: Auditoria) -> list[str]:
    if a.sem_git:
        return ["- Ligação aos commits do repositório: consulta ao git pulada (`--sem-git`)."]
    lig = a.ligacao
    if lig is None:
        return []
    f = lig.por_forma()
    linhas = [f"- Ligação aos commits: com hash: {n(f['hash'])} · ligadas por janela: "
              f"{n(f['janela'])} · ambíguas: {n(f['ambigua'])} · sem ligação: "
              f"{n(f['sem_ligacao'])}"]
    motivos = lig.sem_ligacao_por_motivo()
    if motivos:
        linhas.append("  - sem ligação, por motivo: " + ", ".join(
            f"{m} {n(k)}" for m, k in sorted(motivos.items(), key=lambda kv: (-kv[1], kv[0]))))
    linhas.append(f"- Amends: {n(lig.amends)} (pelo comando: {n(lig.amends_comando)}; "
                  f"o git confirmou {n(lig.amends_confirmados)} e não confirmou "
                  f"{n(lig.amends_nao_confirmados)}; achados só pelo git: "
                  f"{n(lig.amends_so_pelo_git)})")
    if lig.amends_kind:
        linhas.append(f"  - o `kind` gravado pelo Claude Code diz amend em "
                      f"{n(lig.amends_kind)}; guardado à parte, não entra na conta "
                      f"(dá falso positivo com `--amend` dentro de heredoc)")
    ligados = lig.commits_ligados
    linhas.append(f"- Dos {n(len(ligados))} commits ligados: revertidos depois: "
                  f"{n(len(lig.revertidos))} · refeitos por amend depois: "
                  f"{n(len(lig.substituidos))}")
    return linhas


def _apendice(a: Auditoria) -> list[str]:
    linhas = ["## Apêndice", ""]
    vazio = True
    for chave, titulo in CATEGORIAS.items():
        c: ind.Categoria = getattr(a.peso_morto, chave)
        if not c.nunca_usados:
            continue
        vazio = False
        linhas += [f"### {titulo} nunca usados ({n(len(c.nunca_usados))})", ""]
        for nome in sorted(c.nunca_usados):
            o = a.origem(chave, nome)
            if o is None:
                linhas.append(f"- `{nome}`")
            else:
                caminho = f" — `{o.caminho}`" if o.caminho else ""
                linhas.append(f"- `{nome}` ({NOMES_DE_ORIGEM[o.origem]}){caminho}")
        linhas.append("")
    if a.nao_anunciados:
        pecas = [*a.nao_anunciados["skills"], *a.nao_anunciados["tipos_subagente"]]
        if pecas:
            vazio = False
            linhas += [f"### Instalados e não anunciados ({n(len(pecas))})", ""]
            linhas += [f"- `{p.nome}` ({p.tipo}, {NOMES_DE_ORIGEM[p.escopo]}) — `{p.origem}`"
                       for p in pecas]
            linhas.append("")
    if a.desconhecidos.tipos or a.desconhecidos.campos:
        vazio = False
        linhas += ["### Formato desconhecido", ""]
        for nome, qtd in sorted(a.desconhecidos.tipos.items()):
            linhas.append(f"- tipo `{nome}`: {n(qtd)}")
        for nome, qtd in sorted(a.desconhecidos.campos.items()):
            linhas.append(f"- campo `{nome}`: {n(qtd)}")
        linhas.append("")
    if vazio:
        linhas += ["Nada a detalhar.", ""]
    linhas.append(como_ler(
        "listas completas do que o corpo resume. Formato desconhecido interessa a quem "
        "mantém o leitor: tipos e campos que o leitor contou e não interpretou (E1)."))
    return linhas


def markdown(a: Auditoria) -> str:
    partes = [_cabecalho(a)]
    if a.sessoes:
        partes += [_atencao(a), _peso_fixo(a), _peso_morto(a)]
        if a.instalado is not None:
            partes.append(_instalado(a))
        partes += [_custo(a), _intervencoes(a), _hooks(a), _commits(a), _apendice(a)]
    return "\n\n".join("\n".join(p) for p in partes) + "\n"
