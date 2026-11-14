"""Build the self-contained demo package (folder + zip) handed to reviewers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


PROJECT = Path(__file__).resolve().parent.parent
PACKAGE_NAME = "RealTimeDataPipeline_Demo_Package"

INCLUDE = [
    "src", "tests", "sql", "contracts", "config", "dashboard", "docs", "infra", "scripts",
    "artifacts/powerbi", "artifacts/powerbi_demo",
    "Dockerfile", "docker-compose.yml", "pyproject.toml", ".env.example", ".dockerignore", ".gitignore",
    "Đề bài.txt",
]
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".terraform", ".venv", "package"}
EXCLUDE_FILES = {".env", "localSettings.json", "editorSettings.json"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".tfstate", ".tfplan", ".pbix"}

LAUNCHERS = {
    "1_Open_Dashboard.bat": "open-dashboard.ps1",
    "2_Run_Pipeline_Demo.bat": "run-pipeline-demo.ps1",
    "3_Run_Tests.bat": "run-tests.ps1",
    "4_Stop_Pipeline.bat": "stop-pipeline.ps1",
}


def keep(path: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return False
    if path.name in EXCLUDE_FILES or path.suffix in EXCLUDE_SUFFIXES or path.name.endswith(".tfvars"):
        return False
    return True


def copy_tree(source: Path, target: Path) -> None:
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if path.is_file() and keep(relative):
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target / relative)


def latest_passed_acceptance() -> Path:
    runs = []
    for summary in (PROJECT / "artifacts" / "acceptance").glob("*/acceptance-summary.json"):
        if json.loads(summary.read_text(encoding="utf-8-sig")).get("status") == "passed":
            runs.append(summary.parent)
    if not runs:
        raise FileNotFoundError("No passed acceptance run under artifacts/acceptance")
    return max(runs, key=lambda path: path.name)


def write_launchers(package: Path) -> None:
    for name, script in LAUNCHERS.items():
        body = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\demo\\{script}"\r\n'
            "echo.\r\n"
            "pause\r\n"
        )
        (package / name).write_bytes(body.encode("ascii"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output_dir: Path, overwrite: bool) -> dict[str, object]:
    package = output_dir / PACKAGE_NAME
    zip_path = output_dir / f"{PACKAGE_NAME}.zip"
    if package.resolve().is_relative_to(PROJECT):
        raise ValueError("Build the package outside the project folder")
    if package.exists() or zip_path.exists():
        if not overwrite:
            raise FileExistsError(f"{package} already exists; pass --overwrite to rebuild it")
        shutil.rmtree(package, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
        (output_dir / f"{PACKAGE_NAME}.zip.sha256").unlink(missing_ok=True)

    for item in INCLUDE:
        copy_tree(PROJECT / item, package / item)
    preview = PROJECT / "dashboard_preview"
    if any(preview.glob("*.pdf")) or any(preview.glob("*.png")):
        copy_tree(preview, package / "dashboard_preview")
    acceptance = latest_passed_acceptance()
    copy_tree(acceptance, package / "artifacts" / "acceptance" / acceptance.name)

    docs = PROJECT / "scripts" / "demo" / "package"
    shutil.copy2(docs / "README.md", package / "README.md")
    shutil.copy2(docs / "DEMO_GUIDE.md", package / "DEMO_GUIDE.md")
    shutil.copy2(PROJECT / "README.md", package / "TECHNICAL_README.md")
    write_launchers(package)

    files = sorted(path for path in package.rglob("*") if path.is_file())
    checksums = "".join(f"{sha256(path)}  {path.relative_to(package).as_posix()}\n" for path in files)
    (package / "CHECKSUMS.sha256").write_text(checksums, encoding="utf-8")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                archive.write(path, Path(PACKAGE_NAME) / path.relative_to(package))
    zip_hash = sha256(zip_path)
    (output_dir / f"{PACKAGE_NAME}.zip.sha256").write_text(f"{zip_hash}  {zip_path.name}\n", encoding="utf-8")

    return {
        "package": str(package),
        "zip": str(zip_path),
        "zip_sha256": zip_hash,
        "files": len(files) + 1,
        "zip_mb": round(zip_path.stat().st_size / 1_048_576, 2),
        "acceptance_run": acceptance.name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT.parent)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir.resolve(), args.overwrite), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
