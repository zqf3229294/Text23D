from __future__ import annotations

import json
import sys
from pathlib import Path

from .pyvista_renderer import _render_stl_preview_pyvista


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) != 4:
        print(
            "Usage: python -m app.pyvista_render_worker <mesh> <output> <width> <height>",
            file=sys.stderr,
        )
        return 2

    mesh_path = Path(args[0])
    output_path = Path(args[1])
    window_size = (int(args[2]), int(args[3]))
    result = _render_stl_preview_pyvista(
        mesh_path,
        output_path,
        window_size=window_size,
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
