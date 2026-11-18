"""Portability fixes (goal 019): Windows, macOS and Linux.

Each test names the item of docs/portabilidade.md it guards. The tests run
on every system: the Windows branches are exercised by injecting the system
or the executables, so that a Linux or macOS run also checks them.
"""

from __future__ import annotations

import ast
import dataclasses
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath

import pytest

from dark import audit, cli, context_usage, indicators, inventory, reader, report
from dark.evals import __main__ as evals_main
from dark.evals import process, validation
from dark.inventory import HarnessItem, Inventory
from dark.scaffold import cli as scaffold_cli

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "dark"
TOOLS = ROOT / "tools"
FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = FIXTURES / "config"


# ==========================================================================
# S6.5: every process output read as text is decoded as UTF-8
# ==========================================================================

_PROCESS_CALLS = {"run", "Popen", "check_output", "check_call", "call"}


def _text_mode_calls_without_encoding() -> list[str]:
    found = []
    for path in sorted([*SRC.rglob("*.py"), *TOOLS.rglob("*.py")]):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in _PROCESS_CALLS
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            # Any value but a literal False may turn text mode on: `text=True`,
            # and also `text=not binary` (goal 053, `evals/workspace.git`).
            text_mode = any(k in kw and not (isinstance(kw[k], ast.Constant)
                                             and kw[k].value in (False, None))
                            for k in ("text", "universal_newlines"))
            if text_mode and "encoding" not in kw:
                found.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
    return found


def test_process_output_is_never_decoded_with_the_locale():
    """`text=True` without `encoding` uses the locale (cp1252 on Windows).

    Covers `src/dark` and `tools/` (batch 009).
    """
    assert _text_mode_calls_without_encoding() == []


def test_evals_git_decodes_utf8_whatever_the_locale(monkeypatch):
    from dark.evals import git as evals_git
    seen = {}

    def fake_run(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "Corrige o cálculo\n", "")

    monkeypatch.setattr(evals_git.subprocess, "run", fake_run)
    assert evals_git.default_executor(["git", "log"], Path(".")) == "Corrige o cálculo\n"
    assert seen.get("encoding") == "utf-8"


def test_workspace_git_reads_accented_names_whatever_the_locale(tmp_path, monkeypatch):
    """S6.8: the eval copy keeps a harness file with an accented name.

    Simulates Windows: text read without `encoding` is decoded as cp1252.
    """
    from dark.evals import workspace
    real_run = subprocess.run

    def cp1252_run(argv, **kwargs):
        if kwargs.get("text") and not kwargs.get("encoding"):
            kwargs = {**kwargs, "text": False}
            r = real_run(argv, **kwargs)
            return subprocess.CompletedProcess(r.args, r.returncode,
                                               r.stdout.decode("cp1252"),
                                               r.stderr.decode("cp1252"))
        return real_run(argv, **kwargs)

    env = {"GIT_AUTHOR_NAME": "Teste", "GIT_AUTHOR_EMAIL": "teste@exemplo.invalid",
           "GIT_COMMITTER_NAME": "Teste", "GIT_COMMITTER_EMAIL": "teste@exemplo.invalid",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    src = tmp_path / "src"
    skill = src / ".claude" / "skills" / "revisão" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: revisão\n---\n", encoding="utf-8")
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")

    def git(*args):
        return real_run(["git", *args], cwd=src, check=True, capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()

    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    monkeypatch.setattr(workspace.subprocess, "run", cp1252_run)
    copy = tmp_path / "copy"
    workspace.prepare_copy(src, base, copy, None)  # bare: removes the harness
    assert not (copy / skill.relative_to(src)).exists()
    assert (copy / "a.py").is_file()


def test_cli_git_decodes_utf8_whatever_the_locale(monkeypatch):
    seen = {}

    def fake_run(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    cli._git("--version")
    assert seen.get("encoding") == "utf-8"


# ==========================================================================
# S6.6: the commands write UTF-8 even when the output is not a UTF-8 terminal
# ==========================================================================

def _cp1252_streams(monkeypatch):
    """Standard output and error as Windows gives them when redirected."""
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    out, err = io.BytesIO(), io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, encoding="cp1252"))
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(err, encoding="cp1252"))
    return out, err


def _scaffold_plan(tmp_path: Path) -> Path:
    plan = {"module": "módulo-exemplo", "version": "1.0.0", "operations": [
        {"op": "create_file", "path": "notas/ação.md", "content": "olá → mundo\n"}]}
    path = tmp_path / "plano.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _invalid_case(tmp_path: Path) -> Path:
    path = tmp_path / "caso.toml"
    path.write_text('id = "caso-ação"\n', encoding="utf-8")
    return path


COMMANDS = {
    "dark auditar": lambda tmp: cli.main(["auditar", "--todos", "--config", str(CONFIG),
                                          "--sem-git"]),
    "dark.reader": lambda tmp: reader.main(["--config", str(CONFIG)]),
    "dark.indicators": lambda tmp: indicators.main(["--config", str(CONFIG), "--nomes"]),
    "dark.inventory": lambda tmp: inventory.main([str(tmp), "--config", str(tmp),
                                                  "--gerenciado", str(tmp)]),
    "dark.context_usage": lambda tmp: context_usage.main(
        ["--arquivo", str(FIXTURES / "context" / "complete.md"), "--usage", "50000"]),
    "dark.evals": lambda tmp: evals_main.main(["validar", "--repo", str(tmp),
                                               str(_invalid_case(tmp))]),
    "dark.scaffold": lambda tmp: scaffold_cli.main(["inspecionar", str(_scaffold_plan(tmp)),
                                                    "--repositorio", str(tmp)]),
}


@pytest.mark.parametrize("name", COMMANDS)
def test_command_output_is_utf8_on_a_non_utf8_stream(name, tmp_path, monkeypatch, capsys):
    run = COMMANDS[name]
    try:
        expected_code = run(tmp_path)
    except (FileNotFoundError, OSError):
        expected_code = "error"
    expected = capsys.readouterr()

    out, err = _cp1252_streams(monkeypatch)
    try:
        code = run(tmp_path)
    except (FileNotFoundError, OSError):
        code = "error"
    sys.stdout.flush()
    sys.stderr.flush()
    assert code == expected_code
    # A text stream writes "\r\n" on Windows; capsys does not translate.
    assert out.getvalue().decode("utf-8").replace("\r\n", "\n") == expected.out
    assert err.getvalue().decode("utf-8").replace("\r\n", "\n") == expected.err


def test_report_with_arrow_goes_through_redirected_output(monkeypatch):
    out, _ = _cp1252_streams(monkeypatch)
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG), "--sem-git"]) == 0
    sys.stdout.flush()
    assert "→" in out.getvalue().decode("utf-8")


def test_explicit_pythonioencoding_is_respected(monkeypatch):
    from dark import console
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    console.utf8_output(stream)
    assert stream.encoding == "cp1252"


def test_utf8_stream_is_left_alone(monkeypatch):
    from dark import console
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="surrogateescape")
    console.utf8_output(stream)
    assert (stream.encoding, stream.errors) == ("utf-8", "surrogateescape")


def test_command_run_as_process_with_cp1252_output(tmp_path):
    """The real thing: `python -m dark auditar` with the output in a pipe."""
    env = {k: v for k, v in __import__("os").environ.items()
           if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    env.update(PYTHONIOENCODING="", PYTHONUTF8="0",
               PYTHONPATH=str(ROOT / "src"))
    # A child that starts with stdout in cp1252, as Windows does when redirected.
    code = ("import io, sys; "
            "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='cp1252'); "
            "from dark.cli import main; "
            f"sys.exit(main(['auditar', '--todos', '--config', {str(CONFIG)!r}, '--sem-git']))")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert "→" in r.stdout.decode("utf-8")


# ==========================================================================
# S5.2: timeout ends the whole process tree, on Windows too
# ==========================================================================

def test_spawn_options_by_system(monkeypatch):
    monkeypatch.setattr(process, "IS_WINDOWS", False)
    assert process._popen_kwargs() == {"start_new_session": True}
    monkeypatch.setattr(process, "IS_WINDOWS", True)
    windows = process._popen_kwargs()
    assert "start_new_session" not in windows
    assert windows["creationflags"] == 0x00000200      # CREATE_NEW_PROCESS_GROUP


class _FakeProc:
    pid = 4321

    def __init__(self):
        self.killed = False

    def kill(self):
        self.killed = True

    def poll(self):
        return None if not self.killed else -9

    def wait(self, timeout=None):
        return -9


def test_windows_kill_ends_the_tree_with_taskkill(monkeypatch):
    calls = []
    monkeypatch.setattr(process, "IS_WINDOWS", True)
    monkeypatch.setattr(process.subprocess, "run", lambda argv, **kw: calls.append(argv) or
                        subprocess.CompletedProcess(argv, 0))
    proc = _FakeProc()
    process.kill_tree(proc)
    assert calls == [["taskkill", "/PID", "4321", "/T", "/F"]]
    assert proc.killed                # and the direct child, in case taskkill failed


def test_windows_kill_without_taskkill_still_kills_the_child(monkeypatch):
    def missing(argv, **kw):
        raise FileNotFoundError("taskkill")
    monkeypatch.setattr(process, "IS_WINDOWS", True)
    monkeypatch.setattr(process.subprocess, "run", missing)
    proc = _FakeProc()
    process.kill_tree(proc)
    assert proc.killed


def test_validation_ends_processes_with_the_runner_function(monkeypatch, tmp_path):
    """One function ends process trees, on every system (batch 009)."""
    source = Path(validation.__file__).read_text(encoding="utf-8")
    assert "killpg" not in source and "taskkill" not in source
    killed = []
    real = process.kill_tree
    monkeypatch.setattr(process, "kill_tree", lambda proc, *a, **kw: killed.append(proc.pid)
                        or real(proc, *a, **kw))
    code, _, timed_out, did_not_run, _ = validation.run_acceptance(
        [sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, 1)
    assert timed_out and code is None and not did_not_run
    assert len(killed) == 1


def test_temporary_directory_that_cannot_be_removed_becomes_a_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(validation, "_remove_dir", lambda path: False)
    res = validation.ValidationResult(case="x", valid=True)
    with validation._temporary_directory(tmp_path, res) as tmp:
        assert Path(tmp).is_dir()
    assert res.cleanup_warning and Path(tmp).name in res.cleanup_warning
    text = validation.describe(res)
    assert "aviso:" in text and "não pôde ser apagado" in text


def test_temporary_directory_is_removed_normally(tmp_path):
    res = validation.ValidationResult(case="x", valid=True)
    with validation._temporary_directory(tmp_path, res) as tmp:
        (Path(tmp) / "f.txt").write_text("x")
    assert not Path(tmp).exists() and res.cleanup_warning == ""
    assert "aviso" not in validation.describe(res)


# ==========================================================================
# S5.1: the acceptance command in text needs `sh`; found or explained
# ==========================================================================

def test_posix_shell_is_sh_from_path():
    assert validation._shell_argv(windows=False, which=lambda name: None) == ["sh", "-c"]


def test_windows_uses_sh_on_path():
    found = {"sh": r"C:\tools\sh.exe"}
    assert validation._shell_argv(windows=True, which=found.get) == [r"C:\tools\sh.exe", "-c"]


def test_windows_finds_the_sh_of_git_for_windows(tmp_path):
    git_dir = tmp_path / "Git"
    (git_dir / "cmd").mkdir(parents=True)
    (git_dir / "bin").mkdir()
    (git_dir / "cmd" / "git.exe").write_text("")
    (git_dir / "bin" / "sh.exe").write_text("")
    found = {"git": str(git_dir / "cmd" / "git.exe")}
    assert validation._shell_argv(windows=True, which=found.get) == [
        str(git_dir / "bin" / "sh.exe"), "-c"]


def test_windows_without_any_sh():
    assert validation._shell_argv(windows=True, which=lambda name: None) is None


def test_missing_shell_says_what_to_install(monkeypatch, tmp_path):
    monkeypatch.setattr(validation, "_shell_argv", lambda **kw: None)
    code, _, timed_out, did_not_run, output = validation.run_acceptance(
        "pytest -q", tmp_path, 10)
    assert code is None and not timed_out and did_not_run
    assert "sh" in output and "Git for Windows" in output and "lista" in output


def test_command_as_list_does_not_need_a_shell(monkeypatch, tmp_path):
    monkeypatch.setattr(validation, "_shell_argv", lambda **kw: None)
    code, _, _, did_not_run, _ = validation.run_acceptance(
        [sys.executable, "-c", "pass"], tmp_path, 30)
    assert code == 0 and not did_not_run


# ==========================================================================
# S2.4: `claude` installed by npm on Windows is `claude.cmd`
# ==========================================================================

def test_context_usage_resolves_the_executable(monkeypatch, tmp_path):
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "texto", "")

    monkeypatch.setattr(context_usage.shutil, "which",
                        lambda name: r"C:\npm\claude.cmd" if name == "claude" else None)
    monkeypatch.setattr(context_usage.subprocess, "run", fake_run)
    assert context_usage._default_executor(list(context_usage.ARGUMENTS), tmp_path) == "texto"
    assert seen["argv"][0] == r"C:\npm\claude.cmd"
    assert seen["argv"][1:] == list(context_usage.ARGUMENTS)[1:]
    assert seen.get("encoding") == "utf-8"


def test_context_usage_keeps_the_name_when_not_found(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(context_usage.shutil, "which", lambda name: None)
    monkeypatch.setattr(context_usage.subprocess, "run",
                        lambda argv, **kw: seen.setdefault("argv", argv) and
                        subprocess.CompletedProcess(argv, 0, "", ""))
    context_usage._default_executor(list(context_usage.ARGUMENTS), tmp_path)
    assert seen["argv"][0] == "claude"


# ==========================================================================
# S1.2: the report writes paths with forward slashes on every system
# ==========================================================================

def test_path_text_uses_forward_slashes():
    assert report.path_text(PureWindowsPath(r"C:\Users\x\repo")) == "C:/Users/x/repo"
    assert report.path_text(PureWindowsPath(r".claude\skills\x\SKILL.md")) == \
        ".claude/skills/x/SKILL.md"
    assert report.path_text(Path("/repo/alpha")) == "/repo/alpha"


def _item(name, scope, source):
    return HarnessItem(kind="skill", scope=scope, name=name, source=source, chars=100, lines=3)


@pytest.fixture(scope="module")
def sessions():
    return reader.read_all(CONFIG).sessions


def test_header_writes_windows_repository_with_forward_slashes(sessions):
    repo = PureWindowsPath(r"C:\Users\x\repo")
    copy = PureWindowsPath(r"D:\copia\repo")
    a = audit.audit(sessions, repository=repo, directories=[repo, copy])
    hdr = report.markdown(a).split("\n## ")[0]
    assert "`C:/Users/x/repo`" in hdr and "`D:/copia/repo`" in hdr
    assert "\\" not in hdr


def test_appendix_writes_item_paths_with_forward_slashes(sessions):
    s6 = [s for s in sessions if s.id.endswith("0006")]
    windows = PureWindowsPath(r".claude\skills\nunca-usada\SKILL.md")
    inv = Inventory(items=[
        _item("nunca-usada", "project", windows),
        _item("escondida", "user",
              PureWindowsPath(r"C:\Users\x\.claude\skills\escondida\SKILL.md"))])
    text = report.markdown(audit.audit(s6, inventory=inv))
    appendix = text.split("## Apêndice")[1]
    assert ".claude/skills/nunca-usada/SKILL.md" in appendix
    assert "C:/Users/x/.claude/skills/escondida/SKILL.md" in appendix
    assert "\\" not in appendix


# ==========================================================================
# S7.2: transcript retention, from the settings, with a warning
# ==========================================================================

def _settings(folder: Path, data: object, name="settings.json") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


def test_retention_not_set(tmp_path):
    assert inventory.cleanup_period_days(tmp_path / "cfg", tmp_path / "managed") is None


def test_retention_from_user_settings(tmp_path):
    _settings(tmp_path / "cfg", {"cleanupPeriodDays": 90})
    assert inventory.cleanup_period_days(tmp_path / "cfg", tmp_path / "managed") == 90


def test_retention_managed_wins(tmp_path):
    _settings(tmp_path / "cfg", {"cleanupPeriodDays": 90})
    _settings(tmp_path / "managed", {"cleanupPeriodDays": 14}, "managed-settings.json")
    assert inventory.cleanup_period_days(tmp_path / "cfg", tmp_path / "managed") == 14


@pytest.mark.parametrize("value", ["90", -1, 0, True, None, 1.5])
def test_retention_invalid_value_is_ignored(tmp_path, value):
    _settings(tmp_path / "cfg", {"cleanupPeriodDays": value})
    assert inventory.cleanup_period_days(tmp_path / "cfg", tmp_path / "managed") is None


def test_retention_unreadable_settings_are_ignored(tmp_path):
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "settings.json").write_text("{não é json", encoding="utf-8")
    assert inventory.cleanup_period_days(tmp_path / "cfg", tmp_path / "managed") is None


NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def _header(sessions, **kw) -> str:
    return report.markdown(audit.audit(sessions, **kw)).split("\n## ")[0]


def test_default_retention_line_is_unchanged(sessions):
    hdr = _header(sessions)
    assert ("- Alcance: a retenção padrão das transcrições é de 30 dias; sessões mais "
            "antigas podem já ter sido apagadas pelo Claude Code.") in hdr


def test_configured_retention_is_shown(sessions):
    hdr = _header(sessions, retention_days=90, retention_start=NOW - timedelta(days=90))
    assert "90 dias" in hdr and "`cleanupPeriodDays`" in hdr
    assert "retenção padrão" not in hdr


def test_window_beyond_retention_is_warned(sessions):
    since = NOW - timedelta(days=90)
    hdr = _header(sessions, since=since, retention_start=NOW - timedelta(days=30))
    line = next(l for l in hdr.splitlines() if "limite de retenção" in l)
    assert line.startswith("- **Aviso:**")
    assert "2026-08-19" in line and "2026-10-18" in line


def test_window_inside_retention_is_not_warned(sessions):
    hdr = _header(sessions, since=NOW - timedelta(days=7),
                  retention_start=NOW - timedelta(days=30))
    assert "limite de retenção" not in hdr


def test_cli_passes_retention_to_the_report(tmp_path, capsys):
    config = tmp_path / "config"
    import shutil
    shutil.copytree(CONFIG, config)
    _settings(config, {"cleanupPeriodDays": 7})
    assert cli.main(["auditar", "--todos", "--config", str(config), "--sem-git",
                     "--gerenciado", str(tmp_path / "managed"), "--dias", "3650"]) in (0, 1)
    hdr = capsys.readouterr().out.split("\n## ")[0]
    assert "7 dias" in hdr and "limite de retenção" in hdr


# ==========================================================================
# S2.1: Claude Code versions outside the tested range
# ==========================================================================

def test_tested_range():
    assert reader.TESTED_VERSIONS == ("2.1.295", "2.1.326")
    assert reader.version_tested("2.1.300") and reader.version_tested("2.1.326")
    assert not reader.version_tested("2.1.294") and not reader.version_tested("2.2.0")
    assert not reader.version_tested("3.0.0")


def test_versions_inside_range_have_no_warning(sessions):
    assert "fora do intervalo testado" not in _header(sessions)


def test_versions_outside_range_are_warned(sessions):
    old = [dataclasses.replace(s, versions=["2.1.274"]) if s.id.endswith("0001") else s
           for s in sessions]
    hdr = _header(old)
    line = next(l for l in hdr.splitlines() if "fora do intervalo testado" in l)
    assert line.startswith("- **Aviso:**")
    assert "1 sessão" in line and "2.1.274" in line and "2.1.295 a 2.1.326" in line


# ==========================================================================
# S3.3: skills counted as built-in only by the rule
# ==========================================================================

def test_builtin_by_rule_is_warned(sessions):
    s6 = [s for s in sessions if s.id.endswith("0006")]
    inv = Inventory(items=[_item("exemplo-skill", "project",
                                 Path(".claude/skills/exemplo-skill/SKILL.md"))])
    a = audit.audit(s6, inventory=inv)
    assert a.builtin_by_rule == ["nunca-usada", "por-comando"]
    hdr = report.markdown(a).split("\n## ")[0]
    line = next(l for l in hdr.splitlines() if "embutidas pela regra" in l)
    assert line.startswith("- **Aviso:**")
    for name in a.builtin_by_rule[:report.FIRST_NAMES]:
        assert f"`{name}`" in line
    assert "O que chama atenção" in line


def test_without_inventory_there_is_no_builtin_warning(sessions):
    assert "embutidas pela regra" not in _header(sessions)
