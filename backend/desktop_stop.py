import json
import sys
from desktop_control import BASE, stop, message, check_control

if __name__ == "__main__":
    try:
        if "--check" in sys.argv:
            logs=BASE/"logs"
            logs.mkdir(exist_ok=True)
            (logs/"stop-check.json").write_text(json.dumps({"ok":check_control()}),encoding="utf-8")
        else:
            stop()
    except Exception as exc:
        if "--check" not in sys.argv:
            message(f"关闭失败：{exc}",True)
        raise SystemExit(1)
