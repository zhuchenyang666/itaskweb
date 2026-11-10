import asyncio
from contextlib import closing, redirect_stderr, redirect_stdout
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
import webbrowser

from desktop_control import BASE, NAME, kernel, message, check_control
from desktop_logs import DailyLog, maintain_logs
import ctypes

def packaged_app(data_dir=None):
    from app.main import create_app
    from fastapi.staticfiles import StaticFiles
    frontend = (Path(sys._MEIPASS) if getattr(sys, "frozen", False) else BASE) / "frontend"
    if not (frontend / "index.html").is_file():
        raise FileNotFoundError("缺少前端构建文件，请重新打包工时服务。")
    app = create_app(data_dir)
    app.mount("/",StaticFiles(directory=frontend,html=True),name="frontend")
    return app

async def check_app():
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import User
    with tempfile.TemporaryDirectory() as folder:
        app = packaged_app(Path(folder))
        async with app.router.lifespan_context(app):
            with Session(app.state.database.accounts) as db:
                assert db.scalar(select(User).where(User.username=="admin")).role == "admin"
            for path in ("/", "/api/auth/me", "/api/records/suggestions"):
                messages=[]
                received=False
                async def receive():
                    nonlocal received
                    if not received:
                        received=True
                        return {"type":"http.request","body":b"","more_body":False}
                    await asyncio.Event().wait()
                async def send(msg):
                    messages.append(msg)
                await app({"type":"http","asgi":{"version":"3.0","spec_version":"2.4"},"http_version":"1.1","method":"GET","scheme":"http","path":path,"raw_path":path.encode(),"query_string":b"","headers":[(b"host",b"localhost")],"client":("127.0.0.1",1),"server":("127.0.0.1",5173),"root_path":""},receive,send)
                expected=200 if path=="/" else 401
                assert messages[0]["status"] == expected, messages
    return {"ok":True,"control":check_control(),"python":sys.version,"frontend":True,"database":True,"api":True}

def show_startup(url, open_browser):
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            logging.exception("无法自动打开浏览器")
    message(f"前端服务已启动。\n访问地址：{url}")


def start(logs, streams):
    import uvicorn
    from app.settings import load_settings
    server_config,_,_=load_settings()
    desktop=server_config.get("desktop",{})
    log_config=desktop.get("logs",{})
    cleanup_time=datetime.strptime(log_config.get("cleanup-time", "01:00"), "%H:%M").time()
    retention_days=log_config.get("retention-days", 7)
    if type(retention_days) is not int or retention_days < 1:
        raise ValueError("日志保留天数必须是正整数")
    host=desktop.get("listen-host","0.0.0.0")
    port=int(desktop.get("port",5173))
    if not 1 <= port <= 65535: raise ValueError("服务端口必须在1至65535之间")
    browser_host=desktop.get("browser-host","127.0.0.1")
    url=f"http://{browser_host}:{port}/"
    mutex=kernel.CreateMutexW(None,True,NAME+"-running")
    if not mutex: raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:
        kernel.CloseHandle(mutex)
        message("服务已经在运行，无需重复启动。")
        return
    event=None
    finished=threading.Event()
    thread=maintenance=None
    try:
        event=kernel.CreateEventW(None,True,False,NAME+"-stop")
        if not event: raise ctypes.WinError(ctypes.get_last_error())
        app=packaged_app()
        config=uvicorn.Config(app,host=host,port=port,reload=False,workers=1,log_config=None,loop="asyncio",http="h11",ws="none",timeout_graceful_shutdown=25)
        server=uvicorn.Server(config)
        def watch():
            announced=False
            while not finished.wait(.1):
                if kernel.WaitForSingleObject(event,0)==0:
                    server.should_exit=True
                    return
                if server.started and not announced:
                    announced=True
                    # 提示窗口未关闭时，仍需监听停止请求。
                    threading.Thread(target=show_startup, args=(url, desktop.get("open-browser",True)), daemon=True).start()
        thread=threading.Thread(target=watch,daemon=True)
        thread.start()
        maintenance=threading.Thread(target=maintain_logs,args=(logs,streams,cleanup_time,retention_days,finished),daemon=True)
        maintenance.start()
        try:
            server.run()
        except SystemExit as exc:
            if exc.code:
                raise RuntimeError(f"无法启动服务，请检查端口 {port} 是否被占用。") from exc
    finally:
        finished.set()
        if thread: thread.join(timeout=2)
        if maintenance: maintenance.join(timeout=2)
        if event: kernel.CloseHandle(event)
        kernel.ReleaseMutex(mutex)
        kernel.CloseHandle(mutex)

def main():
    logs=BASE/"logs"
    logs.mkdir(exist_ok=True)
    # 无控制台程序的标准输出为None，第三方库仍可能尝试写入。
    with closing(DailyLog(logs,"server")) as server_log, closing(DailyLog(logs,"console")) as console_log, \
            redirect_stdout(console_log), redirect_stderr(console_log):
        handler=logging.StreamHandler(server_log)
        logging.basicConfig(level=logging.INFO,handlers=[handler],format="%(asctime)s %(levelname)s %(message)s")
        try:
            if "--check" in sys.argv:
                result=asyncio.run(check_app())
                (logs/"check.json").write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
            else:
                start(logs,(server_log,console_log))
        except Exception as exc:
            logging.exception("启动失败")
            if "--check" in sys.argv:
                (logs/"check.json").write_text(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False),encoding="utf-8")
            else:
                message(f"启动失败：{exc}\n详情见 logs/{Path(server_log.stream.name).name}。",True)
            raise SystemExit(1)
        finally:
            logging.getLogger().removeHandler(handler)
            handler.close()

if __name__=="__main__":
    main()
