"""Create a source-only pilot release; never include .env, models, logs or Git history."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    files = []
    for directory in ("app", "tests", "docs", ".github/workflows"):
        for path in (root / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in {
                ".py", ".json", ".md", ".yml", ".yaml",
            }:
                files.append(path)
    for name in (
        "pyproject.toml", "requirements.txt", "requirements-dev.txt", "constraints-windows-py311.txt",
        "README.md", "pytest.ini", "ruff.toml", "mypy.ini", ".gitignore", ".env.example",
        "scripts/package_source.py",
    ):
        path = root / name
        if path.exists():
            files.append(path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with ZipFile(args.out, "w", ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            relative = path.relative_to(root).as_posix()
            data = path.read_bytes()
            archive.writestr(relative, data)
            manifest.append(hashlib.sha256(data).hexdigest() + "  " + relative)
        archive.writestr("MANIFEST.sha256", "\n".join(manifest) + "\n")
    print(f"Packaged {len(manifest)} source files: {args.out}")


if __name__ == "__main__":
    main()
