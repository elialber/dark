"""Testes da repartição do contexto (`/context` em modo não interativo).

As amostras de tests/fixtures/contexto/ têm a estrutura da saída real do
Claude Code 2.1.326, com nomes inventados. Nenhum teste chama o Claude Code:
o executor é injetado.
"""

from pathlib import Path

import pytest

from dark import context_usage

AMOSTRAS = Path(__file__).parent / "fixtures" / "contexto"


def ler(nome: str) -> str:
    return (AMOSTRAS / nome).read_text(encoding="utf-8")


def analisar(nome: str) -> context_usage.Reparticao:
    return context_usage.analisar(ler(nome))


# --- números ---------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("319", 319),
    ("10", 10),
    ("1,234", 1234),
    ("767,000", 767000),
    ("2.5k", 2500),
    ("12.3k", 12300),
    ("33k", 33000),
    ("33K", 33000),
    ("~220", 220),
    ("~1.2k", 1200),
    ("~1,500", 1500),
    ("~0.5k", 500),
    ("1m", 1_000_000),
    ("1.18m", 1_180_000),
    (" 59 ", 59),
])
def test_numero_com_separador_e_sufixo(texto, esperado):
    assert context_usage.numero(texto) == esperado


@pytest.mark.parametrize("texto", ["", "muitos", "1.2.3", "k", "12x", "-5"])
def test_numero_invalido_devolve_none(texto):
    assert context_usage.numero(texto) is None


# --- saída completa ----------------------------------------------------------

def test_completa_cabecalho():
    r = analisar("completa.md")
    assert r.modelo == "modelo-exemplo"
    assert r.total == 10900
    assert r.janela == 200_000


def test_completa_categorias_e_tipos():
    r = analisar("completa.md")
    por_nome = {c.nome: c for c in r.categorias}
    assert list(por_nome) == [
        "System prompt", "System tools", "MCP tools (deferred)",
        "System tools (deferred)", "Custom agents", "Memory files", "Skills",
        "Messages", "Free space", "Autocompact buffer",
    ]
    assert por_nome["System prompt"].tokens == 2500
    assert por_nome["System prompt"].tipo == "usado"
    assert por_nome["MCP tools (deferred)"].tipo == "adiado"
    assert por_nome["System tools (deferred)"].tipo == "adiado"
    assert por_nome["Free space"].tipo == "livre"
    assert por_nome["Autocompact buffer"].tipo == "reserva"
    assert all(c.conhecida for c in r.categorias)


def test_completa_soma_das_categorias_contra_total():
    r = analisar("completa.md")
    # 2500 + 5700 + 40 + 319 + 2300 + 10: só as que contam no total
    assert r.soma_categorias == 10869
    assert r.total - r.soma_categorias == 31          # arredondamento do texto


def test_completa_ferramentas_adiadas_fora_do_total():
    r = analisar("completa.md")
    assert r.adiadas == 16300 + 120


def test_completa_skills_com_origem():
    r = analisar("completa.md")
    assert [(s.nome, s.origem, s.tokens) for s in r.skills] == [
        ("exemplo-skill", "User", 220),
        ("outra-skill", "Project", 1200),
        ("ferramenta:exemplo-plugin", "Plugin (exemplo-plugin)", 90),
        ("skill-embutida", "Built-in", 480),
        ("skill-sincronizada", "claude.ai sync", 340),
    ]


def test_completa_mcp_agentes_e_memoria():
    r = analisar("completa.md")
    assert [(f.nome, f.origem, f.tokens) for f in r.ferramentas_mcp] == [
        ("mcp__servidor-a__ferramenta_um", "servidor-a", 59),
        ("mcp__servidor-b__ferramenta_dois", "servidor-b", 61),
    ]
    assert [(a.nome, a.origem, a.tokens) for a in r.agentes] == [
        ("agente-exemplo", "Project", 20),
        ("outro-agente", "User", 20),
    ]
    assert [(m.nome, m.origem, m.tokens) for m in r.memoria] == [
        ("/repo/exemplo/CLAUDE.md", "Project", 300),
        ("/home/exemplo/.claude/CLAUDE.md", "User", 19),
    ]


def test_completa_nada_fica_sem_reconhecer():
    assert analisar("completa.md").nao_reconhecido == []


# --- variações ---------------------------------------------------------------

def test_sem_skills():
    r = analisar("sem-skills.md")
    assert r.skills == [] and r.ferramentas_mcp == [] and r.agentes == []
    assert r.total == 8200 and r.soma_categorias == 8210
    assert r.adiadas == 16300
    assert r.nao_reconhecido == []


def test_numeros_com_separador_e_sufixo_na_saida():
    r = analisar("numeros.md")
    assert r.total == 1_200_000 and r.janela == 2_000_000
    por_nome = {c.nome: c.tokens for c in r.categorias}
    assert por_nome["System prompt"] == 1234
    assert por_nome["Messages"] == 1_180_000
    assert por_nome["Free space"] == 767_000
    assert por_nome["Autocompact buffer"] == 33_000
    assert [s.tokens for s in r.skills] == [1500, 500]
    assert r.adiadas == 0
    assert r.nao_reconhecido == []


def test_secao_e_linhas_desconhecidas_sao_guardadas_e_nao_derrubam():
    r = analisar("secao-desconhecida.md")
    assert r.total == 8300
    # categoria nova entra (conta no total) mas é marcada e relatada
    nova = [c for c in r.categorias if c.nome == "Output styles"]
    assert len(nova) == 1 and not nova[0].conhecida and nova[0].tipo == "usado"
    assert r.soma_categorias == 8300
    textos = "\n".join(r.nao_reconhecido)
    assert "Output styles" in textos                 # categoria desconhecida
    assert "**Cache:**" in textos                    # linha de cabeçalho nova
    assert "### Hooks" in textos                     # seção nova
    assert "hook-exemplo" in textos                  # linhas da seção nova
    assert "muitos" in textos                        # número ilegível
    assert "Linha solta no fim." in textos
    assert r.skills == []                            # a linha ilegível não vira skill


def test_saida_vazia_e_erro():
    with pytest.raises(context_usage.SaidaInvalida):
        analisar("vazia.md")


def test_saida_sem_categoria_e_erro():
    with pytest.raises(context_usage.SaidaInvalida):
        analisar("sem-categorias.md")


def test_analisar_nao_depende_de_fim_de_linha():
    texto = ler("completa.md").replace("\n", "\r\n")
    assert context_usage.analisar(texto) == analisar("completa.md")


# --- parte não atribuída -----------------------------------------------------

def test_nao_atribuido_contra_usage():
    r = analisar("completa.md")
    na = context_usage.nao_atribuido(r, 16350)
    assert na.medido == 16350 and na.informado == 10900
    assert na.tokens == 5450
    assert na.percentual == pytest.approx(33.333, abs=0.001)


def test_nao_atribuido_negativo_quando_usage_e_menor():
    na = context_usage.nao_atribuido(analisar("completa.md"), 10000)
    assert na.tokens == -900
    assert na.percentual == pytest.approx(-9.0)


def test_nao_atribuido_rejeita_usage_invalido():
    with pytest.raises(ValueError):
        context_usage.nao_atribuido(analisar("completa.md"), 0)


# --- execução ----------------------------------------------------------------

def test_executar_usa_executor_injetado(tmp_path):
    chamadas = []

    def executor(argumentos, diretorio):
        chamadas.append((argumentos, diretorio))
        return ler("completa.md")

    texto = context_usage.executar(tmp_path, executor=executor)
    assert texto == ler("completa.md")
    [(argumentos, diretorio)] = chamadas
    assert diretorio == tmp_path
    assert argumentos[:3] == ["claude", "-p", "/context"]
    # não deixa transcrição no diretório do usuário
    assert "--no-session-persistence" in argumentos


def test_executar_rejeita_diretorio_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        context_usage.executar(tmp_path / "nao-existe", executor=lambda a, d: "")


def test_medir_junta_execucao_e_analise(tmp_path):
    r = context_usage.medir(tmp_path, executor=lambda a, d: ler("sem-skills.md"))
    assert r.total == 8200
