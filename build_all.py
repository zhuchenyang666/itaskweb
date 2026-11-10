from contextlib import closing
from datetime import datetime
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def copy_database(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original, \
            closing(sqlite3.connect(destination)) as copied:
        original.backup(copied)


def clean_outputs():
    targets = [ROOT / "build/package", ROOT / "frontend/dist"]
    # 先校验全部目标，再删除；禁止链接跳出项目目录。
    for target in targets:
        resolved = target.resolve()
        if target.is_symlink() or target.is_junction() or not resolved.is_relative_to(ROOT.resolve()):
            raise ValueError(f"拒绝清理项目外目录或目录链接：{target}")
    for target in targets:
        if target.exists():
            shutil.rmtree(target)


def copy_release_data(package):
    import yaml

    backend = ROOT / "backend"
    config_path = backend / "resources/config.yaml"
    if not config_path.is_file():
        config_path = config_path.with_name("config.example.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    server = config["server"]
    server["active"] = "production"
    relative = Path(server["environments"]["production"].get("data-dir", "data"))
    source = (backend / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not source.is_relative_to(backend.resolve()):
        raise ValueError("正式数据目录必须位于backend内")
    mock_dirs = {"mock", "mock-backups"}
    if any(part.lower() in mock_dirs for part in source.relative_to(backend.resolve()).parts):
        raise ValueError("正式数据目录不能指向模拟数据库")

    resources = package / "backend/resources"
    shutil.copytree(backend / "resources", resources, ignore=shutil.ignore_patterns("config.example.yaml"))
    (resources / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                                           encoding="utf-8")
    for database in source.rglob("*.sqlite3"):
        path = database.relative_to(source)
        if not any(part.lower() in mock_dirs for part in path.parts):
            copy_database(database, package / "backend" / relative / path)


def main():
    os.chdir(ROOT)
    python = ROOT / ".venv/Scripts/python.exe"
    if not python.is_file():
        python = Path(sys.executable)
    if python.resolve() != Path(sys.executable).resolve():
        subprocess.run([str(python), str(Path(__file__).resolve())], check=True)
        return
    if not shutil.which("npm.cmd"):
        raise RuntimeError("打包电脑需要安装Node.js，并将npm添加到PATH")
    subprocess.run([str(python), "-c", "import PyInstaller, yaml"], check=True)
    clean_outputs()
    package = ROOT / "release" / datetime.now().strftime("iTime-%Y%m%d-%H%M%S-%f")
    package.mkdir(parents=True, exist_ok=False)
    subprocess.run(["npm.cmd", "run", "build"], cwd=ROOT / "frontend", check=True)
    subprocess.run(
        [str(python), "-m", "PyInstaller", "--clean", "--noconfirm", "--distpath", str(package), "--workpath",
         str(ROOT / "build/package"), "itime.spec"], check=True)
    copy_release_data(package)
    shutil.copy2(ROOT / "PACKAGING.md", package / "使用说明.md")
    print("发布目录：", package)


if __name__ == "__main__":
    main()
