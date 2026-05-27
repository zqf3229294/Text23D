from __future__ import annotations

import argparse
import importlib.util
import sys
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a CadQuery build_model script.")
    parser.add_argument("script", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        module = load_user_module(args.script)
        build_model = getattr(module, "build_model", None)
        if not callable(build_model):
            raise RuntimeError("Script must define a callable build_model().")
        model = build_model()
        export_model(model, args.output_dir)
        print(f"Exported STEP and GLB to {args.output_dir}")
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1


def load_user_module(script_path: Path) -> ModuleType:
    if not script_path.exists():
        raise FileNotFoundError(script_path)
    spec = importlib.util.spec_from_file_location("text23d_user_model", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["text23d_user_model"] = module
    spec.loader.exec_module(module)
    return module


def export_model(model: Any, output_dir: Path) -> None:
    import cadquery as cq
    from cadquery import exporters

    if model is None:
        raise RuntimeError("build_model() returned None.")

    step_path = output_dir / "model.step"
    glb_path = output_dir / "preview.glb"

    if isinstance(model, cq.Assembly):
        model.export(str(step_path))
        model.export(str(glb_path))
        return

    exporters.export(model, str(step_path))

    assembly = cq.Assembly(name="generated_model")
    assembly.add(model, name="generated_part", color=cq.Color(0.64, 0.68, 0.72, 1.0))
    assembly.export(str(glb_path))


if __name__ == "__main__":
    raise SystemExit(main())
