"""Goal 043: the ``langfuse`` module (self-hosted Langfuse plus the Claude Code plugin)."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from dark import cli
from dark.scaffold import AppendLine, CreateFile, JsonEntry, get_module, list_modules
from dark.scaffold import langfuse

ALL_VARS = (*langfuse.COMPOSE_SECRETS, *langfuse.INTEGRATION_VARS)

# ------------------------------------------------------------ compose checks

_IMAGE = re.compile(r"^\s*image:\s*(\S+)\s*$")
_EXACT_TAG = re.compile(r"\d+(\.\d+)+")
_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}")
# Names that hold a password, a secret or a key. KEY_ID is an identifier.
_SECRET_NAME = re.compile(r"(PASSWORD|SECRET|SALT|ENCRYPTION_KEY|AUTH|_KEY)$")
_REF_DEFAULT = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):?-([^}]*)\}")
_ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*(#.*)?$")


def image_problems(text: str, version: str) -> list[str]:
    """Image lines without an exact tag (or digest); Langfuse's own at ``version``."""
    out = []
    for line in text.splitlines():
        m = _IMAGE.match(line)
        if not m:
            continue
        ref = m.group(1)
        if "$" in ref or "latest" in ref:
            out.append(ref)
            continue
        if _DIGEST.search(ref):
            continue
        name, _, tag = ref.rpartition(":")
        if not name or "/" in tag or not _EXACT_TAG.fullmatch(tag):
            out.append(ref)
        elif "/langfuse/" in name and tag != version:
            out.append(ref)
    return out


def _harmless(value: str) -> bool:
    """A flag or a file path is not a secret (``REDIS_TLS_KEY: /certs/redis.key``)."""
    return value in ("true", "false") or value.startswith("/")


def secret_problems(text: str) -> list[str]:
    """Secrets written out instead of referenced by variable name."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for name, default in _REF_DEFAULT.findall(line):
            if _SECRET_NAME.search(name) and default and not _harmless(default):
                out.append(line.strip())
        m = _ENV_LINE.match(line)
        if m and _SECRET_NAME.search(m.group(1)):
            value = m.group(2).strip("\"'")
            if value and not value.startswith("${") and not _harmless(value):
                out.append(line.strip())
    return out


def test_compose_images_are_pinned_exactly():
    assert image_problems(langfuse.COMPOSE, langfuse.Langfuse.version) == []
    assert len([l for l in langfuse.COMPOSE.splitlines() if _IMAGE.match(l)]) == 7


@pytest.mark.parametrize("image", [
    "langfuse/langfuse:3", "docker.io/redis:7", "docker.io/redis:latest",
    "cgr.dev/chainguard/minio", "langfuse/langfuse:${LANGFUSE_IMAGE_TAG:-4}",
    "docker.langfuse.com/langfuse/langfuse:4.81.0",
])
def test_image_probe_fails_on_loose_tags(image):
    probe = langfuse.COMPOSE + f"\n  probe:\n    image: {image}\n"
    assert image_problems(probe, langfuse.Langfuse.version) == [image]


def test_compose_has_no_secret_written_out():
    assert secret_problems(langfuse.COMPOSE) == []
    for weak in ("mysalt", "mysecret", "miniosecret", "myredissecret", "postgres:postgres@"):
        assert weak not in langfuse.COMPOSE


@pytest.mark.parametrize("line", [
    "      SALT: mysalt",
    "      SALT: ${SALT:-mysalt}",
    "      POSTGRES_PASSWORD: \"postgres\"",
    "      --requirepass ${REDIS_AUTH:-myredissecret}",
])
def test_secret_probe_fails_on_written_values(line):
    probe = langfuse.COMPOSE.replace("services:\n", "services:\n" + line + "\n", 1)
    assert secret_problems(probe) == [line.strip()]


def test_every_required_variable_is_in_the_example_without_value():
    code = "\n".join(l for l in langfuse.COMPOSE.splitlines() if not l.lstrip().startswith("#"))
    required = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*):\?", code))
    assert required == set(langfuse.COMPOSE_SECRETS)
    lines = langfuse.ENV_EXAMPLE.splitlines()
    for name in langfuse.COMPOSE_SECRETS:
        assert f"{name}=" in lines, name
        i = lines.index(f"{name}=")
        assert lines[i - 1].startswith("#") and "openssl rand" in lines[i - 1]
    assert not [l for l in lines if "=" in l and not l.startswith("#") and not l.endswith("=")]


@pytest.mark.parametrize("text", [langfuse.COMPOSE, langfuse.ENV_EXAMPLE])
def test_generated_files_cite_origin_version_and_license(text):
    head = "\n".join(text.splitlines()[:12])
    assert "https://github.com/langfuse/langfuse" in head
    assert "v4.82.0" in head
    assert "MIT" in head


def test_compose_keeps_the_mit_notice():
    assert "Copyright (c) 2023-2026 ClickHouse, Inc." in langfuse.COMPOSE
    assert "Permission is hereby granted, free of charge" in langfuse.COMPOSE


# ------------------------------------------------------------ module and plan


def test_module_is_registered_with_pinned_version():
    module = get_module("langfuse")
    assert module is not None and "langfuse" in [m.name for m in list_modules()]
    assert module.version == "4.82.0"
    assert module.indicator == "cost_per_task"


def test_plan_operations(tmp_path):
    plan = langfuse.Langfuse().plan(tmp_path)
    assert plan.module == "langfuse" and plan.version == "4.82.0"
    ops = plan.operations
    assert CreateFile(".dark/langfuse/docker-compose.yml", langfuse.COMPOSE) in ops
    assert CreateFile(".dark/langfuse/env.exemplo", langfuse.ENV_EXAMPLE) in ops
    assert AppendLine(".gitignore", ".dark/langfuse/.env") in ops
    settings = [op for op in ops if isinstance(op, JsonEntry)]
    assert settings and all(op.path == ".claude/settings.json" for op in settings)
    texts = " ".join(t for op in settings for t in op.texts())
    assert "langfuse-observability@langfuse-observability" in texts
    for name in langfuse.INTEGRATION_VARS:     # keys are never written, not even as names
        assert name not in texts
    assert not list(tmp_path.iterdir())         # plan does not write


def test_plugin_marketplace_is_pinned_to_a_tag(tmp_path):
    ops = langfuse.Langfuse().plan(tmp_path).operations
    market = next(op for op in ops if isinstance(op, JsonEntry)
                  and op.keys == ("extraKnownMarketplaces",))
    assert market.value["source"]["ref"] == langfuse.PLUGIN_VERSION
    assert re.fullmatch(r"v\d+\.\d+\.\d+", langfuse.PLUGIN_VERSION)


# ------------------------------------------------------------ command line


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


@pytest.fixture(autouse=True)
def no_vars(monkeypatch):
    for name in ALL_VARS:
        monkeypatch.delenv(name, raising=False)


def run(capsys, *argv):
    capsys.readouterr()
    code = cli.main(list(argv))
    c = capsys.readouterr()
    return code, c.out, c.err


@pytest.mark.parametrize("user_files", [
    {},
    {".gitignore": b"*.log", ".claude/settings.json": b'{\n  "model": "opus"\n}\n'},
    {".gitignore": b"*.log\r\nbuild/\r\n",
     ".claude/settings.json": b'{"env": {"FOO": "1"}, "enabledPlugins": {"x@y": false}}'},
])
def test_round_trip_leaves_the_tree_byte_identical(repo, capsys, user_files):
    for rel, data in user_files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes(data)
    before = snapshot(repo)
    code, out, err = run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    assert code == 0, out + err
    assert (repo / ".dark/langfuse/docker-compose.yml").read_text(encoding="utf-8") == langfuse.COMPOSE
    settings = json.loads((repo / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"]["langfuse-observability@langfuse-observability"] is True
    assert settings["env"]["LANGFUSE_BASE_URL"] == "http://localhost:3000"
    if b"\r\n" in user_files.get(".gitignore", b""):
        assert (repo / ".gitignore").read_bytes().endswith(b"\r\n.dark/langfuse/.env\r\n")
    code, out, err = run(capsys, "remover", "langfuse", str(repo))
    assert code == 0, out + err
    assert snapshot(repo) == before


def test_add_prints_how_to_start_where_keys_go_and_privacy(repo, capsys):
    code, out, _ = run(capsys, "adicionar", "langfuse", str(repo))
    assert code == 0
    assert ("docker compose -f .dark/langfuse/docker-compose.yml "
            "--env-file .dark/langfuse/.env up -d") in out
    assert "cp .dark/langfuse/env.exemplo .dark/langfuse/.env" in out
    for name in langfuse.INTEGRATION_VARS:
        assert name in out
    assert "conteúdo das conversas" in out and "não guarda" in out
    assert "uv" in out and "langfuse>=4.7,<5" in out
    assert not (repo / ".dark").exists()


def test_add_twice_with_apply(repo, capsys):
    assert run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")[0] == 0
    code, out, _ = run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    assert code == 0 and "Nada a fazer: já aplicado." in out


def test_add_with_invalid_settings_writes_nothing(repo, capsys):
    (repo / ".claude").mkdir()
    (repo / ".claude/settings.json").write_text("{ not json", encoding="utf-8")
    before = snapshot(repo)
    code, out, err = run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    assert code == 1 and "Traceback" not in out + err
    assert "[conflito]" in out
    assert snapshot(repo) == before


def test_engine_refuses_a_secret_value_in_the_content(repo, capsys, monkeypatch):
    monkeypatch.setenv("DARK_PROBE_SECRET", "http://localhost:3000")
    before = snapshot(repo)
    code, out, err = run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    assert code == 1 and "DARK_PROBE_SECRET" in out and "Traceback" not in out + err
    assert snapshot(repo) == before


def test_remove_after_user_edits_the_compose_keeps_it(repo, capsys):
    assert run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")[0] == 0
    compose = repo / ".dark/langfuse/docker-compose.yml"
    compose.write_text(langfuse.COMPOSE + "# mine\n", encoding="utf-8")
    code, out, err = run(capsys, "remover", "langfuse", str(repo))
    assert code == 1 and "Traceback" not in out + err
    assert compose.read_text(encoding="utf-8").endswith("# mine\n")


# ------------------------------------------------------------ verify


def test_verify_before_apply(repo):
    check = langfuse.Langfuse().verify(repo)
    assert not check.ok and "não foi aplicado" in check.detail


def test_verify_names_missing_variables(repo, capsys):
    run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    check = langfuse.Langfuse().verify(repo)
    assert not check.ok
    for name in ALL_VARS:
        assert name in check.detail


def test_verify_ok_with_variables_in_the_environment(repo, capsys, monkeypatch):
    run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    for name in ALL_VARS:
        monkeypatch.setenv(name, "fake-value")
    code, out, _ = run(capsys, "verificar", "langfuse", str(repo))
    assert code == 0 and out.strip() == "ok"


def test_verify_accepts_compose_variables_from_the_env_file(repo, capsys, monkeypatch):
    run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    for name in langfuse.INTEGRATION_VARS:
        monkeypatch.setenv(name, "fake-value")
    env = "".join(f"{n}=fake\n" for n in langfuse.COMPOSE_SECRETS[1:])
    (repo / ".dark/langfuse/.env").write_text(env + f"{langfuse.COMPOSE_SECRETS[0]}=\n",
                                              encoding="utf-8")
    check = langfuse.Langfuse().verify(repo)
    assert not check.ok and langfuse.COMPOSE_SECRETS[0] in check.detail
    assert not any(n in check.detail for n in ALL_VARS if n != langfuse.COMPOSE_SECRETS[0])
    with (repo / ".dark/langfuse/.env").open("a", encoding="utf-8") as f:
        f.write(f"export {langfuse.COMPOSE_SECRETS[0]}='x'\n")
    assert langfuse.Langfuse().verify(repo).ok


def test_verify_never_prints_values(repo, capsys, monkeypatch):
    run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-do-not-print")
    (repo / ".dark/langfuse/.env").write_text("SALT=do-not-print-either\n", encoding="utf-8")
    detail = langfuse.Langfuse().verify(repo).detail
    assert "do-not-print" not in detail


def test_verify_detects_edited_files_and_missing_wiring(repo, capsys, monkeypatch):
    run(capsys, "adicionar", "langfuse", str(repo), "--aplicar")
    for name in ALL_VARS:
        monkeypatch.setenv(name, "fake-value")
    compose = repo / ".dark/langfuse/docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    check = langfuse.Langfuse().verify(repo)
    assert not check.ok and ".dark/langfuse/docker-compose.yml" in check.detail
    compose.write_text(langfuse.COMPOSE, encoding="utf-8")
    (repo / ".claude/settings.json").write_text("{}\n", encoding="utf-8")
    check = langfuse.Langfuse().verify(repo)
    assert not check.ok and ".claude/settings.json" in check.detail
    (repo / ".claude/settings.json").write_text("{ broken", encoding="utf-8")
    check = langfuse.Langfuse().verify(repo)
    assert not check.ok and ".claude/settings.json" in check.detail


# ------------------------------------------------------------ docker (optional)


@pytest.mark.skipif(shutil.which("docker") is None, reason="sem Docker")
def test_docker_compose_config_accepts_the_file(tmp_path):
    (tmp_path / "compose").mkdir()
    compose = tmp_path / "compose" / "docker-compose.yml"
    compose.write_text(langfuse.COMPOSE, encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("".join(f"{n}={'0' * 64}\n" for n in langfuse.COMPOSE_SECRETS),
                   encoding="utf-8")
    clean = {k: v for k, v in os.environ.items() if k not in ALL_VARS}
    try:
        done = subprocess.run(["docker", "compose", "-f", str(compose), "--env-file", str(env),
                               "config", "--quiet"], capture_output=True, text=True,
                              timeout=60, env=clean)
    except (OSError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"docker compose indisponível: {e}")
    if "is not a docker command" in done.stderr or "unknown command" in done.stderr:
        pytest.skip("sem o plugin docker compose")
    assert done.returncode == 0, done.stderr
    missing = subprocess.run(["docker", "compose", "-f", str(compose), "config", "--quiet"],
                             capture_output=True, text=True, timeout=60, env=clean)
    assert missing.returncode != 0 and "SALT" in missing.stderr + missing.stdout
