from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .api.v1.router import api_router
from .config import ROOT_DIR, settings
from .db.session import init_db
from .seed import seed_defaults


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_defaults()
    yield


app = FastAPI(title="ChatPhantasm", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.middleware("http")
async def no_cache_html(request, call_next):
    """index.html 禁止缓存，避免前端 hash 资源更新后被旧页面引用而 404"""
    response = await call_next(request)
    path = request.url.path
    if path in ("/",) or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-store"
    return response

# 生产模式：若存在前端构建产物则托管（frontend/dist），含 SPA history 回退
frontend_dist = ROOT_DIR / "frontend" / "dist"
if frontend_dist.exists():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(request: Request, full_path: str):
        dist = frontend_dist.resolve()
        target = (dist / full_path).resolve()
        if full_path and target.is_file() and target.is_relative_to(dist):
            return FileResponse(target)
        return FileResponse(dist / "index.html")