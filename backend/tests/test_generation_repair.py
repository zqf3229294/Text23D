import asyncio

from app.db import SQLiteRepository
from app.models import GenerationStatus, MessageRole
from app.providers.base import CADGenerationResponse
from app.service import GenerationService
from tests.conftest import FakeRunner


class RepairingProvider:
    def __init__(self):
        self.calls = 0

    async def generate_cad(self, messages, previous_error=None):
        self.calls += 1
        if self.calls == 1:
            return CADGenerationResponse(
                assistant_summary="bad script",
                code="import os\n\ndef build_model():\n    return os.getcwd()\n",
            )
        return CADGenerationResponse(
            assistant_summary="fixed script",
            code='import cadquery as cq\n\ndef build_model():\n    return cq.Workplane("XY").box(1, 1, 1)\n',
        )


def test_generation_retries_after_validation_failure(test_settings):
    repository = SQLiteRepository(test_settings.database_path)
    conversation = repository.create_conversation()
    repository.create_message(
        conversation["id"],
        MessageRole.user,
        "make a cube",
    )
    generation = repository.create_generation(conversation["id"], "make a cube")
    provider = RepairingProvider()
    service = GenerationService(
        test_settings,
        repository,
        provider,
        FakeRunner(),
    )

    asyncio.run(service.run_generation(generation["id"]))

    updated = repository.get_generation(generation["id"])
    assert updated["status"] == GenerationStatus.succeeded.value
    assert updated["attempt_count"] == 2
    assert provider.calls == 2
