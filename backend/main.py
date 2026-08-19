import logging

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from database import init_db, seed_from_json

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

app = FastAPI(title="fyndnot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    seed_from_json()

# Import routers after app creation to avoid circular imports
from routers import auth, datasets, templates, projects
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")

# Serve built frontend as static files
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="frontend_assets")

    @app.get("/favicon.svg")
    def favicon():
        return FileResponse(str(frontend_dist / "favicon.svg"))

    @app.get("/icons.svg")
    def icons():
        return FileResponse(str(frontend_dist / "icons.svg"))

    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        if request.url.path.startswith("/api/") or request.url.path.startswith("/static/"):
            return PlainTextResponse("Not Found", status_code=404)
        index = frontend_dist / "index.html"
        if not index.exists():
            return PlainTextResponse("Not Found", status_code=404)
        return FileResponse(str(index))
