"""Distribution (goal 023): what can be checked about the installed package
without network and without building the wheel.

The wheel itself is built, installed outside the checkout and run by the
`install` job of .github/workflows/tests.yml; these tests catch, earlier and
locally, the mistakes that would only show up there or on someone else's
machine.
"""

from __future__ import annotations

import ast
import fnmatch
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PACKAGE = SRC / "dark"
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

# Paths and names that must not appear in files meant for other people.
_PERSONAL = [
    re.compile(r"/Users/[A-Za-z0-9._-]+"),
    re.compile(r"/home/[A-Za-z0-9._-]+"),
    re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
    re.compile(r"/mnt/[a-z]/Users/", re.IGNORECASE),
    re.compile(r"github\.com[:/][A-Za-z0-9-]+/", re.IGNORECASE),
    re.compile(r"git@[A-Za-z0-9.-]+:"),
]
_SECRET = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
]


def _package_files() -> list[Path]:
    return [p for p in PACKAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]


def _changelog_versions() -> list[str]:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.findall(r"^## \[?(\d+\.\d+\.\d+)\]?", text, re.MULTILINE)


# ==========================================================================
# What goes into the wheel
# ==========================================================================


def test_every_directory_with_python_code_is_a_regular_package():
    # `packages.find` only picks up directories with __init__.py; a module in a
    # directory without one would work from the checkout (pythonpath = src) and
    # be missing from the wheel.
    missing = sorted(
        str(d.relative_to(SRC))
        for d in {p.parent for p in _package_files() if p.suffix == ".py"}
        if not (d / "__init__.py").is_file()
    )
    assert missing == []


def test_every_non_python_file_in_the_package_is_declared_as_package_data():
    data = PYPROJECT.get("tool", {}).get("setuptools", {}).get("package-data", {})
    patterns = [pat for pats in data.values() for pat in pats]
    undeclared = sorted(
        str(p.relative_to(PACKAGE))
        for p in _package_files()
        if p.suffix != ".py"
        and not any(
            fnmatch.fnmatch(p.relative_to(PACKAGE).as_posix(), pat) for pat in patterns
        )
    )
    assert undeclared == [], "add them to [tool.setuptools.package-data]"


def test_the_package_reads_no_file_relative_to_its_own_location():
    # A path built from __file__ points into the checkout during development
    # and into site-packages once installed; anything it reads must be package
    # data (checked above). Today nothing does, so any use is flagged.
    users = sorted(
        str(p.relative_to(SRC))
        for p in _package_files()
        if p.suffix == ".py" and "__file__" in p.read_text(encoding="utf-8")
    )
    assert users == []


def test_runtime_imports_are_standard_library_or_the_package_itself():
    # dependencies = []: an import of anything else works in the development
    # venv (where pytest and friends live) and fails after `pip install`.
    assert PYPROJECT["project"]["dependencies"] == []
    allowed = set(sys.stdlib_module_names) | {"dark", "__future__"}
    foreign = set()
    for path in _package_files():
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.split(".")[0] not in allowed:
                    foreign.add(f"{path.relative_to(SRC)}: {name}")
    assert sorted(foreign) == []


def test_console_script_points_to_an_existing_function():
    target = PYPROJECT["project"]["scripts"]["dark"]
    module, _, func = target.partition(":")
    path = SRC / Path(*module.split(".")).with_suffix(".py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert func in {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_the_evals_command_is_a_runnable_module():
    assert (PACKAGE / "evals" / "__main__.py").is_file()


# ==========================================================================
# Version and change log
# ==========================================================================


def test_version_is_semver_and_declared_once():
    version = PYPROJECT["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert "dynamic" not in PYPROJECT["project"] or "version" not in PYPROJECT["project"]["dynamic"]
    # No second copy of the version in the code: read it with importlib.metadata.
    copies = sorted(
        str(p.relative_to(SRC))
        for p in _package_files()
        if p.suffix == ".py" and re.search(r"__version__\s*=", p.read_text(encoding="utf-8"))
    )
    assert copies == []


def test_changelog_latest_entry_matches_pyproject_version():
    versions = _changelog_versions()
    assert versions, "CHANGELOG.md has no '## <version>' entry"
    assert versions[0] == PYPROJECT["project"]["version"]


def test_changelog_entries_are_unique_and_newest_first():
    versions = _changelog_versions()
    keys = [tuple(int(x) for x in v.split(".")) for v in versions]
    assert len(set(keys)) == len(keys)
    assert keys == sorted(keys, reverse=True)


# ==========================================================================
# Files meant for people outside the project
# ==========================================================================


def test_public_files_have_no_personal_path_account_or_secret():
    found = []
    for name in ["README.md", "CHANGELOG.md", "pyproject.toml"]:
        text = (ROOT / name).read_text(encoding="utf-8")
        for pattern in _PERSONAL + _SECRET:
            for m in pattern.finditer(text):
                found.append(f"{name}: {m.group(0)}")
    assert found == []


def test_readme_installs_from_a_placeholder_url():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'pip install "git+<URL do repositório>"' in text


def test_readme_starts_with_the_user_and_ends_with_development():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    assert headings[0] == "Instalação"
    assert headings[-1] == "Desenvolvimento"
