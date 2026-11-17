"""Plan, apply, record and revert.

Every operation is first computed against an in-memory overlay of the
repository. Only when no operation conflicts are the changes written, in
one pass: directories created, files written (each through a temporary
file and ``os.replace``), files deleted, directories removed. If a write
fails, what was already written is undone and the error is raised.

The manifest (``MANIFEST_NAME`` at the repository root) lists one entry
per operation actually applied:

- ``module`` and ``version``: who asked, pinned;
- ``op``: the operation, as in the plan;
- ``owned``: what the operation had to create on the way and must clean
  up: directories, the file itself, JSON keys, and the whitespace that
  was inside a JSON container before it got its first child;
- ``sha256``: for ``create_file``, the content written.

On revert, an entry first undoes its own change (the "leaf"): only when
what is there is exactly what was applied. Otherwise the entry is kept
and reported. Then each owned resource is released, last first: removed
when it is back to empty; handed over to another entry still in the
manifest that lives inside it; or left in place and reported, when what
keeps it non-empty is not ours. The hand-over is what makes reverting one
module safe when another one wrote into the same file or directory.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from . import jsontext, paths, textfile
from .jsontext import JsonTextError
from .operations import (
    AppendLine,
    CreateDir,
    CreateFile,
    JsonEntry,
    MarkedBlock,
    Operation,
    Plan,
    check_pinned,
    op_from_spec,
)
from .paths import PathRefused
from .textfile import EncodingRefused

MANIFEST_NAME = ".dark-scaffold.json"
MANIFEST_FORMAT = "dark-scaffold/1"
JSON_SKELETON = "{}\n"
_NO_FINAL_NEWLINE = "\\ Sem quebra de linha no fim do arquivo\n"

_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSW|CREDENTIAL|AUTH|PRIVATE", re.I)
_SECRET_MIN_LEN = 8


class Conflict(Exception):
    """An operation cannot be applied. The message is meant for the user."""


class ManifestError(ValueError):
    pass


# --------------------------------------------------------------- results


@dataclass
class Step:
    op: Operation
    status: str  # new, already_applied, already_present, conflict
    reason: str = ""


@dataclass
class Outcome:
    steps: list[Step]
    diffs: dict[str, str]
    applied: bool = False

    @property
    def ok(self) -> bool:
        return all(s.status != "conflict" for s in self.steps)

    @property
    def changed(self) -> bool:
        return self.applied and any(s.status == "new" for s in self.steps)


@dataclass
class RevertStep:
    op: Operation
    status: str  # reverted, already_gone, kept, handed_over
    reason: str = ""


@dataclass
class RevertOutcome:
    steps: list[RevertStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.status != "kept" for s in self.steps)


# --------------------------------------------------------------- overlay


class Overlay:
    """The repository as it would be after the pending changes."""

    def __init__(self, root: Path):
        self.root = root
        self.files: dict[str, bytes | None] = {}
        self.dirs: dict[str, bool] = {}

    def _disk(self, rel: str) -> Path:
        return paths.on_disk(self.root, rel)

    def read(self, rel: str) -> bytes | None:
        if rel in self.files:
            return self.files[rel]
        p = self._disk(rel)
        return p.read_bytes() if p.is_file() else None

    def is_dir(self, rel: str) -> bool:
        if rel in self.dirs:
            return self.dirs[rel]
        return self._disk(rel).is_dir()

    def write(self, rel: str, data: bytes) -> None:
        self.files[rel] = data

    def delete(self, rel: str) -> None:
        self.files[rel] = None

    def mkdir(self, rel: str) -> None:
        self.dirs[rel] = True

    def rmdir(self, rel: str) -> None:
        self.dirs[rel] = False

    def dir_empty(self, rel: str) -> bool:
        names: set[str] = set()
        p = self._disk(rel)
        if p.is_dir():
            names = {c.name for c in p.iterdir()}
        for table in (self.files, self.dirs):
            for k, v in table.items():
                kp = PurePosixPath(k)
                if kp.parent.as_posix() != rel:
                    continue
                if v is None or v is False:
                    names.discard(kp.name)
                else:
                    names.add(kp.name)
        return not names

    def changes(self):
        mkdirs = sorted((d for d, v in self.dirs.items()
                         if v and not self._disk(d).is_dir()),
                        key=lambda d: len(PurePosixPath(d).parts))
        rmdirs = sorted((d for d, v in self.dirs.items()
                         if not v and self._disk(d).is_dir()),
                        key=lambda d: -len(PurePosixPath(d).parts))
        writes, deletes = [], []
        for rel in sorted(self.files):
            data = self.files[rel]
            p = self._disk(rel)
            if data is None:
                if p.is_file():
                    deletes.append(rel)
            elif not p.is_file() or p.read_bytes() != data:
                writes.append((rel, data))
        return mkdirs, writes, deletes, rmdirs


def _write_bytes(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".dark-tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _commit(ov: Overlay) -> None:
    mkdirs, writes, deletes, rmdirs = ov.changes()
    disk = ov._disk
    done: list[tuple[str, Path, bytes | None]] = []
    try:
        for d in mkdirs:
            disk(d).mkdir()
            done.append(("mkdir", disk(d), None))
        for rel, data in writes:
            p = disk(rel)
            orig = p.read_bytes() if p.is_file() else None
            _write_bytes(p, data)
            done.append(("file", p, orig))
        for rel in deletes:
            p = disk(rel)
            orig = p.read_bytes()
            p.unlink()
            done.append(("file", p, orig))
        for d in rmdirs:
            disk(d).rmdir()
            done.append(("rmdir", disk(d), None))
    except BaseException:
        for kind, p, orig in reversed(done):
            try:
                if kind == "mkdir":
                    p.rmdir()
                elif kind == "rmdir":
                    p.mkdir()
                elif orig is None:
                    p.unlink()
                else:
                    _write_bytes(p, orig)
            except OSError:
                pass
        raise


# -------------------------------------------------------------- manifest


def load_manifest(root: Path) -> dict:
    p = Path(root) / MANIFEST_NAME
    if p.is_symlink():
        raise ManifestError(f"{MANIFEST_NAME} é um link simbólico; o motor não o usa")
    if not p.exists():
        return {"format": MANIFEST_FORMAT, "entries": []}
    try:
        data = json.loads(p.read_bytes())
    except ValueError as e:
        raise ManifestError(f"{MANIFEST_NAME} não é JSON válido: {e}") from None
    if (not isinstance(data, dict) or data.get("format") != MANIFEST_FORMAT
            or not isinstance(data.get("entries"), list)):
        raise ManifestError(f"{MANIFEST_NAME} existe, mas não é um manifesto do motor")
    return data


def _store_manifest(ov: Overlay, manifest: dict) -> None:
    if manifest["entries"]:
        text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        ov.write(MANIFEST_NAME, text.encode("utf-8"))
    elif ov.read(MANIFEST_NAME) is not None:
        ov.delete(MANIFEST_NAME)


# ------------------------------------------------------------- utilities


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_secrets(op: Operation) -> None:
    texts = op.texts()
    for name, value in os.environ.items():
        if len(value) >= _SECRET_MIN_LEN and _SECRET_NAME.search(name):
            if any(value in t for t in texts):
                raise Conflict(
                    f"o conteúdo contém o valor da variável de ambiente {name}; "
                    f"refira o nome (${{{name}}}), nunca o valor")


def _ensure_dirs(ov: Overlay, dirs: list[str]) -> list[dict]:
    owned = []
    for d in dirs:
        if ov.is_dir(d):
            continue
        if ov.read(d) is not None:
            raise Conflict(f"{d} existe e não é um diretório")
        ov.mkdir(d)
        owned.append({"kind": "dir", "path": d})
    return owned


def _open_text(ov: Overlay, rel: str, skeleton: str):
    if ov.is_dir(rel):
        raise Conflict(f"{rel} é um diretório")
    data = ov.read(rel)
    if data is not None:
        return textfile.decode(data), []
    owned = _ensure_dirs(ov, paths.parents(rel))
    owned.append({"kind": "file", "path": rel, "skeleton": skeleton})
    return textfile.Decoded(skeleton, "utf-8", b"", False), owned


def _check_line(text: str, what: str) -> None:
    if not text or "\n" in text or "\r" in text:
        raise Conflict(f"{what} precisa ser uma linha não vazia, sem quebra")


def _find_block(lines: list[str], op: MarkedBlock) -> tuple[int, int] | None:
    starts = [i for i, t in enumerate(lines) if t == op.start]
    if len(starts) > 1:
        raise Conflict(f"marcador {op.start!r} aparece mais de uma vez")
    if not starts:
        if op.end in lines:
            raise Conflict(f"marcador de fim {op.end!r} sem o de início")
        return None
    s = starts[0]
    for e in range(s + 1, len(lines)):
        if lines[e] == op.end:
            return s, e
    raise Conflict(f"marcador de início {op.start!r} sem o de fim")


def _json_target(op: JsonEntry) -> list[str]:
    return list(op.keys) + ([op.key] if op.key is not None else [])


# ------------------------------------------------------------ apply side


def _do_create_file(ov: Overlay, rel: str, op: CreateFile):
    if ov.is_dir(rel):
        raise Conflict(f"{rel} é um diretório")
    want = op.content.encode("utf-8")
    data = ov.read(rel)
    if data is not None:
        if data == want:
            return None
        raise Conflict(f"{rel} já existe com conteúdo diferente")
    owned = _ensure_dirs(ov, paths.parents(rel))
    ov.write(rel, want)
    return owned, {"sha256": _sha(want)}


def _do_create_dir(ov: Overlay, rel: str, op: CreateDir):
    if ov.read(rel) is not None:
        raise Conflict(f"{rel} existe e não é um diretório")
    if ov.is_dir(rel):
        return None
    return _ensure_dirs(ov, paths.parents(rel) + [rel]), {}


def _do_append_line(ov: Overlay, rel: str, op: AppendLine):
    _check_line(op.line, "a linha")
    dec, owned = _open_text(ov, rel, "")
    if textfile.find_line(dec.text, op.line) is not None:
        return None
    dec.check(op.line)
    ov.write(rel, dec.encode(textfile.append_lines(dec.text, [op.line], dec.newline)))
    return owned, {}


def _do_marked_block(ov: Overlay, rel: str, op: MarkedBlock):
    _check_line(op.start, "o marcador de início")
    _check_line(op.end, "o marcador de fim")
    if op.start == op.end:
        raise Conflict("os marcadores de início e fim precisam ser diferentes")
    for line in op.lines:
        if "\n" in line or "\r" in line or line in (op.start, op.end):
            raise Conflict("as linhas do bloco não podem ter quebra nem repetir marcador")
    dec, owned = _open_text(ov, rel, "")
    lines = textfile.line_texts(dec.text)
    found = _find_block(lines, op)
    if found is not None:
        s, e = found
        if tuple(lines[s + 1:e]) == op.lines:
            return None
        raise Conflict(f"o bloco {op.start!r} já existe em {rel} com outro conteúdo")
    for t in op.texts():
        dec.check(t)
    new = textfile.append_lines(dec.text, [op.start, *op.lines, op.end], dec.newline)
    ov.write(rel, dec.encode(new))
    return owned, {}


def _do_json_entry(ov: Overlay, rel: str, op: JsonEntry):
    dec, owned = _open_text(ov, rel, JSON_SKELETON)
    text = dec.text
    root = jsontext.parse(text)
    keys = list(op.keys)
    append = op.key is None
    nl = dec.newline
    created = False
    for depth in range(len(keys)):
        if jsontext.find(root, keys[:depth + 1]) is not None:
            continue
        parent = jsontext.find(root, keys[:depth])
        if parent.kind != "object":
            raise Conflict(f"{'.'.join(keys[:depth]) or 'a raiz'} não é um objeto JSON")
        empty = [] if append and depth == len(keys) - 1 else {}
        dec.check(keys[depth])
        text, inner = jsontext.insert(text, root, parent, keys[depth], empty, nl)
        if inner is not None:
            owned.append({"kind": "json_inner", "path": rel, "keys": keys[:depth],
                          "inner": inner})
        owned.append({"kind": "json_key", "path": rel, "keys": keys[:depth + 1]})
        root = jsontext.parse(text)
        created = True
    container = jsontext.find(root, keys)
    where = ".".join(keys) or "a raiz"
    if append:
        if container.kind != "array":
            raise Conflict(f"{where} em {rel} não é uma lista JSON")
        if not created and any(c.node.value(text) == op.value for c in container.children):
            return None
    else:
        if container.kind != "object":
            raise Conflict(f"{where} em {rel} não é um objeto JSON")
        found = jsontext.child(container, op.key)
        if found is not None:
            if found[1].node.value(text) == op.value:
                return None
            raise Conflict(f"{where}.{op.key} já existe em {rel} com outro valor")
    for t in op.texts():
        dec.check(t)
    text, inner = jsontext.insert(text, root, container, op.key, op.value, nl)
    if inner is not None:
        owned.append({"kind": "json_inner", "path": rel, "keys": keys, "inner": inner})
    ov.write(rel, dec.encode(text))
    return owned, {}


_DO = {
    CreateFile.kind: _do_create_file,
    CreateDir.kind: _do_create_dir,
    AppendLine.kind: _do_append_line,
    MarkedBlock.kind: _do_marked_block,
    JsonEntry.kind: _do_json_entry,
}

_REFUSALS = (Conflict, PathRefused, EncodingRefused, JsonTextError)


def _check_repo(root: Path) -> Path:
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"o repositório não é um diretório: {root}")
    return root


def _compute(root: Path, plan: Plan):
    root = _check_repo(root)
    if not isinstance(plan.module, str) or not plan.module:
        raise ValueError("o plano precisa de um nome de módulo")
    check_pinned(plan.version)
    manifest = load_manifest(root)
    initial = [(e["module"], e["op"]) for e in manifest["entries"]]
    ov = Overlay(root)
    steps: list[Step] = []
    dirty = False
    for op in plan.operations:
        spec = op.to_spec()
        recorded = (plan.module, spec) in initial
        try:
            rel = paths.normalize(op.path, MANIFEST_NAME)
            paths.check_no_links(root, rel)
            _check_secrets(op)
            if op.kind != CreateFile.kind:
                _check_not_owned_whole(manifest, plan.module, rel)
            result = _DO[op.kind](ov, rel, op)
            if result is not None and recorded:
                raise Conflict("registrado no manifesto, mas ausente ou desfeito no "
                               "repositório; reverta o módulo antes de aplicar de novo")
        except _REFUSALS as e:
            steps.append(Step(op, "conflict", str(e)))
            continue
        if result is None:
            steps.append(Step(op, "already_applied" if recorded else "already_present"))
            if not recorded and _owner(manifest, plan.module, spec, rel) is not None:
                # Present because another module applied it: record the need,
                # so reverting that module hands the thing over instead.
                manifest["entries"].append({"module": plan.module, "version": plan.version,
                                            "op": spec, "owned": [], "shared": True})
                dirty = True
            continue
        owned, extra = result
        manifest["entries"].append({"module": plan.module, "version": plan.version,
                                    "op": spec, "owned": owned, **extra})
        steps.append(Step(op, "new"))
        dirty = True
    return ov, steps, manifest, dirty


def _check_not_owned_whole(manifest: dict, module: str, rel: str) -> None:
    """A file created whole by one module is not edited by another: its
    revert checks the hash of the whole file and would keep it."""
    for e in manifest["entries"]:
        if (e["module"] != module and e["op"]["op"] == CreateFile.kind
                and e["op"].get("path") == rel):
            raise Conflict(f"{rel} foi criado inteiro pelo módulo {e['module']}; "
                           "outro módulo não pode editá-lo")


def _owner(manifest: dict, module: str, spec: dict, rel: str) -> dict | None:
    """Entry of another module that applied what ``spec`` asks for."""
    for e in manifest["entries"]:
        if e["module"] == module:
            continue
        if e["op"] == spec:
            return e
        if spec["op"] == CreateDir.kind and any(
                r["kind"] == "dir" and r["path"] == rel for r in e.get("owned", [])):
            return e
    return None


def _diffs(ov: Overlay) -> dict[str, str]:
    out = {}
    for rel, data in sorted(ov.files.items()):
        if rel == MANIFEST_NAME:
            continue
        before_bytes = ov._disk(rel).read_bytes() if ov._disk(rel).is_file() else b""
        if data == before_bytes:
            continue
        before = textfile.decode(before_bytes).text
        after = textfile.decode(data or b"").text
        lines = difflib.unified_diff(
            before.replace("\r\n", "\n").splitlines(keepends=True),
            after.replace("\r\n", "\n").splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}")
        out[rel] = "".join(
            line if line.endswith("\n") else line + "\n" + _NO_FINAL_NEWLINE
            for line in lines)
    return out


def inspect(root: Path, plan: Plan) -> Outcome:
    """What ``apply`` would do. Changes nothing."""
    ov, steps, _, _ = _compute(root, plan)
    return Outcome(steps, _diffs(ov))


def apply(root: Path, plan: Plan) -> Outcome:
    """Apply every operation of ``plan``, or none when one conflicts."""
    ov, steps, manifest, dirty = _compute(root, plan)
    out = Outcome(steps, _diffs(ov))
    if not out.ok:
        return out
    if dirty:
        _store_manifest(ov, manifest)
        _commit(ov)
    out.applied = True
    return out


# ----------------------------------------------------------- revert side


def _undo_create_file(ov, rel, op, entry):
    data = ov.read(rel)
    if data is None:
        return "already_gone", ""
    if _sha(data) != entry.get("sha256"):
        return "kept", f"{rel} foi alterado depois da aplicação"
    ov.delete(rel)
    return "reverted", ""


def _undo_create_dir(ov, rel, op, entry):
    return ("reverted", "") if ov.is_dir(rel) else ("already_gone", "")


def _undo_append_line(ov, rel, op, entry):
    data = ov.read(rel)
    if data is None:
        return "already_gone", ""
    dec = textfile.decode(data)
    i = textfile.find_line(dec.text, op.line)
    if i is None:
        return "already_gone", ""
    ov.write(rel, dec.encode(textfile.remove_lines(dec.text, i, 1)))
    return "reverted", ""


def _undo_marked_block(ov, rel, op, entry):
    data = ov.read(rel)
    if data is None:
        return "already_gone", ""
    dec = textfile.decode(data)
    lines = textfile.line_texts(dec.text)
    try:
        found = _find_block(lines, op)
    except Conflict as e:
        return "kept", str(e)
    if found is None:
        return "already_gone", ""
    s, e = found
    if tuple(lines[s + 1:e]) != op.lines:
        return "kept", f"o bloco {op.start!r} em {rel} foi alterado depois da aplicação"
    ov.write(rel, dec.encode(textfile.remove_lines(dec.text, s, e - s + 1)))
    return "reverted", ""


def _undo_json_entry(ov, rel, op, entry):
    data = ov.read(rel)
    if data is None:
        return "already_gone", ""
    dec = textfile.decode(data)
    root = jsontext.parse(dec.text)
    container = jsontext.find(root, list(op.keys))
    if container is None or container.kind not in ("object", "array"):
        return "already_gone", ""
    index = None
    if op.key is None:
        for i, c in enumerate(container.children):
            if c.node.value(dec.text) == op.value:
                index = i
        if index is None:
            return "already_gone", ""
    else:
        found = jsontext.child(container, op.key) if container.kind == "object" else None
        if found is None:
            return "already_gone", ""
        index, c = found
        if c.node.value(dec.text) != op.value:
            where = ".".join(_json_target(op))
            return "kept", f"{where} em {rel} foi alterado depois da aplicação"
    ov.write(rel, dec.encode(jsontext.remove(dec.text, container, index)))
    return "reverted", ""


_UNDO = {
    CreateFile.kind: _undo_create_file,
    CreateDir.kind: _undo_create_dir,
    AppendLine.kind: _undo_append_line,
    MarkedBlock.kind: _undo_marked_block,
    JsonEntry.kind: _undo_json_entry,
}


def _release_state(ov: Overlay, res: dict) -> tuple[str, Any]:
    """("gone" | "empty" | "busy", parsed info) for an owned resource."""
    kind, rel = res["kind"], res["path"]
    if kind == "dir":
        if not ov.is_dir(rel):
            return "gone", None
        return ("empty" if ov.dir_empty(rel) else "busy"), None
    data = ov.read(rel)
    if data is None:
        return "gone", None
    if kind == "file":
        return ("empty" if data == res["skeleton"].encode("utf-8") else "busy"), None
    dec = textfile.decode(data)
    root = jsontext.parse(dec.text)
    node = jsontext.find(root, res["keys"])
    if node is None:
        return "gone", None
    if node.kind == "scalar" or node.children:
        return "busy", None
    return "empty", (dec, root, node)


def _release_one(ov: Overlay, res: dict, info) -> None:
    kind, rel = res["kind"], res["path"]
    if kind == "dir":
        ov.rmdir(rel)
    elif kind == "file":
        ov.delete(rel)
    elif kind == "json_inner":
        dec, root, node = info
        ov.write(rel, dec.encode(jsontext.set_inner(dec.text, node, res["inner"])))
    elif kind == "json_key":
        dec, root, node = info
        keys = res["keys"]
        parent = jsontext.find(root, keys[:-1])
        index, _ = jsontext.child(parent, keys[-1])
        ov.write(rel, dec.encode(jsontext.remove(dec.text, parent, index)))


def _depends(entry: dict, res: dict) -> bool:
    spec = entry["op"]
    target = spec.get("path", "")
    try:
        target = paths.normalize(target, MANIFEST_NAME)
    except PathRefused:
        return False
    if res["kind"] == "dir":
        return paths.is_under(target, res["path"]) or (
            target == res["path"] and spec["op"] == CreateDir.kind)
    if target != res["path"] or spec["op"] == CreateFile.kind:
        return False
    if res["kind"] == "file":
        return True
    if spec["op"] != JsonEntry.kind:
        return False
    op = op_from_spec(spec)
    tk, rk = _json_target(op), res["keys"]
    return tk[:len(rk)] == rk and (len(tk) > len(rk) or op.key is None)


def _release(ov: Overlay, res: dict, remaining: list[dict], notes: list[str]) -> None:
    try:
        state, info = _release_state(ov, res)
    except _REFUSALS as e:
        notes.append(f"{res['path']}: deixado no lugar ({e})")
        return
    if state == "gone":
        return
    # Hand over first: an empty directory can still be what another entry
    # asked for (create_dir).
    for other in remaining:
        if _depends(other, res):
            other.setdefault("owned", []).insert(0, res)
            return
    if state == "empty":
        _release_one(ov, res, info)
        return
    note = f"{res['path']}: deixado no lugar, contém conteúdo que não veio do motor"
    if note not in notes:
        notes.append(note)


def revert(root: Path, module: str) -> RevertOutcome:
    """Undo every manifest entry of ``module``, last applied first."""
    root = _check_repo(root)
    manifest = load_manifest(root)
    remaining: list[dict] = list(manifest["entries"])
    mine = [e for e in remaining if e.get("module") == module]
    ov = Overlay(root)
    out = RevertOutcome()
    for entry in reversed(mine):
        op = op_from_spec(entry["op"])
        heir = next((o for o in remaining
                     if o is not entry and o["module"] != module and o["op"] == entry["op"]),
                    None)
        if heir is not None:
            # Another module needs the same thing: it becomes the owner.
            heir["owned"] = entry.get("owned", []) + heir.get("owned", [])
            if "sha256" in entry:
                heir["sha256"] = entry["sha256"]
            heir.pop("shared", None)
            remaining.remove(entry)
            out.steps.append(RevertStep(
                op, "handed_over", f"continua no lugar para o módulo {heir['module']}"))
            continue
        try:
            rel = paths.normalize(op.path, MANIFEST_NAME)
            paths.check_no_links(root, rel)
            if entry.get("shared"):
                status, reason = "reverted", ""  # the change was not ours
            else:
                status, reason = _UNDO[op.kind](ov, rel, op, entry)
        except _REFUSALS as e:
            status, reason = "kept", str(e)
        out.steps.append(RevertStep(op, status, reason))
        if status == "kept":
            continue
        remaining.remove(entry)
        for res in reversed(entry.get("owned", [])):
            _release(ov, res, remaining, out.notes)
    manifest["entries"] = remaining
    if mine:
        _store_manifest(ov, manifest)
        _commit(ov)
    return out
