from __future__ import annotations

import subprocess
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
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class CadRunner(Protocol):
    def run(self, script_path: Path, output_dir: Path) -> RunnerResult:
        ...


class DockerCadRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, script_path: Path, output_dir: Path) -> RunnerResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "run.log"
        step_path = output_dir / "model.step"
        glb_path = output_dir / "preview.glb"

        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cpus",
            self.settings.cad_runner_cpus,
            "--memory",
            self.settings.cad_runner_memory,
            "-v",
            f"{script_path.resolve()}:/work/model.py:ro",
            "-v",
            f"{output_dir.resolve()}:/work/output",
            self.settings.cad_runner_image,
            "python",
            "/opt/text23d/run_cadquery.py",
            "/work/model.py",
            "/work/output",
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
                "Docker executable was not found on PATH.\n"
                "Install Docker Desktop and build the cad-runner image.\n",
                encoding="utf-8",
            )
            return RunnerResult(
                success=False,
                step_path=None,
                glb_path=None,
                log_path=log_path,
                error=str(exc),
            )


def _format_log(command: list[str], stdout: str, stderr: str) -> str:
    redacted = ["<script-or-output-path>" if "/work/" in part else part for part in command]
    return (
        "Command:\n"
        + " ".join(redacted)
        + "\n\nSTDOUT:\n"
        + stdout
        + "\n\nSTDERR:\n"
        + stderr
        + "\n"
    )
