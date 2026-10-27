import json

from scripts import portable


def test_generated_configs_handle_spaces_and_machine_paths(tmp_path):
    root = tmp_path / "Project with spaces"
    root.mkdir()
    python = root / ".venv-portable" / "Scripts" / "python.exe"
    portable.write_configs(python, root)
    mcp = json.loads((root / ".local-config" / "mcp.json").read_text())
    server = mcp["mcpServers"]["ollama-router"]
    assert server["command"] == str(python)
    assert server["args"] == ["-m", "app.server", "--coding-tools"]
    assert server["cwd"] == str(root)
    continuation = json.loads(
        (root / ".continue" / "mcpServers" / "new-mcp-server.yaml").read_text()
    )
    assert continuation["mcpServers"][0]["command"] == str(python)


def test_run_anchors_working_directory_and_forwards_arguments(monkeypatch, tmp_path):
    python = tmp_path / "python"
    python.touch()
    monkeypatch.setattr(portable, "environment_python", lambda: python)
    monkeypatch.setattr(portable, "ROOT", tmp_path)
    monkeypatch.setattr(portable.sys, "executable", str(python))
    monkeypatch.setattr(portable.sys, "argv", ["portable.py", "run", "--coding-tools"])
    calls = []
    monkeypatch.setattr(portable.os, "chdir", lambda path: calls.append(path))
    monkeypatch.setattr(
        portable.runpy,
        "run_module",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(portable.sys, "path", list(portable.sys.path))
    assert portable.main() == 0
    assert calls == [tmp_path, (("app.server",), {"run_name": "__main__"})]
    assert portable.sys.argv == ["app.server", "--coding-tools"]


def test_missing_environment_returns_actionable_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(portable, "environment_python", lambda: tmp_path / "missing")
    monkeypatch.setattr(portable.sys, "argv", ["portable.py", "run"])
    assert portable.main() == 1
    assert "setup" in capsys.readouterr().err
