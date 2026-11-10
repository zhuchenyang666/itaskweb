"""一次性将旧版人员账号迁移为姓名全拼。"""

import argparse
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

from app.mock import PEOPLE, write_roster
from app.security import hash_password, verify_password
from app.settings import ROOT


def migrate(source: Path, backup: Path) -> int:
    old_accounts = {f"{legacy}@hengbao.com": username for _, legacy, username in PEOPLE}
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=rw", uri=True)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        users = db.execute("SELECT id, username, password_hash FROM users WHERE role = 'user'").fetchall()
        occupied = {username.lower() for _, username, _ in users}
        changes = [(user_id, old_accounts[username.lower()], password)
                   for user_id, username, password in users if username.lower() in old_accounts]
        if unknown := [name for name in occupied if "@" in name and name not in old_accounts]:
            raise ValueError(f"以下旧账号没有全拼映射：{', '.join(sorted(unknown))}")
        if conflicts := occupied.intersection(username for _, username, _ in changes):
            raise ValueError(f"全拼账号已存在：{', '.join(sorted(conflicts))}")
        if not changes:
            return 0

        backup.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(backup)) as copied:
                original.backup(copied)

        for user_id, username, password in changes:
            if not verify_password("123456", password):
                password = hash_password("123456")
            db.execute("UPDATE users SET username = ?, password_hash = ?, must_change_password = 1 WHERE id = ?",
                       (username, password, user_id))
            db.execute("DELETE FROM login_sessions WHERE user_id = ?", (user_id,))
        return len(changes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("databases", nargs="+", type=Path, help="待迁移的 accounts.sqlite3 路径")
    args = parser.parse_args()
    backups = ROOT / "account-backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for index, source in enumerate(args.databases, start=1):
        backup = backups / f"{index}-{source.parent.name}.sqlite3"
        count = migrate(source, backup)
        if (source.parent / "人员账号清单.csv").is_file():
            write_roster(source.parent)
        print(f"{source}：迁移 {count} 个账号" + (f"，备份至 {backup}" if count else ""))
