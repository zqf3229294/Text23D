from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .agent import CADAgent
from .api import router
from .config import Settings, get_settings
from .db import SQLiteRepository
from .freecad_agent import FreeCADSessionManager
from .providers import create_provider
from .runner import create_runner
from .service import GenerationService


def _frontend_dist_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "dist"
        / "text23d-frontend"
        / "browser"
    )


def create_app(
    settings: Settings | None = None,
    provider=None,
    runner=None,
) -> FastAPI:
    settings = settings or get_settings()
    repository = SQLiteRepository(settings.database_path)
    llm_provider = provider or create_provider(settings)
    cad_runner = runner or create_runner(settings)
    freecad_sessions = FreeCADSessionManager(settings, cad_runner)
    cad_agent = CADAgent(settings, repository, freecad_sessions)
    generation_service = GenerationService(
        settings=settings,
        repository=repository,
        provider=llm_provider,
        runner=cad_runner,
        agent=cad_agent,
    )

    app = FastAPI(title="Text23D Mechanical API", version="0.1.0")
    app.state.settings = settings
    app.state.repository = repository
    app.state.generation_service = generation_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(router)

    frontend_dist = _frontend_dist_dir()
    if frontend_dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=frontend_dist, html=True),
            name="frontend",
        )

    return app


app = create_app()
