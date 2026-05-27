from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import Settings


@dataclass
class RunnerResult:
    success: bool
    step_path: Path | None
    glb_path: Path | None
    log_path: Path
    stl_path: Path | None = None
    native_path: Path | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class CadRunner(Protocol):
    def run(self, script_path: Path, output_dir: Path) -> RunnerResult:
        ...


class LocalCadRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, script_path: Path, output_dir: Path) -> RunnerResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "run.log"
        step_path = output_dir / "model.step"
        glb_path = output_dir / "preview.glb"

        command = [
            self.settings.cad_runner_python or sys.executable,
            str(self._runner_script()),
            str(script_path.resolve()),
            str(output_dir.resolve()),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.settings.cad_runner_timeout_seconds,
                check=False,
            )
            log_text = _format_log(command, completed.stdout, completed.stderr)
            log_path.write_text(log_text, encoding="utf-8")
            success = (
                completed.returncode == 0
                and step_path.exists()
                and glb_path.exists()
                and step_path.stat().st_size > 0
                and glb_path.stat().st_size > 0
            )
            return RunnerResult(
                success=success,
                step_path=step_path if step_path.exists() else None,
                glb_path=glb_path if glb_path.exists() else None,
                log_path=log_path,
                stdout=completed.stdout,
                stderr=completed.stderr,
                error=None if success else f"CAD runner exited with {completed.returncode}",
            )
        except subprocess.TimeoutExpired as exc:
            log_path.write_text(
                _format_log(command, exc.stdout or "", exc.stderr or "")
                + f"\nTimed out after {self.settings.cad_runner_timeout_seconds} seconds.\n",
                encoding="utf-8",
            )
            return RunnerResult(
                success=False,
                step_path=None,
                glb_path=None,
                log_path=log_path,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                error="CAD runner timed out.",
            )
        except FileNotFoundError as exc:
            log_path.write_text(
                "Local CadQuery runner could not be started.\n"
                "Check TEXT23D_CAD_RUNNER_PYTHON and TEXT23D_CAD_RUNNER_SCRIPT.\n",
                encoding="utf-8",
            )
            return RunnerResult(
                success=False,
                step_path=None,
                glb_path=None,
                log_path=log_path,
                error=str(exc),
            )

    def _runner_script(self) -> Path:
        if self.settings.cad_runner_script:
            return self.settings.cad_runner_script
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "cad-runner" / "run_cadquery.py"


def create_runner(settings: Settings) -> CadRunner:
    if settings.cad_kernel == "freecad":
        return LocalFreeCADRunner(settings)
    return LocalCadRunner(settings)


class LocalFreeCADRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, script_path: Path, output_dir: Path) -> RunnerResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "run.log"
        step_path = output_dir / "model.step"
        stl_path = output_dir / "preview.stl"
        native_path = output_dir / "model.FCStd"

        command = [
            self.settings.freecad_python or "FreeCADCmd",
            str(self._runner_script()),
            str(script_path.resolve()),
            str(output_dir.resolve()),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.settings.cad_runner_timeout_seconds,
                check=False,
            )
            log_path.write_text(
                _format_log(command, completed.stdout, completed.stderr),
                encoding="utf-8",
            )
            success = (
                completed.returncode == 0
                and step_path.exists()
                and stl_path.exists()
                and native_path.exists()
                and step_path.stat().st_size > 0
                and stl_path.stat().st_size > 0
                and native_path.stat().st_size > 0
            )
            return RunnerResult(
                success=success,
                step_path=step_path if step_path.exists() else None,
                glb_path=None,
                stl_path=stl_path if stl_path.exists() else None,
                native_path=native_path if native_path.exists() else None,
                log_path=log_path,
                stdout=completed.stdout,
                stderr=completed.stderr,
                error=None if success else f"FreeCAD runner exited with {completed.returncode}",
            )
        except subprocess.TimeoutExpired as exc:
            log_path.write_text(
                _format_log(command, exc.stdout or "", exc.stderr or "")
                + f"\nTimed out after {self.settings.cad_runner_timeout_seconds} seconds.\n",
                encoding="utf-8",
            )
            return RunnerResult(
                success=False,
                step_path=None,
                glb_path=None,
                stl_path=None,
                native_path=None,
                log_path=log_path,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                error="FreeCAD runner timed out.",
            )
        except FileNotFoundError as exc:
            log_path.write_text(
                "FreeCAD runner could not be started.\n"
                "Set TEXT23D_FREECAD_PYTHON to FreeCADCmd.exe or a FreeCAD Python executable.\n",
                encoding="utf-8",
            )
            return RunnerResult(
                success=False,
                step_path=None,
                glb_path=None,
                stl_path=None,
                native_path=None,
                log_path=log_path,
                error=str(exc),
            )

    def _runner_script(self) -> Path:
        if self.settings.freecad_runner_script:
            return self.settings.freecad_runner_script
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "freecad-runner" / "run_freecad.py"


def _format_log(command: list[str], stdout: str, stderr: str) -> str:
    redacted = [
        "<script-or-output-path>"
        if part.endswith(("model.py", "run_cadquery.py", "run_freecad.py"))
        or "generations" in part
        else part
        for part in command
    ]
    return (
        "Command:\n"
        + " ".join(redacted)
        + "\n\nSTDOUT:\n"
        + stdout
        + "\n\nSTDERR:\n"
        + stderr
        + "\n"
    )
