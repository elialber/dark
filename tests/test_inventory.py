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
from dark.inventory import Inventory

FIXTURES = Path(__file__).parent / "fixtures" / "inventario"
SRC = Path(__file__).parent.parent / "src"

SECRETS = [
    "valor-secreto-hook", "valor-secreto-cabecalho-hook",
    "valor-secreto-mcp-projeto", "valor-secreto-cabecalho-mcp",
    "valor-secreto-usuario", "valor-secreto-local", "valor-secreto-manifesto",
    "valor-secreto-env-settings", "valor-secreto-credencial",
    "pessoa@exemplo.invalid",
]


def _real_name(name: str) -> str:
    if name.startswith("dot-"):
        name = "." + name[4:]
    return name.removesuffix(".fixture")


def _copy(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / _real_name(item.name)
        if item.is_dir():
            _copy(item, target)
        else:
            shutil.copyfile(item, target)


def mount(case: str, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Copia o caso para tmp_path; devolve (repo, config, gerenciado)."""
    base = tmp_path / case
    _copy(FIXTURES / case, base)
    repo, config, managed = base / "repo", base / "config", base / "gerenciado"
    for d in (repo, config, managed):
        d.mkdir(exist_ok=True)
    for fpath in base.rglob("*.json"):
        text = fpath.read_text(encoding="utf-8")
        fpath.write_text(text.replace("{REPO}", str(repo)).replace("{CONFIG}", str(config)),
                       encoding="utf-8")
    memory = config / "projects" / "MEMORIA"
    if memory.exists():
        memory.rename(config / "projects" / inventory.project_dir(repo))
    return repo, config, managed


def take_inventory(case: str, tmp_path: Path) -> Inventory:
    repo, config, managed = mount(case, tmp_path)
    return inventory.take_inventory(repo, config, managed=managed, environment={})


@pytest.fixture(scope="module")
def complete(tmp_path_factory):
    return take_inventory("completo", tmp_path_factory.mktemp("inv"))


def _single(inv: Inventory, kind: str, name: str):
    found = [p for p in inv.items if p.kind == kind and p.name == name]
    assert len(found) == 1, (kind, name, [(p.kind, p.name) for p in inv.items])
    return found[0]


# --- uma peça de cada tipo, em cada escopo ---------------------------------------

EXPECTED = [
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


@pytest.mark.parametrize("kind,name,scope,plugin,local,on_demand", EXPECTED)
def test_peca_de_cada_tipo_em_cada_escopo(complete, kind, name, scope, plugin, local,
                                          on_demand):
    found = [p for p in complete.items
               if p.kind == kind and p.name == name and p.scope == scope]
    assert len(found) == 1, [(p.kind, p.name, p.scope) for p in complete.items]
    p = found[0]
    assert (p.plugin, p.local, p.on_demand) == (plugin, local, on_demand)
    assert p.source.is_file()
    text = p.source.read_text(encoding="utf-8")
    if kind in ("instrucao", "skill", "subagente"):
        assert p.chars == len(text)
        assert p.lines == len(text.splitlines())
    assert p.chars > 0 and p.lines > 0


def test_hooks_de_cada_escopo(complete):
    hooks = {(h.scope, h.local, h.hook.event): h for h in complete.items if h.kind == "hook"}
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
    assert (pre.matcher, pre.kind) == ("Bash", "command")
    assert pre.command == "TOKEN_PROJETO=*** ./verifica.sh"
    assert pre.variables == ["TOKEN_PROJETO"]
    pos = hooks[("projeto", True, "PostToolUse")].hook
    assert (pos.matcher, pos.command) == ("Edit|Write", "./formata.sh")
    stop = hooks[("projeto", False, "Stop")].hook
    assert (stop.matcher, stop.kind, stop.command) == (None, "http", "http://localhost:9/aviso")
    assert stop.headers == ["Authorization"] and stop.variables == ["CHAVE_AVISO"]
    plugin = hooks[("plugin", False, "PreToolUse")]
    assert plugin.plugin == "plugin-exemplo"
    assert plugin.hook.command == "${CLAUDE_PLUGIN_ROOT}/bin/checa"
    assert hooks[("gerenciado", False, "UserPromptSubmit")].hook.kind == "prompt"
    header = hooks[("usuario", False, None)]
    assert header.name == "skill-com-hook" and header.hook.parsed is False


def test_permissoes_de_cada_escopo(complete):
    perms = {(p.scope, p.local, p.source.name): p.permissions
             for p in complete.items if p.kind == "permissao"}
    assert set(perms) == {
        ("gerenciado", False, "managed-settings.json"),
        ("gerenciado", False, "10-extra.json"),
        ("usuario", False, "settings.json"),
        ("projeto", False, "settings.json"),
        ("projeto", True, "settings.local.json"),
    }
    proj = perms[("projeto", False, "settings.json")]
    assert (proj.default_mode, proj.allow, proj.deny, proj.ask) == ("acceptEdits", 2, 1, 1)
    local = perms[("projeto", True, "settings.local.json")]
    assert (local.default_mode, local.allow, local.deny, local.ask) == (None, 1, 0, 0)
    assert perms[("usuario", False, "settings.json")].default_mode == "plan"
    assert perms[("gerenciado", False, "10-extra.json")].ask == 1


# --- instruções ----------------------------------------------------------------------

def test_instrucao_conta_itens_e_motivos(complete):
    i = next(p for p in complete.items
             if p.kind == "instrucao" and p.name == "CLAUDE.md" and p.scope == "projeto")
    d = i.instruction
    assert d.item_count == 6                 # 4 com marcador, 2 numerados; bloco de código fora
    assert d.with_reason == 3            # "Motivo:", "porque", "para que"
    assert d.estimated_reason is True
    assert d.imports == ["docs/importado.md"]


def test_instrucao_sem_motivo(complete):
    i = next(p for p in complete.items if p.name == "CLAUDE.local.md")
    assert (i.instruction.item_count, i.instruction.with_reason) == (1, 0)


def test_importacoes_seguem_ate_quatro_saltos(complete):
    names = {p.name for p in complete.items if p.kind == "instrucao"}
    assert {"@docs/importado.md", "@docs/nivel2.md", "@docs/nivel3.md",
            "@docs/nivel4.md"} <= names
    assert "@docs/nivel5.md" not in names
    assert not any("nao-importado" in n or "tambem-nao" in n for n in names)
    imp = _single(complete, "instrucao", "@docs/importado.md")
    assert imp.instruction.imported_by.name == "CLAUDE.md"
    assert (imp.instruction.item_count, imp.instruction.with_reason) == (2, 1)


def test_memoria_de_topico_e_claude_md_de_plugin_ficam_fora(complete):
    provenances = {p.source.name for p in complete.items}
    assert "exemplo.md" not in provenances
    assert not any(p.kind == "instrucao" and p.scope == "plugin" for p in complete.items)


# --- skills e subagentes ----------------------------------------------------------------

def test_skill_com_descricao_curta_e_corpo_longo(complete):
    s = _single(complete, "skill", "skill-projeto")
    assert s.description.chars == len("Faz uma coisa curta.")
    assert s.description.body_chars > 2000
    assert s.description.body_lines > 40
    assert s.description.body_chars + s.description.chars < s.chars


def test_descricao_em_bloco_dobrado_e_entre_aspas(complete):
    a = _single(complete, "subagente", "agente-projeto")
    assert a.description.chars == len("Revisa mudanças de exemplo em duas linhas.")
    s = _single(complete, "skill", "skill-usuario")
    assert s.description.chars == len("Skill pessoal de exemplo.")
    assert s.description.model_invocable is False
    assert _single(complete, "skill", "comando-usuario").description.chars == 0


def test_plugins_inativos_nao_entram_mas_sao_relatados(complete):
    assert not any("inativa" in p.name for p in complete.items)
    state = {p.name: p.active for p in complete.plugins}
    assert state == {"plugin-exemplo@mercado-exemplo": True,
                      "plugin-desligado@mercado-exemplo": False,
                      "plugin-outro-projeto@mercado-exemplo": False}


# --- servidores MCP e segredos -------------------------------------------------------

def test_servidor_mcp_guarda_transporte_e_nomes_de_variaveis(complete):
    m = {p.name: p.mcp for p in complete.items if p.kind == "mcp"}
    assert m["servidor-projeto"].transport == "stdio"
    assert m["servidor-projeto"].variables == ["CHAVE_PROJETO"]
    assert m["servidor-remoto"].transport == "http"
    assert m["servidor-remoto"].headers == ["Authorization"]
    assert m["servidor-usuario"].transport == "sse"
    assert m["servidor-plugin"].transport == "ws"
    assert m["servidor-local"].variables == ["CHAVE_LOCAL"]
    assert "servidor-de-outro-projeto" not in m


def test_nenhum_valor_secreto_aparece_no_resultado(complete):
    everything = repr(complete) + json.dumps(inventory.as_dict(complete), ensure_ascii=False)
    for secret in SECRETS:
        assert secret not in everything, secret


def test_arquivo_de_credenciais_nunca_e_aberto(tmp_path, monkeypatch):
    repo, config, managed = mount("completo", tmp_path)
    opened = []
    original = Path.read_text

    def spy(self, *a, **k):
        opened.append(self.name)
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy)
    inventory.take_inventory(repo, config, managed=managed, environment={})
    assert opened and ".credentials.json" not in opened


# --- falhas, vazio, somente leitura ---------------------------------------------------

def test_configuracao_malformada_relata_e_segue(tmp_path):
    inv = take_inventory("quebrado", tmp_path)
    failures = {(f.file.name, f.file.parent.name) for f in inv.failures}
    assert ("settings.json", ".claude") in failures        # projeto, JSON cortado
    assert ("settings.json", "config") in failures         # usuário, não é JSON
    assert (".claude.json", "config") in failures
    assert (".mcp.json", "repo") in failures               # mcpServers não é objeto
    assert ("SKILL.md", "skill-sem-fim") in failures
    assert ("installed_plugins.json", "plugins") in failures   # pasta do plugin ausente
    assert any(f.file.name == "nao-existe.md" for f in inv.failures)
    assert all(f.message for f in inv.failures)
    names = {p.name for p in inv.items}
    assert {"skill-boa", "agente-bom", "CLAUDE.md"} <= names


def test_repositorio_sem_harness(tmp_path):
    inv = take_inventory("vazio", tmp_path)
    assert inv.items == [] and inv.failures == [] and inv.plugins == []


def _snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.stat().st_mtime_ns, p.read_bytes())
            for p in root.rglob("*") if p.is_file()}


def test_somente_leitura(tmp_path):
    repo, config, managed = mount("completo", tmp_path)
    before = _snapshot(tmp_path)
    inventory.take_inventory(repo, config, managed=managed, environment={})
    assert _snapshot(tmp_path) == before


# --- entradas injetáveis -----------------------------------------------------------------

def test_diretorio_de_configuracao_respeita_variavel(tmp_path):
    assert inventory.config_dir({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path
    assert inventory.config_dir({}) == Path.home() / ".claude"


def test_config_padrao_vem_do_ambiente(tmp_path):
    repo, config, managed = mount("completo", tmp_path)
    inv = inventory.take_inventory(repo, managed=managed,
                                 environment={"CLAUDE_CONFIG_DIR": str(config)})
    assert any(p.name == "skill-usuario" for p in inv.items)


def test_claude_json_fica_ao_lado_da_pasta_padrao(tmp_path):
    home_dir = tmp_path / "casa"
    (home_dir / ".claude").mkdir(parents=True)
    (home_dir / ".claude.json").write_text('{"mcpServers": {"servidor-ao-lado": {"command": "x"}}}',
                                       encoding="utf-8")
    empty = tmp_path / "repo"
    empty.mkdir()
    inv = inventory.take_inventory(empty, home_dir / ".claude", managed=tmp_path / "nada",
                                 environment={})
    assert [p.name for p in inv.items] == ["servidor-ao-lado"]


def test_pasta_de_projeto_codifica_o_caminho():
    assert inventory.project_dir(Path("/mnt/c/Repos/Ex_1")) == "-mnt-c-Repos-Ex-1"


def test_nao_importa_o_leitor():
    code = ("import sys; import dark.inventory; "
              "sys.exit(1 if 'dark.reader' in sys.modules else 0)")
    r = subprocess.run([sys.executable, "-c", code], env={**os.environ, "PYTHONPATH": str(SRC)})
    assert r.returncode == 0


def test_pecas_sao_dataclasses_congeladas(complete):
    p = complete.items[0]
    assert dataclasses.is_dataclass(p)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.name = "outro"


# --- comando mínimo -----------------------------------------------------------------------

def test_comando_imprime_contagens(tmp_path, capsys):
    repo, config, managed = mount("completo", tmp_path)
    assert inventory.main([str(repo), "--config", str(config),
                            "--gerenciado", str(managed)]) == 0
    output = capsys.readouterr().out
    assert "skill" in output and "usuario" in output and "falhas: 0" in output
    assert "skill-projeto" not in output            # nomes só com --nomes
