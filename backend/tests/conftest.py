from pathlib import Path

import pytest

from app.config import Settings
from app.main import create_app
from app.runner import RunnerResult


class FakeRunner:
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed

    def run(self, script_path: Path, output_dir: Path) -> RunnerResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "run.log"
        log_path.write_text("fake runner log", encoding="utf-8")
        if not self.should_succeed:
            return RunnerResult(
                success=False,
                step_path=None,
                glb_path=None,
                log_path=log_path,
                stderr="fake execution failure",
                error="fake runner failed",
            )
        step_path = output_dir / "model.step"
        glb_path = output_dir / "preview.glb"
        step_path.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
        glb_path.write_bytes(b"glTF")
        return RunnerResult(
            success=True,
            step_path=step_path,
            glb_path=glb_path,
            log_path=log_path,
            stdout="ok",
        )


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        database_path=tmp_path / "text23d.sqlite3",
        storage_dir=tmp_path / "artifacts",
        llm_provider="mock",
    )


@pytest.fixture
def app(test_settings):
    return create_app(settings=test_settings, runner=FakeRunner())
