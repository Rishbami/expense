from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .auth import router as auth_router
from .database import init_db
from .expenses import router as expenses_router
from .reviews import router as reviews_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Expense Claims", lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"


@app.middleware("http")
async def protect_origin(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        expected = urlsplit(str(request.base_url))
        if origin:
            actual = urlsplit(origin)
            if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
                return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # FastAPI's documentation pages load their own CDN assets and inline scripts.
    if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(auth_router)
app.include_router(expenses_router)
app.include_router(reviews_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
