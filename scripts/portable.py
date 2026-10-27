"""Portable bootstrap; requires only Python 3.11+ before setup."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".venv-portable"


def environment_python(root: Path = ENV) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def client_config(python: Path, root: Path) -> dict:
    return {
        "command": str(python),
        "args": ["-m", "app.server", "--coding-tools"],
        "cwd": str(root),
        "env": {"ROUTER_TRANSPORT": "stdio"},
    }


def write_configs(python: Path, root: Path = ROOT) -> None:
    config = client_config(python, root)
    destination = root / ".local-config"
    destination.mkdir(exist_ok=True)
    (destination / "mcp.json").write_text(
        json.dumps({"mcpServers": {"ollama-router": config}}, indent=2) + "\n",
        encoding="utf-8",
    )
    # JSON is also valid YAML; Continue accepts this local YAML file.
    target = root / ".continue" / "mcpServers" / "new-mcp-server.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "name": "Ollama Router MCP",
                "version": "1.0.0",
                "schema": "v1",
                "mcpServers": [
                    {"name": "ollama-router", **config, "connectionTimeout": 60000}
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"MCP configuration: {destination / 'mcp.json'}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "run", "bridge", "config"])
    parser.add_argument("--dev", action="store_true", help="Install development tools")
    args, extra = parser.parse_known_args()
    if args.action in {"setup", "config"} and extra:
        parser.error("unrecognized arguments: " + " ".join(extra))
    python = environment_python()
    if args.action == "setup":
        if sys.version_info < (3, 11):  # noqa: UP036 - bootstrap runs before install
            parser.error("Python 3.11 or later is required")
        if not python.exists():
            venv.EnvBuilder(with_pip=True).create(ENV)
        subprocess.run(
            [str(python), "-m", "pip", "install", "setuptools>=68", "wheel"],
            cwd=ROOT,
            check=True,
        )
        command = [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "-e",
            str(ROOT),
        ]
        if args.dev:
            command.extend(["-r", str(ROOT / "requirements-dev.txt"), "ruff", "mypy"])
        subprocess.run(command, cwd=ROOT, check=True)
        write_configs(python)
        return 0
    if not python.exists():
        print(
            "Run python scripts/portable.py setup on this computer first.",
            file=sys.stderr,
        )
        return 1
    if args.action == "config":
        write_configs(python)
        return 0
    # Stable working directory for relative paths and logging, even from an MCP client.
    os.chdir(ROOT)
    module = "app.server" if args.action == "run" else "app.agent_bridge"
    if Path(sys.executable).resolve() == python.resolve():
        # Keep the MCP client's process alive on Windows; execv can detach it.
        sys.path.insert(0, str(ROOT))
        sys.argv = [module, *extra]
        runpy.run_module(module, run_name="__main__")
        return 0
    return subprocess.call(
        [str(python), str(Path(__file__).resolve()), args.action, *extra]
    )


if __name__ == "__main__":
    raise SystemExit(main())
