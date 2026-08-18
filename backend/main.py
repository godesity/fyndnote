from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import init_db, seed_from_json

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
