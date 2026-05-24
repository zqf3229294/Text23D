import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


RUNNER = Path(__file__).resolve().parents[1] / "run_cadquery.py"


def run_runner(script: Path, output_dir: Path):
    return subprocess.run(
        [sys.executable, str(RUNNER), str(script), str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_invalid_syntax_fails(tmp_path):
    script = tmp_path / "bad.py"
    script.write_text("def build_model(:\n", encoding="utf-8")
    result = run_runner(script, tmp_path / "out")
    assert result.returncode != 0
    assert "SyntaxError" in result.stderr


def test_missing_build_model_fails(tmp_path):
    script = tmp_path / "missing.py"
    script.write_text("VALUE = 1\n", encoding="utf-8")
    result = run_runner(script, tmp_path / "out")
    assert result.returncode != 0
    assert "build_model" in result.stderr


@pytest.mark.skipif(
    importlib.util.find_spec("cadquery") is None,
    reason="CadQuery is only required inside the runner image.",
)
def test_cube_with_hole_exports_step_and_glb(tmp_path):
    script = Path(__file__).resolve().parents[1] / "examples" / "cube_with_hole.py"
    output_dir = tmp_path / "out"
    result = run_runner(script, output_dir)
    assert result.returncode == 0, result.stderr
    assert (output_dir / "model.step").stat().st_size > 0
    assert (output_dir / "preview.glb").stat().st_size > 0
