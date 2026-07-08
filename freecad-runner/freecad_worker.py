from __future__ import annotations

import json
import math
import sys
import traceback
from pathlib import Path
from typing import Any


_SOLID_VIEW_MAX_OBJECTS = 12
_SOLID_VIEW_MAX_EDGES_PER_OBJECT = 500
_SOLID_VIEW_MAX_POINTS_PER_EDGE = 24
_SOLID_VIEW_MAX_TOTAL_POINTS = 20000


class FreeCADWorker:
    def __init__(self):
        import FreeCAD as App

        self.App = App
        self.Gui = self._load_gui()
        self.doc = None
        self.document_name = "Text23DGeneratedModel"
        self.namespace: dict[str, Any] = {}
        self.create_document(self.document_name)

    def _load_gui(self):
        try:
            import FreeCADGui as Gui
        except Exception:
            return None
        return Gui

    def create_document(self, name: str | None = None) -> dict[str, Any]:
        self.close_document()
        self.document_name = _safe_document_name(name or "Text23DGeneratedModel")
        self.doc = self.App.newDocument(self.document_name)
        self.App.setActiveDocument(self.doc.Name)
        if self.Gui is not None:
            try:
                self.Gui.ActiveDocument = self.Gui.getDocument(self.doc.Name)
            except Exception:
                pass
        self.namespace = self._execution_namespace()
        return {
            "document": self.doc.Name,
            "message": "Created a fresh live FreeCAD document.",
        }

    def close_document(self) -> None:
        if self.doc is None:
            return
        try:
            self.App.closeDocument(self.doc.Name)
        except Exception:
            pass
        self.doc = None

    def execute_code(self, code: str) -> dict[str, Any]:
        if self.doc is None:
            self.create_document(self.document_name)
        exec(code, self.namespace, self.namespace)
        self.doc.recompute()
        return {
            "message": "Code executed in the live FreeCAD document.",
            "object_count": len(self.doc.Objects),
            "objects": self.objects(),
        }

    def objects(self) -> list[dict[str, Any]]:
        if self.doc is None:
            return []
        return [_object_manifest(obj) for obj in self.doc.Objects]

    def get_object(self, name: str) -> dict[str, Any]:
        target = name.strip().lower()
        for obj in self.objects():
            names = {
                str(obj.get("name", "")).lower(),
                str(obj.get("label", "")).lower(),
            }
            if target in names:
                return {"object": obj}
        raise RuntimeError(f"Object not found: {name}")

    def get_view(self, output_path: str) -> dict[str, Any]:
        if self.Gui is None:
            raise RuntimeError("FreeCADGui is not available; cannot capture viewport.")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._activate_view()
        view = self.Gui.ActiveDocument.ActiveView
        try:
            view.viewAxonometric()
            view.fitAll()
        except Exception:
            pass
        view.saveImage(str(path), 1280, 720, "White")
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError("FreeCAD viewport screenshot was not written.")
        return {
            "message": "Captured FreeCAD viewport screenshot.",
            "image_path": str(path),
            "objects": self.objects(),
        }

    def export_preview_mesh(self, output_path: str) -> dict[str, Any]:
        import Mesh

        if self.doc is None:
            raise RuntimeError("No FreeCAD document is active.")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.recompute()
        objects = self._exportable_objects()
        if not objects:
            raise RuntimeError("No exportable FreeCAD objects were produced.")
        Mesh.export(objects, str(path))
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError("FreeCAD preview mesh was not written.")
        return {
            "message": "Exported temporary FreeCAD preview mesh.",
            "mesh_path": str(path),
            "objects": self.objects(),
        }

    def export_solid_view(self) -> dict[str, Any]:
        if self.doc is None:
            raise RuntimeError("No FreeCAD document is active.")
        self.doc.recompute()
        objects = self._exportable_objects()
        if not objects:
            raise RuntimeError("No exportable FreeCAD solid objects were produced.")
        return {
            "message": "Exported FreeCAD solid B-Rep view data.",
            "objects": self.objects(),
            "solid_view": _solid_view_payload(self.doc.Name, objects),
        }

    def export_model(self, output_dir: str) -> dict[str, Any]:
        import Mesh
        import Part

        if self.doc is None:
            raise RuntimeError("No FreeCAD document is active.")
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        self.doc.recompute()
        objects = self._exportable_objects()
        if not objects:
            raise RuntimeError("No exportable FreeCAD objects were produced.")

        native_path = output / "model.FCStd"
        step_path = output / "model.step"
        stl_path = output / "preview.stl"
        objects_path = output / "objects.json"
        script_path = output / "live_session.py"

        self.doc.saveAs(str(native_path))
        Part.export(objects, str(step_path))
        Mesh.export(objects, str(stl_path))
        objects_path.write_text(json.dumps(self.objects(), indent=2), encoding="utf-8")
        script_path.write_text(
            "# Generated by Text23D live FreeCAD worker.\n"
            "# Open model.FCStd for the editable feature tree.\n",
            encoding="utf-8",
        )
        return {
            "message": "Final FreeCAD artifacts are ready.",
            "objects": self.objects(),
            "artifacts": {
                "native": str(native_path),
                "step": str(step_path),
                "stl": str(stl_path),
                "glb": None,
                "script": str(script_path),
                "runner_log": None,
            },
            "script_path": str(script_path),
        }

    def _exportable_objects(self) -> list[Any]:
        if self.doc is None:
            return []
        shape_objects = [
            obj
            for obj in self.doc.Objects
            if _is_exportable_shape_object(obj)
        ]
        visible_objects = [
            obj for obj in shape_objects if not _is_explicitly_hidden(obj)
        ]
        candidates = visible_objects or shape_objects
        solid_candidates = [
            obj
            for obj in candidates
            if _shape_count(getattr(obj, "Shape", None), "Solids")
        ]
        candidates = solid_candidates or candidates
        return _top_level_shape_objects(candidates) or candidates

    def _activate_view(self) -> None:
        if self.Gui is None or self.doc is None:
            return
        try:
            self.Gui.showMainWindow()
        except Exception:
            pass
        try:
            self.Gui.ActiveDocument = self.Gui.getDocument(self.doc.Name)
        except Exception:
            pass
        try:
            self.Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass

    def _execution_namespace(self) -> dict[str, Any]:
        import Mesh
        import Part

        namespace = {
            "__builtins__": __builtins__,
            "App": self.App,
            "FreeCAD": self.App,
            "Part": Part,
            "Mesh": Mesh,
            "doc": self.doc,
        }
        if self.Gui is not None:
            namespace["Gui"] = self.Gui
            namespace["FreeCADGui"] = self.Gui
        return namespace


def main() -> int:
    worker = FreeCADWorker()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request: dict[str, Any] = {}
        try:
            request = json.loads(line)
            response = handle_request(worker, request)
        except Exception as exc:
            response = {
                "id": request.get("id"),
                "ok": False,
                "content": {
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            }
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
        if response.get("command") == "shutdown":
            break
    worker.close_document()
    return 0


def handle_request(worker: FreeCADWorker, request: dict[str, Any]) -> dict[str, Any]:
    command = request.get("command")
    args = request.get("args") or {}
    content: dict[str, Any]
    asset_path = None

    if command == "create_document":
        content = worker.create_document(args.get("name"))
    elif command == "execute_code":
        content = worker.execute_code(str(args.get("code", "")))
    elif command == "get_objects":
        objects = worker.objects()
        content = {"object_count": len(objects), "objects": objects}
    elif command == "get_object":
        content = worker.get_object(str(args.get("name", "")))
    elif command == "get_view":
        asset_path = str(args["output_path"])
        content = worker.get_view(asset_path)
    elif command == "export_preview_mesh":
        content = worker.export_preview_mesh(str(args["output_path"]))
    elif command == "export_solid_view":
        content = worker.export_solid_view()
    elif command == "export_model":
        content = worker.export_model(str(args["output_dir"]))
    elif command == "shutdown":
        content = {"message": "Worker shutting down."}
    else:
        raise RuntimeError(f"Unsupported command: {command}")

    return {
        "id": request.get("id"),
        "command": command,
        "ok": True,
        "content": content,
        "asset_path": asset_path,
    }


def _object_manifest(obj: Any) -> dict[str, Any]:
    row = {
        "name": getattr(obj, "Name", ""),
        "label": getattr(obj, "Label", ""),
        "type": getattr(obj, "TypeId", ""),
        "visible": getattr(getattr(obj, "ViewObject", None), "Visibility", None),
    }
    shape = getattr(obj, "Shape", None)
    bound_box = getattr(shape, "BoundBox", None)
    bounds = _bounds_manifest(bound_box)
    if bounds is not None:
        row["bounds"] = bounds
    if shape is not None:
        row["solid_count"] = _shape_count(shape, "Solids")
        row["face_count"] = _shape_count(shape, "Faces")
        row["edge_count"] = _shape_count(shape, "Edges")
    return row


def _is_exportable_shape_object(obj: Any) -> bool:
    shape = getattr(obj, "Shape", None)
    if shape is None:
        return False
    is_null = getattr(shape, "isNull", None)
    if callable(is_null) and is_null():
        return False
    return _shape_count(shape, "Solids") > 0 or _shape_count(shape, "Faces") > 0


def _is_explicitly_hidden(obj: Any) -> bool:
    view_object = getattr(obj, "ViewObject", None)
    if view_object is None:
        return False
    return getattr(view_object, "Visibility", None) is False


def _top_level_shape_objects(objects: list[Any]) -> list[Any]:
    object_ids = {id(obj) for obj in objects}
    consumed_ids: set[int] = set()
    for obj in objects:
        for child in getattr(obj, "OutList", []) or []:
            if id(child) in object_ids:
                consumed_ids.add(id(child))
    return [obj for obj in objects if id(obj) not in consumed_ids]


def _solid_view_payload(document_name: str, objects: list[Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_points = 0
    truncated = False

    for obj in objects:
        if len(rows) >= _SOLID_VIEW_MAX_OBJECTS:
            truncated = True
            break
        shape = getattr(obj, "Shape", None)
        edges: list[list[list[float]]] = []
        for edge in list(getattr(shape, "Edges", []) or []):
            if len(edges) >= _SOLID_VIEW_MAX_EDGES_PER_OBJECT:
                truncated = True
                break
            points = _edge_points(edge)
            if len(points) < 2:
                continue
            if total_points + len(points) > _SOLID_VIEW_MAX_TOTAL_POINTS:
                truncated = True
                break
            edges.append(points)
            total_points += len(points)

        bounds = _bounds_manifest(getattr(shape, "BoundBox", None))
        rows.append(
            {
                "name": getattr(obj, "Name", ""),
                "label": getattr(obj, "Label", ""),
                "type": getattr(obj, "TypeId", ""),
                "bounds": bounds,
                "solid_count": _shape_count(shape, "Solids"),
                "face_count": _shape_count(shape, "Faces"),
                "edge_count": _shape_count(shape, "Edges"),
                "vertex_count": _shape_count(shape, "Vertexes"),
                "edges": edges,
            }
        )
        if truncated and total_points >= _SOLID_VIEW_MAX_TOTAL_POINTS:
            break

    return {
        "document": document_name,
        "source": "freecad-brep",
        "object_count": len(rows),
        "objects": rows,
        "truncated": truncated,
    }


def _edge_points(edge: Any) -> list[list[float]]:
    raw_points = []
    try:
        raw_points = edge.discretize(Number=_SOLID_VIEW_MAX_POINTS_PER_EDGE)
    except Exception:
        try:
            raw_points = edge.discretize(_SOLID_VIEW_MAX_POINTS_PER_EDGE)
        except Exception:
            raw_points = [
                getattr(vertex, "Point", None)
                for vertex in getattr(edge, "Vertexes", []) or []
            ]

    points: list[list[float]] = []
    last_point: list[float] | None = None
    for raw_point in raw_points:
        point = _point_tuple(raw_point)
        if point is None or point == last_point:
            continue
        points.append(point)
        last_point = point
    return points


def _point_tuple(point: Any) -> list[float] | None:
    if isinstance(point, (list, tuple)) and len(point) >= 3:
        values = (
            _finite_float(point[0]),
            _finite_float(point[1]),
            _finite_float(point[2]),
        )
    else:
        values = (
            _finite_float(_first_attr(point, "x", "X")),
            _finite_float(_first_attr(point, "y", "Y")),
            _finite_float(_first_attr(point, "z", "Z")),
        )
    if any(value is None for value in values):
        return None
    return [float(values[0]), float(values[1]), float(values[2])]


def _bounds_manifest(bound_box: Any) -> dict[str, float] | None:
    if bound_box is None:
        return None
    values = {
        "x_min": _finite_float(getattr(bound_box, "XMin", None)),
        "x_max": _finite_float(getattr(bound_box, "XMax", None)),
        "y_min": _finite_float(getattr(bound_box, "YMin", None)),
        "y_max": _finite_float(getattr(bound_box, "YMax", None)),
        "z_min": _finite_float(getattr(bound_box, "ZMin", None)),
        "z_max": _finite_float(getattr(bound_box, "ZMax", None)),
    }
    if any(value is None for value in values.values()):
        return None
    return {key: float(value) for key, value in values.items()}


def _shape_count(shape: Any, attribute: str) -> int:
    value = getattr(shape, attribute, None)
    if value is None:
        return 0
    try:
        return len(value)
    except TypeError:
        return 0


def _first_attr(value: Any, *names: str) -> Any:
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _safe_document_name(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-"}).strip()
    return cleaned[:64] or "Text23DGeneratedModel"


if __name__ == "__main__":
    raise SystemExit(main())
