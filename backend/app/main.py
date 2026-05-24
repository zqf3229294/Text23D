from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .config import Settings, get_settings
from .db import SQLiteRepository
from .providers import create_provider
from .runner import DockerCadRunner
from .service import GenerationService


def create_app(
    settings: Settings | None = None,
    provider=None,
    runner=None,
) -> FastAPI:
    settings = settings or get_settings()
    repository = SQLiteRepository(settings.database_path)
    llm_provider = provider or create_provider(settings)
    cad_runner = runner or DockerCadRunner(settings)
    generation_service = GenerationService(
        settings=settings,
        repository=repository,
        provider=llm_provider,
        runner=cad_runner,
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
    return app


app = create_app()
