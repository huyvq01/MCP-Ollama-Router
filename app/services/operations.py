"""Bounded allowlisted checks, explicit Git actions and public
document retrieval."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
import sys
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

import httpx

from app.services.workspace import TEXT, Workspace


class Operations:
    def __init__(self, workspace: Workspace, config):
        self.workspace = workspace
        self.config = config

    def command(self, args: list[str], timeout: int = 60) -> dict:
        if not args or len(args) > 100 or any("\x00" in a for a in args):
            raise ValueError("Invalid command arguments")
        env = os.environ.copy()
        env.update(
            GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never", PYTHONIOENCODING="utf-8"
        )
        kwargs = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        proc = subprocess.Popen(
            args,
            cwd=self.workspace.root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            shell=False,
            **kwargs,
        )
        chunks = bytearray()
        total = 0

        def drain():
            nonlocal total
            assert proc.stdout is not None
            while block := proc.stdout.read(4096):
                total += len(block)
                chunks.extend(block)
                if len(chunks) > 20000:
                    del chunks[:-20000]

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            else:
                import signal

                os.killpg(proc.pid, signal.SIGKILL)
            proc.kill()
            proc.wait(timeout=10)
        reader.join(timeout=5)
        if proc.stdout:
            proc.stdout.close()
        return {
            "exit_code": proc.returncode,
            "output": chunks.decode("utf-8", errors="replace"),
            "output_truncated": total > 20000,
            "timed_out": timed_out,
        }

    def check(self, name: str, owner: str) -> dict:
        commands = self.config.check_commands
        if name not in commands:
            raise ValueError("Unknown check. Available: " + ", ".join(commands))
        args = [sys.executable if x == "{python}" else x for x in commands[name]]
        with self.workspace.lock:
            result = self.command(args, self.config.check_timeout)
            self.workspace.audit(
                owner,
                "check",
                {
                    "name": name,
                    "exit_code": result["exit_code"],
                    "timed_out": result["timed_out"],
                },
            )
            return {"check": name, **result}

    def git(self, args: list[str], timeout: int = 60, *, fail: bool = True) -> dict:
        # Require the configured worktree root, not a parent repository.
        root = str(self.workspace.root)
        base = [
            "git",
            "-c",
            "safe.directory=" + root,
            "-c",
            "core.hooksPath=" + str(self.workspace.state / "no-hooks"),
            "-c",
            "core.quotepath=false",
        ]
        check = self.command(base + ["rev-parse", "--show-toplevel"], 10)
        if (
            check["exit_code"]
            or Path(check["output"].strip()).resolve() != self.workspace.root
        ):
            raise ValueError("Configured workspace must be the Git worktree root")
        result = self.command(base + args, timeout)
        if fail and result["exit_code"]:
            raise RuntimeError("Git failed: " + result["output"][-2000:])
        return result

    def worktree_status(self) -> str:
        result = self.git(["status", "--porcelain", "--untracked-files=all"])
        if result["output_truncated"]:
            raise ValueError("Status is too large; configure .gitignore first")
        state = self.workspace.state
        prefix = (
            state.relative_to(self.workspace.root).as_posix()
            if state.is_relative_to(self.workspace.root)
            else None
        )
        rows = []
        for line in result["output"].splitlines():
            name = line[3:].strip('"')
            if prefix and (name == prefix or name.startswith(prefix + "/")):
                continue
            rows.append(line)
        return "\n".join(rows)

    def status(self) -> dict:
        return {
            "head": self.git(["rev-parse", "HEAD"])["output"].strip(),
            "branch": self.git(["branch", "--show-current"])["output"].strip(),
            "status": self.worktree_status(),
        }

    def diff(self, staged: bool = False, path: str | None = None) -> dict:
        args = ["diff", "--no-ext-diff", "--no-textconv"]
        if staged:
            args.append("--cached")
        if path:
            self.workspace.path(path)
            paths = [path]
            truncated = False
        else:
            names = self.git(args + ["--name-only"])["output"].splitlines()
            paths = []
            for name in names:
                try:
                    p = self.workspace.path(name)
                    if p.suffix.lower() in TEXT:
                        paths.append(name)
                except ValueError:
                    continue
            truncated = len(paths) > 100
            paths = paths[:100]
        if not paths:
            return {
                "exit_code": 0,
                "output": "",
                "output_truncated": False,
                "timed_out": False,
                "files_truncated": False,
            }
        return {**self.git(args + ["--", *paths]), "files_truncated": truncated}

    @staticmethod
    def ref(value: str) -> str:
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,150}", value)
            or ".." in value
            or "@{" in value
            or value.endswith(("/", ".lock"))
        ):
            raise ValueError("Invalid branch/remote name")
        return value

    def remote(self, name: str) -> str:
        self.ref(name)
        if name not in self.git(["remote"])["output"].splitlines():
            raise ValueError("Unknown configured Git remote")
        url = self.git(["remote", "get-url", name])["output"].strip()
        if not (
            url.startswith("https://")
            or re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+", url)
        ):
            raise ValueError(
                "Only configured HTTPS or git@host:path remotes are allowed"
            )
        if url.startswith("https://") and (
            urlsplit(url).username or urlsplit(url).password
        ):
            raise ValueError(
                "Remove inline remote credentials; use Git Credential Manager"
            )
        return url

    def expect_head(self, expected_head: str) -> None:
        if not re.fullmatch("[a-fA-F0-9]{40,64}", expected_head):
            raise ValueError("Provide the exact HEAD hash from git_status")
        if self.git(["rev-parse", "HEAD"])["output"].strip() != expected_head:
            raise ValueError("HEAD changed; review status/diff again")

    def branch(self, name: str, expected_head: str, owner: str) -> dict:
        with self.workspace.lock:
            self.expect_head(expected_head)
            result = self.git(["switch", "-c", self.ref(name)])
            self.workspace.audit(owner, "git_branch", {"branch": name})
            return result

    def commit(
        self, paths: list[str], message: str, expected_head: str, owner: str
    ) -> dict:
        if not paths or len(paths) > 30 or not message.strip() or len(message) > 2000:
            raise ValueError(
                "Provide 1..30 explicit paths and a message <=2000 characters"
            )
        for path in paths:
            self.workspace.path(path)
        with self.workspace.lock:
            self.expect_head(expected_head)
            if self.git(["diff", "--cached", "--name-only"])["output"].strip():
                raise ValueError(
                    "Index already contains staged changes; refusing to mix commits"
                )
            self.git(["add", "--", *paths])
            try:
                result = self.git(["commit", "-m", message, "--no-gpg-sign"])
            except Exception:
                self.git(["reset", "--quiet", "HEAD", "--", *paths], fail=False)
                raise
            self.workspace.audit(owner, "git_commit", {"paths": paths})
            return {"head": self.git(["rev-parse", "HEAD"])["output"].strip(), **result}

    def sync(
        self,
        action: str,
        remote: str,
        branch: str | None,
        expected_head: str | None,
        owner: str,
    ) -> dict:
        if not self.config.enable_git_network:
            raise PermissionError(
                "Set ROUTER_ENABLE_GIT_NETWORK=true on the host first"
            )
        with self.workspace.lock:
            self.remote(remote)
            if action == "fetch":
                args = ["fetch", remote]
            elif action == "pull":
                if expected_head is None or branch is None:
                    raise ValueError("Pull requires expected_head and branch")
                self.expect_head(expected_head)
                if self.worktree_status().strip():
                    raise ValueError("Pull requires a clean worktree")
                current = self.git(["branch", "--show-current"])["output"].strip()
                if current != branch:
                    raise ValueError("Pull branch must match the checked-out branch")
                args = ["pull", "--ff-only", remote, self.ref(branch)]
            elif action == "push":
                if not self.config.enable_publish:
                    raise PermissionError(
                        "Set ROUTER_ENABLE_PUBLISH=true on the host first"
                    )
                if expected_head is None or branch is None:
                    raise ValueError("Push requires expected_head and branch")
                self.expect_head(expected_head)
                current = self.git(["branch", "--show-current"])["output"].strip()
                if branch != current:
                    raise ValueError("Only the current named branch can be pushed")
                if self.worktree_status().strip():
                    raise ValueError("Review/commit local changes before pushing")
                args = ["push", remote, f"HEAD:refs/heads/{self.ref(branch)}"]
            else:
                raise ValueError("action must be fetch, pull or push")
            result = self.git(args, 120)
            self.workspace.audit(
                owner, "git_" + action, {"remote": remote, "branch": branch}
            )
            return result

    async def create_pr(
        self,
        title: str,
        body: str,
        base: str,
        expected_head: str,
        owner: str,
        *,
        client=None,
    ) -> dict:
        if not self.config.enable_publish or not self.config.enable_git_network:
            raise PermissionError(
                "Publishing and Git networking must be enabled on the host"
            )
        token = (
            self.config.github_token.get_secret_value()
            if self.config.github_token
            else ""
        )
        if not token:
            raise PermissionError(
                "Configure ROUTER_GITHUB_TOKEN on the host; never pass "
                "credentials in tool arguments"
            )
        if not 1 <= len(title) <= 200 or len(body) > 20000:
            raise ValueError("Title 1..200 characters; body <=20000")
        with self.workspace.lock:
            self.expect_head(expected_head)
            url = self.remote("origin")
            match = re.fullmatch(
                (
                    "(?:https://github\\.com/|git@github\\.com:)([A-Za-z0-9_.-"
                    "]+)/([A-Za-z0-9_.-]+?)(?:\\.git)?"
                ),
                url,
            )
            if not match:
                raise ValueError(
                    "This PR tool currently supports github.com origin remotes"
                )
            account, repo = match.groups()
            branch = self.git(["branch", "--show-current"])["output"].strip()
            self.ref(base)
            if not branch or branch == base:
                raise ValueError("Use a feature branch different from the base branch")
        own = client is None
        client = client or httpx.AsyncClient(
            timeout=30, trust_env=False, follow_redirects=False
        )
        try:
            headers = {
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            endpoint = f"https://api.github.com/repos/{account}/{repo}/pulls"
            reference = await client.get(
                f"https://api.github.com/repos/{account}/{repo}/git/ref/heads/"
                + quote(branch, safe=""),
                headers=headers,
            )
            reference.raise_for_status()
            if reference.json().get("object", {}).get("sha") != expected_head:
                raise ValueError(
                    "Remote branch does not match reviewed HEAD; push it first"
                )
            existing = await client.get(
                endpoint,
                headers=headers,
                params={"state": "open", "head": f"{account}:{branch}", "base": base},
            )
            existing.raise_for_status()
            rows = existing.json()
            if rows:
                data = rows[0]
            else:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json={
                        "title": title,
                        "body": body,
                        "head": branch,
                        "base": base,
                        "draft": True,
                    },
                )
                response.raise_for_status()
                data = response.json()
            self.workspace.audit(owner, "github_pr", {"number": data["number"]})
            return {
                "url": data["html_url"],
                "number": data["number"],
                "draft": data.get("draft", True),
            }
        finally:
            if own:
                await client.aclose()


class DocumentText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def validate_public_url(url: str, allowed: list[str]) -> str:
    p = urlsplit(url)
    host = (p.hostname or "").casefold()
    if (
        p.scheme != "https"
        or p.username
        or p.password
        or p.port not in {None, 443}
        or host not in allowed
    ):
        raise ValueError("Use HTTPS port 443 on an exact host in ROUTER_DOCUMENT_HOSTS")
    for address in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise ValueError(
                "Private, loopback and reserved network addresses are forbidden"
            )
    return url


async def fetch_document(url: str, allowed: list[str], *, client=None) -> dict:
    own = client is None
    client = client or httpx.AsyncClient(
        timeout=20, trust_env=False, follow_redirects=False
    )
    try:
        for _ in range(4):
            validate_public_url(url, allowed)
            async with client.stream(
                "GET", url, headers={"User-Agent": "MCP-Ollama-Router/1.2"}
            ) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                response.raise_for_status()
                kind = response.headers.get("content-type", "").split(";")[0].strip()
                if kind not in {
                    "text/html",
                    "text/plain",
                    "text/markdown",
                    "application/json",
                    "application/xml",
                    "text/xml",
                }:
                    raise ValueError("Only text/HTML/JSON/XML documents are supported")
                raw = bytearray()
                async for block in response.aiter_bytes():
                    raw.extend(block)
                    if len(raw) > 1_000_000:
                        raise ValueError("Document exceeds 1 MB")
                text = raw.decode(response.encoding or "utf-8", errors="replace")
                if kind == "text/html":
                    parser = DocumentText()
                    parser.feed(text)
                    text = "\n".join(parser.parts)
                return {
                    "url": url,
                    "content": text[:20000],
                    "truncated": len(text) > 20000,
                    "content_type": kind,
                    "untrusted_external_content": True,
                }
        raise ValueError("Too many redirects")
    finally:
        if own:
            await client.aclose()
