"""Confined file access, reviewed changes and compare-and-swap
rollback."""

from __future__ import annotations

import base64
import difflib
import fnmatch
import hashlib
import json
import os
import re
import stat
import tempfile
import threading
import time
import uuid
from pathlib import Path, PureWindowsPath

from pydantic import BaseModel, Field

DENIED = {
    ".git",
    ".router-state",
    ".idea",
    "node_modules",
    "__pycache__",
    "backups",
    "dist",
    "build",
    "target",
    "logs",
    "htmlcov",
    ".pytest_cache",
    ".ruff_cache",
}
TEXT = {
    ".py",
    ".java",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".json",
    ".xml",
    ".html",
    ".css",
    ".sql",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".gradle",
    ".kt",
    ".kts",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".cs",
    ".properties",
}


def digest(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


class FileChange(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    content: str | None = Field(
        description="Complete new UTF-8 contents; null deletes the file."
    )


class Workspace:
    def __init__(self, root: Path, state: Path | None = None):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Workspace must be a directory")
        self.state = (state or self.root / ".router-state").resolve()
        if self.state == self.root or self.state in self.root.parents:
            raise ValueError("State directory cannot contain the workspace")
        self.lock = threading.RLock()
        self.max_bytes = 2_000_000
        self._server_lock = None

    def path(self, value: str, *, directory: bool = False) -> Path:
        if not value or len(value) > 512 or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid relative path")
        normalized = value.replace(chr(92), "/")
        win = PureWindowsPath(normalized)
        if win.drive or win.root or normalized.startswith("/"):
            raise ValueError("Use a path relative to the configured workspace")
        parts = normalized.split("/")
        for part in parts:
            lower = part.casefold()
            if (
                part in {"..", ""}
                or ":" in part
                or part.endswith((" ", "."))
                and part != "."
            ):
                raise ValueError(
                    "Traversal, device and alternate-stream paths are forbidden"
                )
            if (
                lower in DENIED
                or lower.startswith((".venv", ".env"))
                or lower.endswith(".egg-info")
            ):
                raise ValueError("Path is excluded from workspace tools")
            if any(x in lower for x in ("credential", "secret")) or lower.endswith(
                (".pem", ".key", ".pfx", ".p12")
            ):
                raise ValueError("Credential files are excluded")
            if re.fullmatch(r"(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", lower):
                raise ValueError("Windows device paths are forbidden")
        p = self.root.joinpath(*parts)
        current = self.root
        for part in parts:
            current = current / part
            if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
                raise ValueError("Symlinks/junctions are not accessible")
        resolved = p.resolve()
        if (
            not resolved.is_relative_to(self.root)
            or resolved == self.state
            or resolved.is_relative_to(self.state)
        ):
            raise ValueError("Path is outside the accessible workspace")
        if not directory and resolved == self.root:
            raise ValueError("A file path is required")
        if p.exists() and p.is_file() and p.stat().st_nlink > 1:
            raise ValueError("Hard-linked files are not accessible")
        return p

    def raw(self, p: Path) -> bytes | None:
        if not p.exists():
            return None
        if not p.is_file() or p.stat().st_size > self.max_bytes:
            raise ValueError("Not a regular file or file exceeds 2 MB")
        data = p.read_bytes()
        if 0 in data:
            raise ValueError("Binary files are not supported")
        data.decode("utf-8-sig")
        return data

    def inventory(
        self, include: str = "*", limit: int = 20000
    ) -> tuple[list[str], bool]:
        patterns = [x.strip() for x in include.split(",") if x.strip()]
        results = []
        for folder, dirs, files in os.walk(self.root, followlinks=False):
            base = Path(folder)
            allowed = []
            for d in sorted(dirs):
                try:
                    self.path(
                        (base / d).relative_to(self.root).as_posix(), directory=True
                    )
                    allowed.append(d)
                except ValueError:
                    pass
            dirs[:] = allowed
            for name in sorted(files):
                rel = (base / name).relative_to(self.root).as_posix()
                try:
                    self.path(rel)
                except ValueError:
                    continue
                if any(fnmatch.fnmatch(rel, pat) for pat in patterns):
                    if len(results) == limit:
                        return results, True
                    results.append(rel)
        return results, False

    def list_files(self, include: str = "*", offset: int = 0, limit: int = 100) -> dict:
        if not 0 <= offset <= 20000 or not 1 <= limit <= 500:
            raise ValueError("offset 0..20000 and limit 1..500 required")
        files, truncated = self.inventory(include)
        page = files[offset : offset + limit]
        return {
            "root": str(self.root),
            "files": page,
            "total": len(files),
            "next_offset": offset + limit if offset + limit < len(files) else None,
            "inventory_truncated": truncated,
        }

    def read_file(self, path: str, start_line: int = 1, end_line: int = 200) -> dict:
        if start_line < 1 or end_line < start_line or end_line - start_line > 1000:
            raise ValueError("Use a positive range of at most 1001 lines")
        data = self.raw(self.path(path))
        if data is None:
            raise FileNotFoundError(path)
        lines = data.decode("utf-8-sig").splitlines()
        excerpt = "\n".join(lines[start_line - 1 : end_line])
        return {
            "path": path,
            "sha256": digest(data),
            "total_lines": len(lines),
            "start_line": start_line,
            "end_line": min(end_line, len(lines)),
            "content": excerpt[:20000],
            "truncated": len(excerpt) > 20000,
        }

    def search(self, query: str, include: str = "*", limit: int = 100) -> dict:
        if not query or len(query) > 200 or not 1 <= limit <= 200:
            raise ValueError("Nonempty query <=200 characters; limit 1..200")
        files, inventory_truncated = self.inventory(include)
        hits, skipped = [], []
        for name in files:
            p = self.path(name)
            if p.suffix.lower() not in TEXT:
                continue
            try:
                data = self.raw(p)
                for number, line in enumerate(
                    (data or b"").decode("utf-8-sig").splitlines(), 1
                ):
                    if query.casefold() in line.casefold():
                        if len(hits) == limit:
                            return {
                                "matches": hits,
                                "truncated": True,
                                "skipped": skipped,
                            }
                        hits.append({"path": name, "line": number, "text": line[:400]})
            except (OSError, ValueError) as exc:
                if len(skipped) < 50:
                    skipped.append({"path": name, "error": str(exc)})
        return {"matches": hits, "truncated": inventory_truncated, "skipped": skipped}

    def state_path(self, kind: str, identifier: str) -> Path:
        if kind not in {"plans", "scans"} or not re.fullmatch(
            "[a-f0-9]{32}", identifier
        ):
            raise ValueError("Invalid operation identifier")
        self.state.mkdir(parents=True, exist_ok=True)
        folder = self.state / kind
        folder.mkdir(exist_ok=True)
        return folder / (identifier + ".json")

    def store(self, kind: str, data: dict) -> None:
        self.atomic(
            self.state_path(kind, data["id"]),
            json.dumps(data, ensure_ascii=False).encode(),
        )

    def load(self, kind: str, identifier: str, owner: str) -> dict:
        data = json.loads(self.state_path(kind, identifier).read_text(encoding="utf-8"))
        if data["owner"] != owner:
            raise PermissionError("Operation belongs to another identity")
        return data

    @staticmethod
    def atomic(p: Path, data: bytes | None) -> None:
        if data is None:
            p.unlink()
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".router-", dir=p.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if p.exists():
                os.chmod(name, stat.S_IMODE(p.stat().st_mode))
            os.replace(name, p)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def audit(self, owner: str, action: str, details: dict) -> None:
        self.state.mkdir(parents=True, exist_ok=True)
        with (self.state / "audit.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {"time": time.time(), "owner": owner, "action": action, **details}
                )
                + "\n"
            )

    def propose(self, changes: list[FileChange], owner: str) -> dict:
        if not 1 <= len(changes) <= 30:
            raise ValueError("A plan must change 1..30 files")
        with self.lock:
            entries, diffs, seen = [], [], set()
            size = 0
            for change in changes:
                p = self.path(change.path)
                key = os.path.normcase(str(p))
                if key in seen:
                    raise ValueError("Duplicate file in plan")
                seen.add(key)
                if p.suffix.lower() not in TEXT:
                    raise ValueError(
                        "Only supported source/text extensions can be changed"
                    )
                before = self.raw(p)
                after = (
                    change.content.encode("utf-8")
                    if change.content is not None
                    else None
                )
                if after is not None and 0 in after:
                    raise ValueError("Binary content is forbidden")
                size += len(before or b"") + len(after or b"")
                if size > 200000 or before == after:
                    raise ValueError(
                        "Plan exceeds 200 KB or contains an unchanged file"
                    )
                rel = p.relative_to(self.root).as_posix()
                delta = (
                    "\n".join(
                        difflib.unified_diff(
                            (before or b"").decode("utf-8-sig").splitlines(),
                            (after or b"").decode("utf-8").splitlines(),
                            fromfile="a/" + rel if before is not None else "/dev/null",
                            tofile="b/" + rel if after is not None else "/dev/null",
                            lineterm="",
                        )
                    )
                    + "\n"
                )
                diffs.append(delta)
                entries.append(
                    {
                        "path": rel,
                        "before": base64.b64encode(before).decode()
                        if before is not None
                        else None,
                        "after": change.content,
                        "before_sha": digest(before),
                        "after_sha": digest(after),
                    }
                )
            identifier = uuid.uuid4().hex
            self.state_path("plans", identifier)
            if len(list((self.state / "plans").glob("*.json"))) >= 500:
                raise RuntimeError(
                    "Plan storage limit reached; archive old plans on the host"
                )
            data = {
                "id": identifier,
                "owner": owner,
                "created": time.time(),
                "status": "proposed",
                "entries": entries,
            }
            self.store("plans", data)
            self.audit(
                owner,
                "propose",
                {"id": identifier, "files": [x["path"] for x in entries]},
            )
            diff = "\n".join(diffs)
            return {
                "plan_id": identifier,
                "diff": diff[:60000],
                "diff_truncated": len(diff) > 60000,
                "files": [
                    {k: e[k] for k in ("path", "before_sha", "after_sha")}
                    for e in entries
                ],
                "expires_in_seconds": 3600,
                "status": "proposed",
            }

    def apply(self, identifier: str, owner: str, *, rollback: bool = False) -> dict:
        with self.lock:
            data = self.load("plans", identifier, owner)
            expected = {"applied"} if rollback else {"proposed"}
            if data["status"] not in expected:
                raise ValueError("Plan is not in the required state")
            if not rollback and time.time() - data["created"] > 3600:
                raise ValueError("Plan expired; create a new diff")
            paths = []
            for e in data["entries"]:
                p = self.path(e["path"])
                current = self.raw(p)
                wanted = e["after_sha"] if rollback else e["before_sha"]
                if digest(current) != wanted:
                    raise ValueError(
                        f"File changed since plan: {e['path']}; refusing overwrite"
                    )
                target = (
                    (base64.b64decode(e["before"]) if e["before"] is not None else None)
                    if rollback
                    else (
                        e["after"].encode("utf-8") if e["after"] is not None else None
                    )
                )
                paths.append((p, current, target))
            data["status"] = "rolling_back" if rollback else "applying"
            self.store("plans", data)
            completed = []
            try:
                for p, current, target in paths:
                    self.path(p.relative_to(self.root).as_posix())
                    self.atomic(p, target)
                    completed.append((p, current))
            except Exception:
                recovery_errors = []
                for p, current in reversed(completed):
                    try:
                        self.atomic(p, current)
                    except OSError as exc:
                        recovery_errors.append(str(exc))
                data["status"] = (
                    "recovery_required"
                    if recovery_errors
                    else ("applied" if rollback else "proposed")
                )
                self.store("plans", data)
                raise
            data["status"] = "rolled_back" if rollback else "applied"
            self.store("plans", data)
            self.audit(
                owner,
                data["status"],
                {"id": identifier, "files": [e["path"] for e in data["entries"]]},
            )
            return {
                "plan_id": identifier,
                "status": data["status"],
                "files": [e["path"] for e in data["entries"]],
            }

    def plan_status(self, identifier: str, owner: str) -> dict:
        data = self.load("plans", identifier, owner)
        return {k: data[k] for k in ("id", "status", "created")} | {
            "files": [e["path"] for e in data["entries"]]
        }

    def recover(self, identifier: str, owner: str) -> dict:
        """Restore original bytes after an interrupted apply/rollback journal."""
        with self.lock:
            data = self.load("plans", identifier, owner)
            if data["status"] not in {"applying", "rolling_back", "recovery_required"}:
                raise ValueError("Plan does not require interrupted-operation recovery")
            entries = []
            for e in data["entries"]:
                p = self.path(e["path"])
                current = self.raw(p)
                if digest(current) not in {e["before_sha"], e["after_sha"]}:
                    raise ValueError(
                        "Unknown subsequent edit; refusing automatic recovery"
                    )
                before = (
                    base64.b64decode(e["before"]) if e["before"] is not None else None
                )
                entries.append((p, current, before))
            for p, current, before in entries:
                if current != before:
                    self.atomic(p, before)
            data["status"] = "rolled_back"
            self.store("plans", data)
            self.audit(owner, "recovered", {"id": identifier})
            return {"plan_id": identifier, "status": "rolled_back"}

    def acquire_server(self) -> None:
        """Permit one MCP process per workspace to prevent cross-process write races."""
        self.state.mkdir(parents=True, exist_ok=True)
        stream = (self.state / "server.lock").open("a+b")
        try:
            if stream.seek(0, 2) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise RuntimeError(
                "Another MCP server owns this workspace. "
                "Stop it or use a different workspace."
            ) from exc
        self._server_lock = stream

    def release_server(self) -> None:
        if self._server_lock is not None:
            self._server_lock.close()
            self._server_lock = None
