"""Goal 048: a .gitignore line stays while what it ignores exists, and no
``[aplicado]`` label when a conflict means nothing was applied."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from dark import cli
from dark.scaffold import AppendLine, Check, CreateFile, Module, Plan, register, unregister
from dark.scaffold.engine import MANIFEST_NAME, ignored_path, load_manifest

ENV = ".dark/langfuse/.env"
ENV_EXAMPLE = ".dark/langfuse/env.exemplo"


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
    return path


def run(capsys, *argv):
    capsys.readouterr()
    code = cli.main(list(argv))
    c = capsys.readouterr()
    return code, c.out, c.err


def git_ignored(repo: Path, rel: str) -> bool:
    r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", rel])
    return r.returncode == 0


def status(repo: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(repo), "status", "--short", "--ignored",
                        "--untracked-files=all"], capture_output=True, text=True, check=True)
    return r.stdout.splitlines()


# ---------------------------------------------------------- defect 1


def test_langfuse_env_keeps_its_gitignore_line_until_deleted(repo, capsys):
    before = snapshot(repo)
    assert run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")[0] == 0
    (repo / ENV).write_bytes((repo / ENV_EXAMPLE).read_bytes())

    code, out, _ = run(capsys, "remover", "langfuse", str(repo))
    assert code == 1
    assert f"[mantido] linha '{ENV}' em .gitignore" in out
    assert f"{ENV} ainda existe" in out and "dark remover" in out
    assert "Reversão parcial" in out
    assert git_ignored(repo, ENV)
    assert f"!! {ENV}" in status(repo)
    assert f"?? {ENV}" not in status(repo)
    entries = load_manifest(repo)["entries"]
    assert [e["op"]["op"] for e in entries] == ["append_line"]
    assert (repo / ENV).exists()

    (repo / ENV).unlink()
    code, out, _ = run(capsys, "remover", "langfuse", str(repo))
    assert code == 0 and "Módulo revertido." in out
    assert snapshot(repo) == before
    assert not (repo / MANIFEST_NAME).exists()


def test_graphify_output_keeps_its_gitignore_line_until_deleted(repo, capsys):
    before = snapshot(repo)
    assert run(capsys, "adicionar", "graphify", str(repo), "--aplicar")[0] == 0
    (repo / "graphify-out").mkdir()
    (repo / "graphify-out/graph.json").write_text("{}\n")

    code, out, _ = run(capsys, "remover", "graphify", str(repo))
    assert code == 1
    assert "[mantido] linha 'graphify-out/' em .gitignore" in out
    assert git_ignored(repo, "graphify-out/graph.json")
    assert "!! graphify-out/graph.json" in status(repo)

    (repo / "graphify-out/graph.json").unlink()
    (repo / "graphify-out").rmdir()
    code, out, _ = run(capsys, "remover", "graphify", str(repo))
    assert code == 0
    assert snapshot(repo) == before


def test_langfuse_without_env_reverts_fully(repo, capsys):
    before = snapshot(repo)
    assert run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")[0] == 0
    code, out, _ = run(capsys, "remover", "langfuse", str(repo))
    assert code == 0 and "[mantido]" not in out and "Módulo revertido." in out
    assert f"[revertido] linha '{ENV}' em .gitignore" in out
    assert snapshot(repo) == before


def test_line_kept_in_a_gitignore_the_user_already_had(repo, capsys):
    (repo / ".gitignore").write_bytes(b"*.log\r\nbuild/\r\n")
    before = snapshot(repo)
    assert run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")[0] == 0
    (repo / ENV).write_text("X=1\n")
    assert run(capsys, "remover", "langfuse", str(repo))[0] == 1
    assert (repo / ".gitignore").read_bytes() == f"*.log\r\nbuild/\r\n{ENV}\r\n".encode()
    (repo / ENV).unlink()
    assert run(capsys, "remover", "langfuse", str(repo))[0] == 0
    assert snapshot(repo) == before


class Globbing(Module):
    name = "globbing"
    version = "0.1.0"
    indicator = "freshness"

    def plan(self, repo):
        return Plan(self.name, self.version, (
            CreateFile("cache/README.txt", "cache\n"),
            AppendLine(".gitignore", "cache/*.tmp"),
            AppendLine(".gitignore", "/literal.txt")))

    def verify(self, repo):
        return Check(True)


@pytest.fixture
def globbing():
    register(Globbing)
    yield
    unregister("globbing")


def test_glob_line_is_reverted_even_with_a_matching_file(repo, capsys, globbing):
    assert run(capsys, "adicionar", "globbing", str(repo), "--aplicar")[0] == 0
    (repo / "cache/a.tmp").write_text("x\n")
    code, out, _ = run(capsys, "remover", "globbing", str(repo))
    assert code == 0
    assert "[revertido] linha 'cache/*.tmp' em .gitignore" in out
    assert "[revertido] linha '/literal.txt' em .gitignore" in out
    assert not (repo / ".gitignore").exists()
    assert (repo / "cache/a.tmp").exists()


def test_anchored_literal_line_is_kept(repo, capsys, globbing):
    assert run(capsys, "adicionar", "globbing", str(repo), "--aplicar")[0] == 0
    (repo / "literal.txt").write_text("x\n")
    code, out, _ = run(capsys, "remover", "globbing", str(repo))
    assert code == 1
    assert "[mantido] linha '/literal.txt' em .gitignore" in out
    assert "[revertido] linha 'cache/*.tmp' em .gitignore" in out
    assert (repo / ".gitignore").read_text() == "/literal.txt\n"


@pytest.mark.parametrize("rel,line,expected", [
    (".gitignore", ".dark/langfuse/.env", ".dark/langfuse/.env"),
    (".gitignore", "graphify-out/", "graphify-out"),
    (".gitignore", "/build", "build"),
    ("sub/.gitignore", "out/", "sub/out"),
    (".gitignore", "*.log", None),
    (".gitignore", "a?b", None),
    (".gitignore", "[ab]", None),
    (".gitignore", "!keep", None),
    (".gitignore", "# comment", None),
    (".gitignore", "a\\ b", None),
    (".gitignore", "../up", None),
    (".gitignore", "/", None),
    ("notes.txt", "build", None),
])
def test_ignored_path(rel, line, expected):
    assert ignored_path(rel, line) == expected


# ---------------------------------------------------------- defect 2


def _graphify_conflict(repo: Path) -> None:
    (repo / ".claude").mkdir()
    (repo / ".claude/settings.json").write_text(
        json.dumps({"hooks": {"PreToolUse": {}}}, indent=2) + "\n")


def _langfuse_conflict(repo: Path) -> None:
    (repo / ".claude").mkdir()
    (repo / ".claude/settings.json").write_text(
        json.dumps({"enabledPlugins": []}, indent=2) + "\n")


@pytest.mark.parametrize("module,setup", [("graphify", _graphify_conflict),
                                          ("langfuse", _langfuse_conflict)])
def test_conflict_never_labels_anything_applied(repo, capsys, module, setup):
    setup(repo)
    before = snapshot(repo)
    code, out, _ = run(capsys, "adicionar", module, str(repo), "--aplicar")
    assert code == 1
    assert "[conflito]" in out
    assert "[aplicado]" not in out
    assert "[criar]" in out
    assert "Há conflitos: nada foi aplicado." in out
    assert snapshot(repo) == before


def test_without_conflict_apply_still_labels_applied(repo, capsys):
    code, out, _ = run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    assert code == 0 and "[aplicado]" in out and "[criar]" not in out


def test_iniciar_conflict_never_labels_anything_applied(repo, capsys):
    (repo / "evals").write_text("not a directory\n")
    before = snapshot(repo)
    code, out, _ = run(capsys, "iniciar", str(repo), "--aplicar")
    assert code == 1 and "[conflito]" in out and "[aplicado]" not in out
    assert snapshot(repo) == before


def test_scaffold_command_conflict_never_labels_anything_applied(repo, tmp_path, capsys):
    from dark.scaffold import cli as scaffold_cli
    (repo / "taken.txt").write_text("mine\n")
    plan = Plan("t", "1.0.0", (CreateFile("new.txt", "a\n"), CreateFile("taken.txt", "b\n")))
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan.to_dict()))
    capsys.readouterr()
    code = scaffold_cli.main(["aplicar", str(plan_file), "--repositorio", str(repo)])
    out = capsys.readouterr().out
    assert code == 1 and "[aplicado]" not in out and "[aplicar] arquivo new.txt" in out
