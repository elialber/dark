"""Testes do inventário estático do harness.

Os arquivos sintéticos ficam em tests/fixtures/inventario/ com nomes
neutros: `dot-x` no lugar de `.x` e `CLAUDE.md.fixture` no lugar de
`CLAUDE.md`. Guardados com os nomes reais, eles seriam harness de verdade
deste repositório (o Claude Code carrega CLAUDE.md aninhado e
.claude/skills de subdiretório). A função `montar` copia cada árvore para
um diretório temporário, restaura os nomes e troca `{REPO}`, `{CONFIG}` e
a pasta `MEMORIA` pelos caminhos da cópia.
"""

import dataclasses
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dark import inventory
from dark.inventory import Inventario

FIXTURES = Path(__file__).parent / "fixtures" / "inventario"
SRC = Path(__file__).parent.parent / "src"

SEGREDOS = [
    "valor-secreto-hook", "valor-secreto-cabecalho-hook",
    "valor-secreto-mcp-projeto", "valor-secreto-cabecalho-mcp",
    "valor-secreto-usuario", "valor-secreto-local", "valor-secreto-manifesto",
    "valor-secreto-env-settings", "valor-secreto-credencial",
    "pessoa@exemplo.invalid",
]


def _nome_real(nome: str) -> str:
    if nome.startswith("dot-"):
        nome = "." + nome[4:]
    return nome.removesuffix(".fixture")


def _copiar(origem: Path, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    for item in origem.iterdir():
        alvo = destino / _nome_real(item.name)
        if item.is_dir():
            _copiar(item, alvo)
        else:
            shutil.copyfile(item, alvo)


def montar(case: str, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Copia o caso para tmp_path; devolve (repo, config, gerenciado)."""
    base = tmp_path / case
    _copiar(FIXTURES / case, base)
    repo, config, gerenciado = base / "repo", base / "config", base / "gerenciado"
    for d in (repo, config, gerenciado):
        d.mkdir(exist_ok=True)
    for arq in base.rglob("*.json"):
        texto = arq.read_text(encoding="utf-8")
        arq.write_text(texto.replace("{REPO}", str(repo)).replace("{CONFIG}", str(config)),
                       encoding="utf-8")
    memoria = config / "projects" / "MEMORIA"
    if memoria.exists():
        memoria.rename(config / "projects" / inventory.pasta_projeto(repo))
    return repo, config, gerenciado


def inventariar(case: str, tmp_path: Path) -> Inventario:
    repo, config, gerenciado = montar(case, tmp_path)
    return inventory.inventariar(repo, config, gerenciado=gerenciado, ambiente={})


@pytest.fixture(scope="module")
def completo(tmp_path_factory):
    return inventariar("completo", tmp_path_factory.mktemp("inv"))


def _uma(inv: Inventario, tipo: str, nome: str):
    achadas = [p for p in inv.pecas if p.tipo == tipo and p.nome == nome]
    assert len(achadas) == 1, (tipo, nome, [(p.tipo, p.nome) for p in inv.pecas])
    return achadas[0]


# --- uma peça de cada tipo, em cada escopo ---------------------------------------

ESPERADAS = [
    # (tipo, nome, escopo, plugin, local, sob_demanda)
    ("instrucao", "CLAUDE.md", "gerenciado", None, False, False),
    ("instrucao", "CLAUDE.md", "usuario", None, False, False),
    ("instrucao", "rules/geral.md", "usuario", None, False, False),
    ("instrucao", "CLAUDE.md", "projeto", None, False, False),
    ("instrucao", "CLAUDE.local.md", "projeto", None, True, False),
    ("instrucao", "sub/CLAUDE.md", "projeto", None, False, True),
    ("instrucao", "rules/estilo.md", "projeto", None, False, False),
    ("instrucao", "rules/api.md", "projeto", None, False, True),
    ("instrucao", "memory/MEMORY.md", "projeto", None, True, False),
    ("instrucao", "@docs/importado.md", "projeto", None, False, False),
    ("skill", "skill-gerenciada", "gerenciado", None, False, False),
    ("skill", "skill-usuario", "usuario", None, False, False),
    ("skill", "comando-usuario", "usuario", None, False, False),
    ("skill", "skill-projeto", "projeto", None, False, False),
    ("skill", "comando-projeto", "projeto", None, False, False),
    ("skill", "sub:skill-aninhada", "projeto", None, False, True),
    ("skill", "plugin-exemplo:skill-plugin", "plugin", "plugin-exemplo", False, False),
    ("skill", "plugin-exemplo:comando-plugin", "plugin", "plugin-exemplo", False, False),
    ("subagente", "agente-usuario", "usuario", None, False, False),
    ("subagente", "agente-em-subpasta", "usuario", None, False, False),
    ("subagente", "agente-projeto", "projeto", None, False, False),
    ("subagente", "plugin-exemplo:agente-plugin", "plugin", "plugin-exemplo", False, False),
    ("mcp", "servidor-gerenciado", "gerenciado", None, False, False),
    ("mcp", "servidor-usuario", "usuario", None, False, False),
    ("mcp", "servidor-local", "projeto", None, True, False),
    ("mcp", "servidor-projeto", "projeto", None, False, False),
    ("mcp", "servidor-plugin", "plugin", "plugin-exemplo", False, False),
    ("mcp", "servidor-manifesto", "plugin", "plugin-exemplo", False, False),
]


@pytest.mark.parametrize("tipo,nome,escopo,plugin,local,sob_demanda", ESPERADAS)
def test_peca_de_cada_tipo_em_cada_escopo(completo, tipo, nome, escopo, plugin, local,
                                          sob_demanda):
    achadas = [p for p in completo.pecas
               if p.tipo == tipo and p.nome == nome and p.escopo == escopo]
    assert len(achadas) == 1, [(p.tipo, p.nome, p.escopo) for p in completo.pecas]
    p = achadas[0]
    assert (p.plugin, p.local, p.sob_demanda) == (plugin, local, sob_demanda)
    assert p.origem.is_file()
    texto = p.origem.read_text(encoding="utf-8")
    if tipo in ("instrucao", "skill", "subagente"):
        assert p.caracteres == len(texto)
        assert p.linhas == len(texto.splitlines())
    assert p.caracteres > 0 and p.linhas > 0


def test_hooks_de_cada_escopo(completo):
    hooks = {(h.escopo, h.local, h.hook.evento): h for h in completo.pecas if h.tipo == "hook"}
    assert set(hooks) == {
        ("gerenciado", False, "UserPromptSubmit"),
        ("usuario", False, "SessionStart"),
        ("projeto", False, "PreToolUse"),
        ("projeto", False, "Stop"),
        ("projeto", True, "PostToolUse"),
        ("plugin", False, "PreToolUse"),
        ("usuario", False, None),            # declarado no cabeçalho de uma skill
    }
    pre = hooks[("projeto", False, "PreToolUse")].hook
    assert (pre.filtro, pre.tipo) == ("Bash", "command")
    assert pre.comando == "TOKEN_PROJETO=*** ./verifica.sh"
    assert pre.variaveis == ["TOKEN_PROJETO"]
    pos = hooks[("projeto", True, "PostToolUse")].hook
    assert (pos.filtro, pos.comando) == ("Edit|Write", "./formata.sh")
    stop = hooks[("projeto", False, "Stop")].hook
    assert (stop.filtro, stop.tipo, stop.comando) == (None, "http", "http://localhost:9/aviso")
    assert stop.cabecalhos == ["Authorization"] and stop.variaveis == ["CHAVE_AVISO"]
    plugin = hooks[("plugin", False, "PreToolUse")]
    assert plugin.plugin == "plugin-exemplo"
    assert plugin.hook.comando == "${CLAUDE_PLUGIN_ROOT}/bin/checa"
    assert hooks[("gerenciado", False, "UserPromptSubmit")].hook.tipo == "prompt"
    cabecalho = hooks[("usuario", False, None)]
    assert cabecalho.nome == "skill-com-hook" and cabecalho.hook.analisado is False


def test_permissoes_de_cada_escopo(completo):
    perms = {(p.escopo, p.local, p.origem.name): p.permissoes
             for p in completo.pecas if p.tipo == "permissao"}
    assert set(perms) == {
        ("gerenciado", False, "managed-settings.json"),
        ("gerenciado", False, "10-extra.json"),
        ("usuario", False, "settings.json"),
        ("projeto", False, "settings.json"),
        ("projeto", True, "settings.local.json"),
    }
    proj = perms[("projeto", False, "settings.json")]
    assert (proj.modo_padrao, proj.permitir, proj.negar, proj.perguntar) == ("acceptEdits", 2, 1, 1)
    local = perms[("projeto", True, "settings.local.json")]
    assert (local.modo_padrao, local.permitir, local.negar, local.perguntar) == (None, 1, 0, 0)
    assert perms[("usuario", False, "settings.json")].modo_padrao == "plan"
    assert perms[("gerenciado", False, "10-extra.json")].perguntar == 1


# --- instruções ----------------------------------------------------------------------

def test_instrucao_conta_itens_e_motivos(completo):
    i = next(p for p in completo.pecas
             if p.tipo == "instrucao" and p.nome == "CLAUDE.md" and p.escopo == "projeto")
    d = i.instrucao
    assert d.itens == 6                 # 4 com marcador, 2 numerados; bloco de código fora
    assert d.com_motivo == 3            # "Motivo:", "porque", "para que"
    assert d.motivo_estimado is True
    assert d.importa == ["docs/importado.md"]


def test_instrucao_sem_motivo(completo):
    i = next(p for p in completo.pecas if p.nome == "CLAUDE.local.md")
    assert (i.instrucao.itens, i.instrucao.com_motivo) == (1, 0)


def test_importacoes_seguem_ate_quatro_saltos(completo):
    nomes = {p.nome for p in completo.pecas if p.tipo == "instrucao"}
    assert {"@docs/importado.md", "@docs/nivel2.md", "@docs/nivel3.md",
            "@docs/nivel4.md"} <= nomes
    assert "@docs/nivel5.md" not in nomes
    assert not any("nao-importado" in n or "tambem-nao" in n for n in nomes)
    imp = _uma(completo, "instrucao", "@docs/importado.md")
    assert imp.instrucao.importado_por.name == "CLAUDE.md"
    assert (imp.instrucao.itens, imp.instrucao.com_motivo) == (2, 1)


def test_memoria_de_topico_e_claude_md_de_plugin_ficam_fora(completo):
    origens = {p.origem.name for p in completo.pecas}
    assert "exemplo.md" not in origens
    assert not any(p.tipo == "instrucao" and p.escopo == "plugin" for p in completo.pecas)


# --- skills e subagentes ----------------------------------------------------------------

def test_skill_com_descricao_curta_e_corpo_longo(completo):
    s = _uma(completo, "skill", "skill-projeto")
    assert s.descricao.caracteres == len("Faz uma coisa curta.")
    assert s.descricao.corpo_caracteres > 2000
    assert s.descricao.corpo_linhas > 40
    assert s.descricao.corpo_caracteres + s.descricao.caracteres < s.caracteres


def test_descricao_em_bloco_dobrado_e_entre_aspas(completo):
    a = _uma(completo, "subagente", "agente-projeto")
    assert a.descricao.caracteres == len("Revisa mudanças de exemplo em duas linhas.")
    s = _uma(completo, "skill", "skill-usuario")
    assert s.descricao.caracteres == len("Skill pessoal de exemplo.")
    assert s.descricao.invocavel_pelo_modelo is False
    assert _uma(completo, "skill", "comando-usuario").descricao.caracteres == 0


def test_plugins_inativos_nao_entram_mas_sao_relatados(completo):
    assert not any("inativa" in p.nome for p in completo.pecas)
    estado = {p.nome: p.ativo for p in completo.plugins}
    assert estado == {"plugin-exemplo@mercado-exemplo": True,
                      "plugin-desligado@mercado-exemplo": False,
                      "plugin-outro-projeto@mercado-exemplo": False}


# --- servidores MCP e segredos -------------------------------------------------------

def test_servidor_mcp_guarda_transporte_e_nomes_de_variaveis(completo):
    m = {p.nome: p.mcp for p in completo.pecas if p.tipo == "mcp"}
    assert m["servidor-projeto"].transporte == "stdio"
    assert m["servidor-projeto"].variaveis == ["CHAVE_PROJETO"]
    assert m["servidor-remoto"].transporte == "http"
    assert m["servidor-remoto"].cabecalhos == ["Authorization"]
    assert m["servidor-usuario"].transporte == "sse"
    assert m["servidor-plugin"].transporte == "ws"
    assert m["servidor-local"].variaveis == ["CHAVE_LOCAL"]
    assert "servidor-de-outro-projeto" not in m


def test_nenhum_valor_secreto_aparece_no_resultado(completo):
    tudo = repr(completo) + json.dumps(inventory.como_dict(completo), ensure_ascii=False)
    for segredo in SEGREDOS:
        assert segredo not in tudo, segredo


def test_arquivo_de_credenciais_nunca_e_aberto(tmp_path, monkeypatch):
    repo, config, gerenciado = montar("completo", tmp_path)
    abertos = []
    original = Path.read_text

    def espiao(self, *a, **k):
        abertos.append(self.name)
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", espiao)
    inventory.inventariar(repo, config, gerenciado=gerenciado, ambiente={})
    assert abertos and ".credentials.json" not in abertos


# --- falhas, vazio, somente leitura ---------------------------------------------------

def test_configuracao_malformada_relata_e_segue(tmp_path):
    inv = inventariar("quebrado", tmp_path)
    falhas = {(f.arquivo.name, f.arquivo.parent.name) for f in inv.falhas}
    assert ("settings.json", ".claude") in falhas        # projeto, JSON cortado
    assert ("settings.json", "config") in falhas         # usuário, não é JSON
    assert (".claude.json", "config") in falhas
    assert (".mcp.json", "repo") in falhas               # mcpServers não é objeto
    assert ("SKILL.md", "skill-sem-fim") in falhas
    assert ("installed_plugins.json", "plugins") in falhas   # pasta do plugin ausente
    assert any(f.arquivo.name == "nao-existe.md" for f in inv.falhas)
    assert all(f.mensagem for f in inv.falhas)
    nomes = {p.nome for p in inv.pecas}
    assert {"skill-boa", "agente-bom", "CLAUDE.md"} <= nomes


def test_repositorio_sem_harness(tmp_path):
    inv = inventariar("vazio", tmp_path)
    assert inv.pecas == [] and inv.falhas == [] and inv.plugins == []


def _retrato(raiz: Path) -> dict:
    return {str(p.relative_to(raiz)): (p.stat().st_mtime_ns, p.read_bytes())
            for p in raiz.rglob("*") if p.is_file()}


def test_somente_leitura(tmp_path):
    repo, config, gerenciado = montar("completo", tmp_path)
    antes = _retrato(tmp_path)
    inventory.inventariar(repo, config, gerenciado=gerenciado, ambiente={})
    assert _retrato(tmp_path) == antes


# --- entradas injetáveis -----------------------------------------------------------------

def test_diretorio_de_configuracao_respeita_variavel(tmp_path):
    assert inventory.diretorio_config({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path
    assert inventory.diretorio_config({}) == Path.home() / ".claude"


def test_config_padrao_vem_do_ambiente(tmp_path):
    repo, config, gerenciado = montar("completo", tmp_path)
    inv = inventory.inventariar(repo, gerenciado=gerenciado,
                                 ambiente={"CLAUDE_CONFIG_DIR": str(config)})
    assert any(p.nome == "skill-usuario" for p in inv.pecas)


def test_claude_json_fica_ao_lado_da_pasta_padrao(tmp_path):
    casa = tmp_path / "casa"
    (casa / ".claude").mkdir(parents=True)
    (casa / ".claude.json").write_text('{"mcpServers": {"servidor-ao-lado": {"command": "x"}}}',
                                       encoding="utf-8")
    vazio = tmp_path / "repo"
    vazio.mkdir()
    inv = inventory.inventariar(vazio, casa / ".claude", gerenciado=tmp_path / "nada",
                                 ambiente={})
    assert [p.nome for p in inv.pecas] == ["servidor-ao-lado"]


def test_pasta_de_projeto_codifica_o_caminho():
    assert inventory.pasta_projeto(Path("/mnt/c/Repos/Ex_1")) == "-mnt-c-Repos-Ex-1"


def test_nao_importa_o_leitor():
    codigo = ("import sys; import dark.inventory; "
              "sys.exit(1 if 'dark.reader' in sys.modules else 0)")
    r = subprocess.run([sys.executable, "-c", codigo], env={**os.environ, "PYTHONPATH": str(SRC)})
    assert r.returncode == 0


def test_pecas_sao_dataclasses_congeladas(completo):
    p = completo.pecas[0]
    assert dataclasses.is_dataclass(p)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.nome = "outro"


# --- comando mínimo -----------------------------------------------------------------------

def test_comando_imprime_contagens(tmp_path, capsys):
    repo, config, gerenciado = montar("completo", tmp_path)
    assert inventory.main([str(repo), "--config", str(config),
                            "--gerenciado", str(gerenciado)]) == 0
    saida = capsys.readouterr().out
    assert "skill" in saida and "usuario" in saida and "falhas: 0" in saida
    assert "skill-projeto" not in saida            # nomes só com --nomes
