from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


class PyVistaRenderError(RuntimeError):
    pass


def render_stl_preview(
    mesh_path: Path,
    output_path: Path,
    *,
    window_size: tuple[int, int] = (1280, 960),
) -> dict[str, Any]:
    try:
        return _render_stl_preview_pyvista_subprocess(
            mesh_path,
            output_path,
            window_size=window_size,
        )
    except PyVistaRenderError as exc:
        from .software_stl_renderer import render_stl_preview_software

        render_info = render_stl_preview_software(
            mesh_path,
            output_path,
            window_size=window_size,
        )
        render_info["fallback_reason"] = str(exc)
        return render_info


def _render_stl_preview_pyvista_subprocess(
    mesh_path: Path,
    output_path: Path,
    *,
    window_size: tuple[int, int],
) -> dict[str, Any]:
    if not mesh_path.exists() or mesh_path.stat().st_size == 0:
        raise PyVistaRenderError(f"Preview mesh is missing or empty: {mesh_path}")

    env = os.environ.copy()
    env.setdefault("PYVISTA_OFF_SCREEN", "true")
    command = [
        sys.executable,
        "-m",
        "app.pyvista_render_worker",
        str(mesh_path),
        str(output_path),
        str(window_size[0]),
        str(window_size[1]),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired as exc:
        raise PyVistaRenderError("PyVista render subprocess timed out.") from exc
    except OSError as exc:
        raise PyVistaRenderError("Could not start PyVista render subprocess.") from exc

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        if len(details) > 1200:
            details = details[-1200:]
        message = "PyVista render subprocess failed"
        if details:
            message += f": {details}"
        raise PyVistaRenderError(message)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise PyVistaRenderError("PyVista render subprocess did not write a screenshot.")

    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise PyVistaRenderError("PyVista render subprocess returned invalid metadata.") from exc


def _render_stl_preview_pyvista(
    mesh_path: Path,
    output_path: Path,
    *,
    window_size: tuple[int, int],
) -> dict[str, Any]:
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    try:
        import pyvista as pv
    except Exception as exc:  # pragma: no cover - depends on optional install
        raise PyVistaRenderError(
            "PyVista is not installed. Install backend optional dependency "
            "with: python -m pip install -e \".[render]\""
        ) from exc

    if not mesh_path.exists() or mesh_path.stat().st_size == 0:
        raise PyVistaRenderError(f"Preview mesh is missing or empty: {mesh_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        mesh = pv.read(str(mesh_path))
    except Exception as exc:
        raise PyVistaRenderError(f"Could not read preview mesh: {mesh_path}") from exc

    point_count = int(getattr(mesh, "n_points", 0) or 0)
    cell_count = int(getattr(mesh, "n_cells", 0) or 0)
    if point_count == 0 or cell_count == 0:
        raise PyVistaRenderError("Preview mesh has no visible geometry.")

    plotter = None
    try:
        plotter = pv.Plotter(
            off_screen=True,
            shape=(2, 2),
            window_size=window_size,
        )
        for index, (title, view_name) in enumerate(
            [
                ("ISO", "view_isometric"),
                ("TOP", "view_xy"),
                ("FRONT", "view_xz"),
                ("RIGHT", "view_yz"),
            ]
        ):
            row, col = divmod(index, 2)
            plotter.subplot(row, col)
            plotter.set_background("white")
            plotter.add_mesh(
                mesh,
                color="#d9e2ec",
                edge_color="#253041",
                show_edges=True,
                smooth_shading=True,
            )
            plotter.add_bounding_box(color="#7a8699", line_width=1)
            plotter.add_text(title, position="upper_left", font_size=12, color="black")
            getattr(plotter, view_name)()
            plotter.camera.parallel_projection = True
            plotter.reset_camera()
            plotter.camera.zoom(1.12)

        plotter.screenshot(str(output_path), return_img=False)
    except Exception as exc:
        raise PyVistaRenderError("PyVista could not render the preview screenshot.") from exc
    finally:
        if plotter is not None:
            plotter.close()

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise PyVistaRenderError(f"PyVista screenshot was not written: {output_path}")

    return {
        "mesh_path": str(mesh_path),
        "image_path": str(output_path),
        "point_count": point_count,
        "cell_count": cell_count,
        "window_size": list(window_size),
        "views": ["ISO", "TOP", "FRONT", "RIGHT"],
        "renderer": "pyvista",
    }
