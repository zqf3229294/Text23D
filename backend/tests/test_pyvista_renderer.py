import subprocess
import types
from pathlib import Path

from app.pyvista_renderer import render_stl_preview


ASCII_STL = """solid wedge
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 10 0 0
      vertex 0 10 0
    endloop
  endfacet
endsolid wedge
"""


def test_pyvista_renderer_falls_back_to_software_when_subprocess_fails(
    tmp_path,
    monkeypatch,
):
    mesh_path = tmp_path / "preview.stl"
    output_path = tmp_path / "view.png"
    mesh_path.write_text(ASCII_STL, encoding="utf-8")

    def fake_run(*_args, **_kwargs):
        return types.SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="failed to get valid pixel format",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = render_stl_preview(mesh_path, output_path, window_size=(640, 480))

    assert output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result["renderer"] == "software"
    assert result["triangle_count"] == 1
    assert "failed to get valid pixel format" in result["fallback_reason"]
