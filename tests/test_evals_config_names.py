"""PYTEST_CONFIG_NAMES follows what the installed pytest reads (goal 033).

Each name is created in an empty directory and pytest is run there: the
"configfile:" line of its header (public output) says which file it read.
Names the list lacks are looked for among the plausible spellings
(stem x extension). What this cannot catch: a name outside that grid, or
a new kind of extension point that is not a file by name.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from dark.evals import workspace

CONFIG_FILES = tuple(n for n in workspace.PYTEST_CONFIG_NAMES if n != "conftest.py")

# Content that makes each spelling a valid pytest configuration.
_INI = "[pytest]\naddopts = -ra\n"
_CONTENT = {
    "pytest.ini": _INI, ".pytest.ini": _INI, "tox.ini": _INI,
    "setup.cfg": "[tool:pytest]\naddopts = -ra\n",
    "pytest.toml": '[pytest]\naddopts = ["-ra"]\n',
    ".pytest.toml": '[pytest]\naddopts = ["-ra"]\n',
    "pyproject.toml": '[tool.pytest]\naddopts = ["-ra"]\n',
}


def _run(tmp_path, *extra):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--co", "-p", "no:cacheprovider", *extra],
        cwd=tmp_path, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        env={"PATH": "", "PYTEST_ADDOPTS": ""}).stdout


def _configfile(tmp_path, name):
    (tmp_path / name).write_text(_CONTENT.get(name, _INI), encoding="utf-8")
    for line in _run(tmp_path).splitlines():
        if line.startswith("configfile:"):
            return line.split(":", 1)[1].strip()
    return None


@pytest.mark.parametrize("name", CONFIG_FILES)
def test_pytest_reads_every_listed_configuration_file(tmp_path, name):
    assert _configfile(tmp_path, name) == name


def test_pytest_reads_conftest_listed_in_the_names(tmp_path):
    (tmp_path / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    assert "1 test collected" in _run(tmp_path)
    (tmp_path / "conftest.py").write_text('collect_ignore = ["test_x.py"]\n', encoding="utf-8")
    assert "1 test collected" not in _run(tmp_path)
    assert "conftest.py" in workspace.PYTEST_CONFIG_NAMES


_CANDIDATES = [f"{stem}{ext}" for stem in ("pytest", ".pytest", "tox", ".tox", "setup",
                                           "pyproject", "pyproject.pytest", "pytest.config")
               for ext in (".ini", ".toml", ".cfg", ".conf", ".yaml", ".json")]


@pytest.mark.parametrize("name", _CANDIDATES)
def test_pytest_reads_no_plausible_name_the_list_lacks(tmp_path, name):
    read = _configfile(tmp_path, name)
    if read is not None:
        assert name in workspace.PYTEST_CONFIG_NAMES
