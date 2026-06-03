from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a FreeCAD build_model script.")
    parser.add_argument("script", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import FreeCAD as App

        module = load_user_module(args.script)
        build_model = getattr(module, "build_model", None)
        if not callable(build_model):
            raise RuntimeError("Script must define a callable build_model(doc).")

        doc = App.newDocument("Text23DGeneratedModel")
        result = build_model(doc)
        doc.recompute()
        write_object_manifest(doc, args.output_dir)
        objects = export_objects(doc, result)
        if not objects:
            raise RuntimeError("No exportable FreeCAD objects were produced.")

        export_model(doc, objects, args.output_dir)
        App.closeDocument(doc.Name)
        print(f"Exported FCStd, STEP, and STL to {args.output_dir}")
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1


def load_user_module(script_path: Path) -> ModuleType:
    if not script_path.exists():
        raise FileNotFoundError(script_path)
    spec = importlib.util.spec_from_file_location("text23d_freecad_user_model", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["text23d_freecad_user_model"] = module
    spec.loader.exec_module(module)
    return module


def export_objects(doc: Any, result: Any) -> list[Any]:
    if result is None:
        return [
            obj
            for obj in doc.Objects
            if hasattr(obj, "Shape") and not getattr(obj.Shape, "isNull", lambda: True)()
        ]
    if isinstance(result, (list, tuple)):
        return list(result)
    return [result]


def write_object_manifest(doc: Any, output_dir: Path) -> None:
    rows = []
    for obj in doc.Objects:
        row = {
            "name": getattr(obj, "Name", ""),
            "label": getattr(obj, "Label", ""),
            "type": getattr(obj, "TypeId", ""),
        }
        shape = getattr(obj, "Shape", None)
        bound_box = getattr(shape, "BoundBox", None)
        if bound_box is not None:
            row["bounds"] = {
                "x_min": getattr(bound_box, "XMin", None),
                "x_max": getattr(bound_box, "XMax", None),
                "y_min": getattr(bound_box, "YMin", None),
                "y_max": getattr(bound_box, "YMax", None),
                "z_min": getattr(bound_box, "ZMin", None),
                "z_max": getattr(bound_box, "ZMax", None),
            }
        rows.append(row)
    (output_dir / "objects.json").write_text(
        json.dumps(rows, indent=2),
        encoding="utf-8",
    )


def export_model(doc: Any, objects: list[Any], output_dir: Path) -> None:
    import Mesh
    import Part

    native_path = output_dir / "model.FCStd"
    step_path = output_dir / "model.step"
    stl_path = output_dir / "preview.stl"

    doc.saveAs(str(native_path))
    Part.export(objects, str(step_path))
    Mesh.export(objects, str(stl_path))


if __name__ == "__main__":
    raise SystemExit(main())
