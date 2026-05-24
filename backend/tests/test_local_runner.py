import sys

from app.config import Settings
from app.runner import LocalCadRunner


def test_blank_runner_script_setting_uses_default(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_runner_script="",
    )
    runner_script = LocalCadRunner(settings)._runner_script()

    assert runner_script.name == "run_cadquery.py"
    assert runner_script.is_file()


def test_local_runner_invokes_configured_python_script(tmp_path):
    runner_script = tmp_path / "fake_runner.py"
    runner_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "output = Path(sys.argv[2])",
                "output.mkdir(parents=True, exist_ok=True)",
                "(output / 'model.step').write_text('STEP', encoding='utf-8')",
                "(output / 'preview.glb').write_bytes(b'glb')",
                "print('fake export complete')",
            ]
        ),
        encoding="utf-8",
    )
    generated_script = tmp_path / "model.py"
    generated_script.write_text("def build_model():\n    return None\n", encoding="utf-8")

    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        cad_runner_python=sys.executable,
        cad_runner_script=runner_script,
    )
    result = LocalCadRunner(settings).run(generated_script, tmp_path / "out")

    assert result.success is True
    assert result.step_path and result.step_path.read_text(encoding="utf-8") == "STEP"
    assert result.glb_path and result.glb_path.read_bytes() == b"glb"
    assert "fake export complete" in result.stdout
