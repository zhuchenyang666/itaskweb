# 启动程序内置前后端，关闭程序单独打包。
from pathlib import Path
root=Path(SPECPATH)
icon=str(root/"frontend/public/itime.ico")
start=Analysis([str(root/"backend/desktop_start.py")],pathex=[str(root/"backend")],
    datas=[(str(root/"frontend/dist"),"frontend")],
    hiddenimports=["uvicorn.logging","uvicorn.loops.asyncio","uvicorn.protocols.http.h11_impl","uvicorn.lifespan.on","sqlalchemy.dialects.sqlite.pysqlite"],
    excludes=["tkinter","pytest","httpx","httpx2"])
stop=Analysis([str(root/"backend/desktop_stop.py")],pathex=[str(root/"backend")])
start_exe=EXE(PYZ(start.pure),start.scripts,start.binaries,start.datas,[],name="启动工时服务",console=False,icon=icon,upx=False)
stop_exe=EXE(PYZ(stop.pure),stop.scripts,stop.binaries,stop.datas,[],name="关闭工时服务",console=False,icon=icon,upx=False)
