from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import router
from .database import Database
from .models import User
from .security import hash_password
from .settings import data_root, load_settings
from .business import router as business_router


def create_app(data_dir: Path | None = None):
    database = Database(data_dir or data_root())
    server, _, _ = load_settings()

    @asynccontextmanager
    async def lifespan(app):
        database.initialize()
        with Session(database.accounts) as db:
            if not db.scalar(select(User).where(User.username == "admin")):
                db.add(User(username="admin", name="管理员", position="管理员", role="admin", password_hash=hash_password("123456")))
                db.commit()
        app.state.dummy_password = hash_password("invalid-login")
        yield
        database.close()

    app = FastAPI(title=server["title"], version=str(server["version"]), root_path=server.get("rootpath", "/").rstrip("/"), lifespan=lifespan)
    app.state.database = database

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "不允许跨站请求"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    app.include_router(router)
    app.include_router(business_router)
    return app


app = create_app()
