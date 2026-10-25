from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
from pydantic import SecretStr

from app.core.settings import Settings
from app.security import build_auth
from app.services.operations import Operations, fetch_document, validate_public_url
from app.services.review import RepositoryReview, split_source
from app.services.workspace import FileChange, Workspace


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_bytes(b'print("old")\r\n')
    return Workspace(root)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.py",
        "/etc/passwd",
        "C:/Windows/test.py",
        r"..\escape.py",
        r".git\config",
        ".git/config",
        ".env",
        ".env.local",
        ".venv-31210/a.py",
        "a.py:stream",
        "CON.py",
        "sub/../../x.py",
        "a.py\nb.py",
        "file.py.",
        "secret.txt",
        "key.pem",
    ],
)
def test_confined_paths(workspace, path):
    with pytest.raises(ValueError):
        workspace.path(path)


def test_backslash_is_normalized_and_blocks_hidden_parent(workspace):
    assert workspace.path(r"sub\file.py") == workspace.root / "sub" / "file.py"
    with pytest.raises(ValueError):
        workspace.path(r"sub\..\main.py")


def test_symlink_and_hardlink_denied(workspace, tmp_path):
    external = tmp_path / "outside.py"
    external.write_text("private")
    try:
        (workspace.root / "link.py").symlink_to(external)
    except OSError:
        pass
    else:
        with pytest.raises(ValueError, match="Symlink"):
            workspace.path("link.py")
    try:
        os.link(external, workspace.root / "hard.py")
    except OSError:
        pass
    else:
        with pytest.raises(ValueError, match="Hard-linked"):
            workspace.path("hard.py")


def test_listing_pagination_search_and_exclusions(workspace):
    (workspace.root / ".env").write_text("TOKEN=private")
    (workspace.root / ".venv").mkdir()
    (workspace.root / ".venv" / "skip.py").write_text("private")
    (workspace.root / "other.py").write_text('print("two")\n')
    first = workspace.list_files("*.py", 0, 1)
    assert first["files"] == ["main.py"]
    assert first["next_offset"] == 1
    assert workspace.list_files("*.py", 1, 1)["files"] == ["other.py"]
    assert workspace.search("PRINT")["matches"][0]["line"] == 1
    assert workspace.search("private")["matches"] == []
    assert workspace.read_file("main.py")["total_lines"] == 1


def test_propose_apply_rollback_exact_bytes_and_owner(workspace):
    before = (workspace.root / "main.py").read_bytes()
    plan = workspace.propose(
        [
            FileChange(path="main.py", content='print("new")\n'),
            FileChange(path="new/file.java", content="class Hello {}\n"),
        ],
        "alice",
    )
    assert 'print("new")' in plan["diff"]
    assert (workspace.root / "main.py").read_bytes() == before
    with pytest.raises(PermissionError):
        workspace.apply(plan["plan_id"], "bob")
    assert workspace.apply(plan["plan_id"], "alice")["status"] == "applied"
    assert (workspace.root / "new/file.java").exists()
    assert (
        workspace.apply(plan["plan_id"], "alice", rollback=True)["status"]
        == "rolled_back"
    )
    assert (workspace.root / "main.py").read_bytes() == before
    assert not (workspace.root / "new/file.java").exists()
    assert len((workspace.state / "audit.jsonl").read_text().splitlines()) == 3


def test_delete_and_rollback(workspace):
    plan = workspace.propose([FileChange(path="main.py", content=None)], "a")
    workspace.apply(plan["plan_id"], "a")
    assert not (workspace.root / "main.py").exists()
    workspace.apply(plan["plan_id"], "a", rollback=True)
    assert (workspace.root / "main.py").exists()


def test_stale_apply_never_partially_writes(workspace):
    (workspace.root / "other.py").write_text("old\n")
    plan = workspace.propose(
        [
            FileChange(path="main.py", content="new"),
            FileChange(path="other.py", content="new"),
        ],
        "a",
    )
    (workspace.root / "other.py").write_text("user edit\n")
    with pytest.raises(ValueError, match="File changed"):
        workspace.apply(plan["plan_id"], "a")
    assert (workspace.root / "main.py").read_bytes() == b'print("old")\r\n'


def test_rollback_refuses_subsequent_edits(workspace):
    plan = workspace.propose([FileChange(path="main.py", content="new")], "a")
    workspace.apply(plan["plan_id"], "a")
    (workspace.root / "main.py").write_text("user edit")
    with pytest.raises(ValueError, match="File changed"):
        workspace.apply(plan["plan_id"], "a", rollback=True)
    assert (workspace.root / "main.py").read_text() == "user edit"


def test_expired_or_duplicate_plan_rejected(workspace):
    with pytest.raises(ValueError, match="Duplicate"):
        workspace.propose(
            [
                FileChange(path="main.py", content="a"),
                FileChange(path="main.py", content="b"),
            ],
            "a",
        )
    p = workspace.propose([FileChange(path="main.py", content="a")], "a")
    state = workspace.load("plans", p["plan_id"], "a")
    state["created"] = time.time() - 3601
    workspace.store("plans", state)
    with pytest.raises(ValueError, match="expired"):
        workspace.apply(p["plan_id"], "a")


def test_write_failure_restores_earlier_files(workspace, monkeypatch):
    (workspace.root / "other.py").write_text("old")
    plan = workspace.propose(
        [
            FileChange(path="main.py", content="new"),
            FileChange(path="other.py", content="new"),
        ],
        "a",
    )
    original = workspace.atomic

    def fail(p, data):
        if p.name == "other.py" and data == b"new":
            raise OSError("simulated")
        return original(p, data)

    monkeypatch.setattr(workspace, "atomic", fail)
    with pytest.raises(OSError):
        workspace.apply(plan["plan_id"], "a")
    assert (workspace.root / "main.py").read_bytes() == b'print("old")\r\n'
    assert workspace.plan_status(plan["plan_id"], "a")["status"] == "proposed"


@pytest.mark.parametrize("text", ["a\nb\n", "x" * 10000, "xin chào\n" * 1000, ""])
def test_scan_chunks_cover_all_characters(text):
    parts = split_source(text)
    assert "".join(p["content"] for p in parts) == text
    assert all(len(p["content"].encode("utf-8")) <= 1400 for p in parts)


async def test_scan_resume_owner_and_changed_file(workspace):
    router = AsyncMock()
    router.clear = lambda _: None
    router.metrics = lambda _: {"finish_reason": "stop"}
    router.chat.return_value = "No issue"
    scanner = RepositoryReview(workspace, router)
    job = scanner.start("a", "*.py")
    with pytest.raises(PermissionError):
        scanner.status(job["scan_id"], "b")
    result = await scanner.step(job["scan_id"], "a")
    assert result["status"] == "completed"
    assert result["result"]["review"] == "No issue"
    job2 = scanner.start("a", "*.py")
    (workspace.root / "main.py").write_text("changed")
    result = await scanner.step(job2["scan_id"], "a")
    assert result["status"] == "retry_required"
    assert scanner.status(job2["scan_id"], "a")["processed"] == 0


def config_for(workspace, **kwargs):
    return Settings(_env_file=None, workspace_root=workspace.root, **kwargs)


def test_checks_allowlist_output_and_timeout(workspace):
    ops = Operations(
        workspace,
        config_for(
            workspace,
            check_timeout=1,
            check_commands={
                "small": ["{python}", "-c", 'print("ok")'],
                "noisy": ["{python}", "-c", 'print("x"*50000)'],
                "sleep": ["{python}", "-c", "import time; time.sleep(20)"],
            },
        ),
    )
    assert ops.check("small", "a")["exit_code"] == 0
    assert ops.check("noisy", "a")["output_truncated"]
    assert len(ops.check("noisy", "a")["output"]) <= 20000
    with pytest.raises(ValueError):
        ops.check("rm -rf /", "a")
    assert ops.check("sleep", "a")["timed_out"]


@pytest.fixture
def git_ops(workspace):
    for args in [
        ["init", "-b", "main"],
        ["config", "user.email", "test@example.invalid"],
        ["config", "user.name", "Test"],
        ["add", "main.py"],
        ["commit", "-m", "initial"],
    ]:
        subprocess.run(
            ["git", "-c", "safe.directory=" + str(workspace.root), *args],
            cwd=workspace.root,
            check=True,
            capture_output=True,
        )
    return Operations(workspace, config_for(workspace))


def test_git_branch_commit_head_and_disabled_publish(git_ops):
    ops = git_ops
    head = ops.status()["head"]
    ops.branch("feature/test", head, "a")
    (ops.workspace.root / "main.py").write_text("new\n")
    assert "new" in ops.diff(path="main.py")["output"]
    result = ops.commit(["main.py"], "change", head, "a")
    assert result["head"] != head
    with pytest.raises(ValueError, match="HEAD changed"):
        ops.commit(["main.py"], "stale", head, "a")
    with pytest.raises(PermissionError):
        ops.sync("push", "origin", "feature/test", result["head"], "a")


def test_git_commit_preserves_preexisting_index(git_ops):
    ops = git_ops
    (ops.workspace.root / "main.py").write_text("new\n")
    ops.git(["add", "main.py"])
    with pytest.raises(ValueError, match="already"):
        ops.commit(["main.py"], "test", ops.status()["head"], "a")
    assert ops.git(["diff", "--cached", "--name-only"])["output"].strip() == "main.py"


def public_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://docs.mendix.com/a",
        "https://127.0.0.1/a",
        "https://evil.invalid/a",
        "https://user:pass@docs.mendix.com/a",
        "https://docs.mendix.com:444/a",
    ],
)
def test_document_url_restrictions(url):
    with pytest.raises(ValueError):
        validate_public_url(url, ["docs.mendix.com"])


def test_private_dns_rejected(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    with pytest.raises(ValueError, match="Private"):
        validate_public_url("https://docs.mendix.com/a", ["docs.mendix.com"])


async def test_document_html_and_redirect_validation(monkeypatch):
    public_dns(monkeypatch)

    def handler(request):
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "https://evil.invalid/x"})
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<h1>Docs</h1><script>bad()</script><p>Text</p>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_document(
            "https://docs.mendix.com/a", ["docs.mendix.com"], client=client
        )
        assert result["content"] == "Docs\nText"
        assert result["untrusted_external_content"]
        with pytest.raises(ValueError):
            await fetch_document(
                "https://docs.mendix.com/redirect", ["docs.mendix.com"], client=client
            )


async def test_document_size_limit(monkeypatch):
    public_dns(monkeypatch)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, headers={"content-type": "text/plain"}, content=b"x" * 1_000_001
            )
        )
    ) as client:
        with pytest.raises(ValueError, match="1 MB"):
            await fetch_document(
                "https://docs.mendix.com/a", ["docs.mendix.com"], client=client
            )


def http_config(**kwargs):
    return Settings(
        _env_file=None, transport="http", jwt_secret=SecretStr("a" * 48), **kwargs
    )


def token(config, **overrides):
    now = int(time.time())
    claims = {
        "sub": "alice",
        "client_id": "alice",
        "iss": config.jwt_issuer,
        "aud": config.jwt_audience,
        "iat": now,
        "exp": now + 600,
        "scope": "chat repo:read",
    }
    claims.update(overrides)
    return jwt.encode(claims, config.jwt_secret.get_secret_value(), algorithm="HS256")


async def test_jwt_expiry_issuer_and_audience():
    config = http_config()
    verifier = build_auth(config)
    assert await verifier.verify_token(token(config))
    assert await verifier.verify_token(token(config, exp=int(time.time()) - 1)) is None
    assert await verifier.verify_token(token(config, aud="other")) is None
    assert await verifier.verify_token(token(config, iss="other")) is None


def test_http_configuration_requires_secret_and_tls():
    with pytest.raises(ValueError, match="at least 32"):
        build_auth(Settings(_env_file=None, transport="http"))
    with pytest.raises(ValueError, match="HTTPS"):
        build_auth(http_config(http_public_url="http://server.example"))
    with pytest.raises(ValueError, match="wildcards"):
        build_auth(http_config(http_allowed_hosts=["*"]))


def test_interrupted_apply_recovery(workspace):
    plan = workspace.propose(
        [
            FileChange(path="main.py", content="new"),
            FileChange(path="new.py", content="created"),
        ],
        "a",
    )
    state = workspace.load("plans", plan["plan_id"], "a")
    state["status"] = "applying"
    workspace.store("plans", state)
    (workspace.root / "main.py").write_text("new")
    assert workspace.recover(plan["plan_id"], "a")["status"] == "rolled_back"
    assert (workspace.root / "main.py").read_bytes() == b'print("old")\r\n'
    assert not (workspace.root / "new.py").exists()


def test_diff_filters_environment_contents(git_ops):
    ops = git_ops
    (ops.workspace.root / ".env").write_text("TOKEN=old")
    ops.git(["add", ".env"])
    ops.git(["commit", "-m", "fixture"])
    (ops.workspace.root / ".env").write_text("TOKEN=DO_NOT_RETURN")
    (ops.workspace.root / "main.py").write_text("changed\n")
    result = ops.diff()
    assert "changed" in result["output"]
    assert "DO_NOT_RETURN" not in result["output"]


async def test_draft_github_pr_uses_reviewed_remote_head(git_ops):
    ops = git_ops
    head = ops.status()["head"]
    ops.branch("feature/pr", head, "a")
    ops.git(["remote", "add", "origin", "https://github.com/example/demo.git"])
    ops.config.enable_publish = True
    ops.config.enable_git_network = True
    ops.config.github_token = SecretStr("test-token")
    calls = []

    def handler(request):
        calls.append(request)
        if "/git/ref/heads/" in request.url.path:
            return httpx.Response(200, json={"object": {"sha": head}})
        if request.method == "GET":
            return httpx.Response(200, json=[])
        payload = json.loads(request.content)
        assert payload["draft"] is True
        assert payload["head"] == "feature/pr"
        return httpx.Response(
            201,
            json={
                "number": 1,
                "html_url": "https://github.com/example/demo/pull/1",
                "draft": True,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ops.create_pr("Review", "Body", "main", head, "a", client=client)
    assert result["draft"]
    assert len(calls) == 3


async def test_wrong_remote_head_prevents_pr(git_ops):
    ops = git_ops
    head = ops.status()["head"]
    ops.branch("feature/pr", head, "a")
    ops.git(["remote", "add", "origin", "https://github.com/example/demo.git"])
    ops.config.enable_publish = True
    ops.config.enable_git_network = True
    ops.config.github_token = SecretStr("test-token")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"object": {"sha": "0" * 40}})
        )
    ) as client:
        with pytest.raises(ValueError, match="Remote branch"):
            await ops.create_pr("Review", "Body", "main", head, "a", client=client)


def test_single_server_lock_released(workspace):
    other = Workspace(workspace.root)
    workspace.acquire_server()
    try:
        with pytest.raises(RuntimeError, match="Another MCP server"):
            other.acquire_server()
    finally:
        workspace.release_server()
    other.acquire_server()
    other.release_server()


def test_git_state_is_not_a_source_change(git_ops):
    ops = git_ops
    ops.workspace.audit("a", "test", {})
    assert ops.status()["status"] == ""
    (ops.workspace.root / "extra.py").write_text("user change")
    assert "extra.py" in ops.status()["status"]
