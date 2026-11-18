"""Goal 042: module registry, `dark adicionar`, `dark verificar`, round trip."""

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from dark import cli
from dark.scaffold import (AppendLine, Check, CreateFile, Module, Plan, get_module,
                           list_modules, load_manifest, register, unregister)


class Fake(Module):
    name = "fake"
    version = "0.1.0"
    indicator = "freshness"
    reasons = {"fake/note.txt": "arquivo de teste"}

    def plan(self, repo):
        return Plan(self.name, self.version, (
            CreateFile("fake/note.txt", "hello\n"), AppendLine(".gitignore", "fake/cache")))

    def verify(self, repo):
        applied = any(e.get("module") == self.name for e in load_manifest(repo)["entries"])
        if not applied:
            return Check(False, "o módulo não foi aplicado")
        if not (Path(repo) / "fake/note.txt").exists():
            return Check(False, "ausente: fake/note.txt")
        return Check(True)


@pytest.fixture(autouse=True)
def fake_registered():
    register(Fake)
    yield
    unregister("fake")


def snapshot(root: Path) -> dict:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for d in dirnames:
            out[os.path.relpath(os.path.join(dirpath, d), root)] = None
        for f in filenames:
            p = os.path.join(dirpath, f)
            out[os.path.relpath(p, root)] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return out


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / ".gitignore").write_bytes(b"*.log")      # no final newline
    return path


def run(capsys, *argv):
    capsys.readouterr()
    code = cli.main(list(argv))
    c = capsys.readouterr()
    return code, c.out, c.err


def test_registry_has_only_base_by_default():
    unregister("fake")
    assert "base" in [m.name for m in list_modules()]
    assert get_module("fake") is None
    register(Fake)
    assert get_module("fake").version == "0.1.0"


def test_register_refuses_a_different_module_with_the_same_name():
    class Other(Fake):
        pass
    with pytest.raises(ValueError):
        register(Other)


def test_round_trip_restores_every_byte(repo, capsys):
    before = snapshot(repo)
    assert run(capsys, "adicionar", "fake", str(repo))[0] == 0
    assert snapshot(repo) == before                      # plan writes nothing
    code, out, _ = run(capsys, "adicionar", "fake", str(repo), "--aplicar")
    assert code == 0 and "dark remover fake" in out
    assert (repo / "fake/note.txt").read_text() == "hello\n"
    assert run(capsys, "verificar", "fake", str(repo)) == (0, "ok\n", "")
    code, out, _ = run(capsys, "remover", "fake", str(repo))
    assert code == 0
    assert snapshot(repo) == before


def test_apply_twice_is_a_no_op(repo, capsys):
    run(capsys, "adicionar", "fake", str(repo), "--aplicar")
    after = snapshot(repo)
    code, out, _ = run(capsys, "adicionar", "fake", str(repo), "--aplicar")
    assert code == 0 and "Nada a fazer: já aplicado." in out
    assert snapshot(repo) == after


@pytest.mark.parametrize("name", ["", "../x", "nope"])
def test_unknown_module_is_exit_2_with_the_known_ones(repo, capsys, name):
    code, out, err = run(capsys, "adicionar", name, str(repo))
    assert code == 2 and "módulo desconhecido" in err and "base, fake" in err
    assert "Traceback" not in err


def test_not_a_repository_root_is_exit_2(tmp_path, repo, capsys):
    sub = repo / "sub"
    sub.mkdir()
    assert run(capsys, "adicionar", "fake", str(sub))[0] == 2
    assert run(capsys, "verificar", "fake", str(sub))[0] == 2
    assert run(capsys, "verificar", "nope", str(repo))[0] == 2


def test_conflict_aborts_and_writes_nothing(repo, capsys):
    (repo / "fake").mkdir()
    (repo / "fake/note.txt").write_text("mine\n")
    before = snapshot(repo)
    code, out, _ = run(capsys, "adicionar", "fake", str(repo), "--aplicar")
    assert code == 1 and "conflito" in out
    assert snapshot(repo) == before


def test_verify_never_applied_is_exit_1(repo, capsys):
    code, out, _ = run(capsys, "verificar", "fake", str(repo))
    assert (code, out) == (1, "o módulo não foi aplicado\n")


def test_verify_reports_a_missing_file(repo, capsys):
    run(capsys, "adicionar", "fake", str(repo), "--aplicar")
    (repo / "fake/note.txt").unlink()
    code, out, _ = run(capsys, "verificar", "fake", str(repo))
    assert (code, out) == (1, "ausente: fake/note.txt\n")


def test_remove_after_user_edit_keeps_the_edit(repo, capsys):
    run(capsys, "adicionar", "fake", str(repo), "--aplicar")
    (repo / "fake/note.txt").write_text("edited\n")
    code, out, err = run(capsys, "remover", "fake", str(repo))
    assert code == 1 and "Traceback" not in err
    assert (repo / "fake/note.txt").read_text() == "edited\n"


def test_list_before_and_after(repo, capsys):
    code, out, _ = run(capsys, "adicionar", "--listar", str(repo))
    assert code == 0
    assert "base 1.0.0  indicador: adherence  não aplicado" in out
    assert "fake 0.1.0  indicador: freshness  não aplicado" in out
    run(capsys, "adicionar", "fake", str(repo), "--aplicar")
    out = run(capsys, "adicionar", "--listar", str(repo))[1]
    assert "fake 0.1.0  indicador: freshness  aplicado" in out
    assert "base 1.0.0  indicador: adherence  não aplicado" in out


def test_adicionar_base_matches_iniciar(tmp_path, capsys):
    outs = []
    for cmd in (("iniciar",), ("adicionar", "base")):
        r = tmp_path / "-".join(cmd)
        r.mkdir()
        subprocess.run(["git", "init", "-q", str(r)], check=True)
        plan = run(capsys, *cmd, str(r))
        applied = run(capsys, *cmd, str(r), "--aplicar")
        outs.append([(c, o.replace(str(r), "R"), e) for c, o, e in (plan, applied)])
    # only the command name inside messages may differ; the success output is the same
    assert outs[0] == outs[1]
