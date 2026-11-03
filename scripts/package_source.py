"""Create a source-only archive for connecting the POC to Git hosting."""

from __future__ import annotations

import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".tmp" / "deployment-source.zip"


def source_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in ("*.py", "*.md", "requirements*.txt"):
        files.update(path for path in ROOT.glob(pattern) if path.is_file())
    for name in (".gitignore", ".python-version", ".env.example", "render.yaml"):
        path = ROOT / name
        if path.is_file():
            files.add(path)
    for folder in ("backend_modules", "pages", "disabled_pages", "tests", "scripts"):
        base = ROOT / folder
        files.update(path for path in base.rglob("*") if path.is_file() and path.suffix.lower() in {".py", ".md", ".pptx"})
    frontend = ROOT / "frontend_modules"
    for current, directories, names in os.walk(frontend):
        directories[:] = [name for name in directories if name not in {"node_modules", "dist", ".npm-cache", ".vercel"}]
        for name in names:
            path = Path(current) / name
            if name == ".env.example" or path.suffix.lower() in {".js", ".jsx", ".css", ".html", ".json", ".md"}:
                files.add(path)
    return sorted(files)


def main() -> None:
    OUTPUT.parent.mkdir(exist_ok=True)
    files = source_files()
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f"Created {OUTPUT} with {len(files)} source files ({OUTPUT.stat().st_size:,} bytes).")


if __name__ == "__main__":
    main()
