from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.db import init_db, make_engine, make_session_factory
from app.operator import AuthMiddleware, LanAccessMiddleware
from app.paths import frontend_dist, session_secret
from app.routers import catalog, dashboard, office, ops, orders, reports, shop
from app.seed import seed_if_empty


def create_app(db_url: str | None = None) -> FastAPI:
    engine = make_engine(db_url)
    SessionLocal = make_session_factory(engine)
    init_db(engine)
    with SessionLocal() as db:
        seed_if_empty(db)

    app = FastAPI(title="Inventory Manager", version="0.1.0")
    app.state.engine = engine
    app.state.SessionLocal = SessionLocal

    secret = session_secret()
    app.add_middleware(AuthMiddleware)
    app.add_middleware(LanAccessMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site="lax")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(shop.router)
    app.include_router(catalog.router)
    app.include_router(orders.router)
    app.include_router(dashboard.router)
    app.include_router(ops.router)
    app.include_router(office.router)
    app.include_router(reports.router)

    web = frontend_dist()
    if web.is_dir():
        assets = web / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str):
            if full_path.startswith("api/") or full_path == "api":
                raise HTTPException(status_code=404, detail="Not found")
            candidate = web / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            index = web / "index.html"
            if index.is_file():
                return FileResponse(index)
            raise HTTPException(status_code=404, detail="Frontend not built")

    return app
