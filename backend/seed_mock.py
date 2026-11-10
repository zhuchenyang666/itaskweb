import argparse
from datetime import datetime
from pathlib import Path
import sqlite3

from app.database import Database
from app.settings import ROOT, data_root, load_settings
from app.mock import seed_mock, rebalance_mock

def backup_databases(root):
    destination = ROOT / "mock-backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination.mkdir(parents=True)
    for source in root.rglob("*.sqlite3"):
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(source.as_uri()+"?mode=ro", uri=True) as original, sqlite3.connect(target) as copied:
            original.backup(copied)
    return destination

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--rebalance", action="store_true", help="备份后仅调整带模拟标记的工时，保留账号、密码和停用状态")
    options.add_argument("--replace", action="store_true", help="备份后替换旧模拟人员和工时，保留管理员")
    args = parser.parse_args()
    if load_settings()[1] != "local":
        raise SystemExit("模拟数据只能在local环境生成")
    root = data_root().resolve()
    if root.name != "mock" or not root.is_relative_to(ROOT.resolve()):
        raise SystemExit("模拟数据必须位于backend下的mock目录")
    database = Database(root)
    try:
        database.initialize()
        if args.replace or args.rebalance:
            print("数据库备份：", backup_databases(root))
        if args.rebalance:
            print("已调整模拟工时条数：", rebalance_mock(database))
        else:
            seed_mock(database, replace=args.replace)
    finally:
        database.close()
    print("模拟数据库已准备：", root)
