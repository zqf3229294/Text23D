from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

from .software_stl_renderer import (
    Color,
    Point2,
    Point3,
    _bounds_2d,
    _camera_axes,
    _draw_line,
    _draw_rect,
    _draw_text,
    _new_image,
    _project_point,
    _write_png,
)


_VIEWS: list[tuple[str, Point3, Point3]] = [
    ("ISO", (1.0, -1.0, 0.85), (0.0, 0.0, 1.0)),
    ("TOP", (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    ("FRONT", (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    ("RIGHT", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
]

_PALETTE: list[Color] = [
    (42, 92, 154),
    (38, 126, 94),
    (142, 89, 36),
    (114, 73, 156),
    (156, 63, 83),
]


def render_solid_view_preview(
    payload: dict[str, Any],
    output_path: Path,
    *,
    window_size: tuple[int, int] = (1280, 960),
) -> dict[str, object]:
    solid_objects = _parse_solid_objects(payload.get("objects"))
    if not any(item["polylines"] or item["bbox"] for item in solid_objects):
        raise RuntimeError("Solid view has no projectable B-Rep geometry.")

    width, height = window_size
    image = _new_image(width, height, (255, 255, 255))
    tile_width = width // 2
    tile_height = height // 2

    for index, (title, direction, up_hint) in enumerate(_VIEWS):
        row, col = divmod(index, 2)
        viewport = (
            col * tile_width,
            row * tile_height,
            tile_width,
            tile_height,
        )
        _draw_solid_view(
            image,
            width,
            height,
            viewport,
            solid_objects,
            title,
            direction,
            up_hint,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_png(output_path, width, height, image)
    return {
        "image_path": str(output_path),
        "object_count": len(solid_objects),
        "edge_count": sum(len(item["polylines"]) for item in solid_objects),
        "source": payload.get("source") or "freecad-brep",
        "truncated": bool(payload.get("truncated")),
        "views": [title for title, _direction, _up_hint in _VIEWS],
        "window_size": [width, height],
        "renderer": "solid-projection",
    }


def _parse_solid_objects(raw_objects: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_objects, list):
        return []

    result: list[dict[str, Any]] = []
    for index, raw_object in enumerate(raw_objects):
        if not isinstance(raw_object, dict):
            continue
        raw_edges = raw_object.get("edges")
        if not isinstance(raw_edges, list):
            raw_edges = []
        polylines = [
            points
            for points in (_parse_polyline(item) for item in raw_edges)
            if len(points) >= 2
        ]
        result.append(
            {
                "color": _PALETTE[index % len(_PALETTE)],
                "bbox": _bbox_corners(raw_object.get("bounds")),
                "polylines": polylines,
            }
        )
    return result


def _parse_polyline(raw_polyline: Any) -> list[Point3]:
    if not isinstance(raw_polyline, list):
        return []
    points = [_parse_point(raw_point) for raw_point in raw_polyline]
    return [point for point in points if point is not None]


def _parse_point(value: Any) -> Point3 | None:
    if isinstance(value, dict):
        raw = (value.get("x"), value.get("y"), value.get("z"))
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        raw = (value[0], value[1], value[2])
    else:
        return None

    point = (_as_float(raw[0]), _as_float(raw[1]), _as_float(raw[2]))
    if any(component is None for component in point):
        return None
    return point  # type: ignore[return-value]


def _bbox_corners(bounds: Any) -> list[Point3]:
    if not isinstance(bounds, dict):
        return []
    x_min = _as_float(bounds.get("x_min"))
    x_max = _as_float(bounds.get("x_max"))
    y_min = _as_float(bounds.get("y_min"))
    y_max = _as_float(bounds.get("y_max"))
    z_min = _as_float(bounds.get("z_min"))
    z_max = _as_float(bounds.get("z_max"))
    values = (x_min, x_max, y_min, y_max, z_min, z_max)
    if any(value is None for value in values):
        return []
    assert x_min is not None
    assert x_max is not None
    assert y_min is not None
    assert y_max is not None
    assert z_min is not None
    assert z_max is not None
    return [
        (x, y, z)
        for x in (x_min, x_max)
        for y in (y_min, y_max)
        for z in (z_min, z_max)
    ]


def _draw_solid_view(
    image: bytearray,
    width: int,
    height: int,
    viewport: tuple[int, int, int, int],
    solid_objects: list[dict[str, Any]],
    title: str,
    direction: Point3,
    up_hint: Point3,
) -> None:
    x0, y0, view_width, view_height = viewport
    _draw_rect(image, width, height, x0, y0, view_width, view_height, (232, 237, 244))
    _draw_text(image, width, height, x0 + 18, y0 + 18, title, (24, 32, 43), scale=3)

    right, up = _camera_axes(direction, up_hint)
    projected_objects = [
        {
            "color": item["color"],
            "bbox": [_project_point(point, right, up) for point in item["bbox"]],
            "polylines": [
                [_project_point(point, right, up) for point in polyline]
                for polyline in item["polylines"]
            ],
        }
        for item in solid_objects
    ]
    bounds = _bounds_2d(_projected_points(projected_objects))
    if bounds is None:
        return

    margin_x = max(32, int(view_width * 0.08))
    margin_top = max(58, int(view_height * 0.13))
    margin_bottom = max(28, int(view_height * 0.06))
    x_min, x_max, y_min, y_max = bounds
    span_x = max(x_max - x_min, 1e-9)
    span_y = max(y_max - y_min, 1e-9)
    scale = min(
        (view_width - margin_x * 2) / span_x,
        (view_height - margin_top - margin_bottom) / span_y,
    )
    center_x = x0 + view_width / 2.0
    center_y = y0 + margin_top + (view_height - margin_top - margin_bottom) / 2.0
    source_center_x = (x_min + x_max) / 2.0
    source_center_y = (y_min + y_max) / 2.0

    def to_screen(point: Point2) -> tuple[int, int]:
        px, py = point
        return (
            int(round(center_x + (px - source_center_x) * scale)),
            int(round(center_y - (py - source_center_y) * scale)),
        )

    for item in projected_objects:
        if item["bbox"]:
            _draw_projected_box(
                image,
                width,
                height,
                [to_screen(point) for point in item["bbox"]],
            )
        for polyline in item["polylines"]:
            screen_points = [to_screen(point) for point in polyline]
            _draw_polyline(image, width, height, screen_points, item["color"])


def _projected_points(projected_objects: list[dict[str, Any]]) -> Iterable[Point2]:
    for item in projected_objects:
        yield from item["bbox"]
        for polyline in item["polylines"]:
            yield from polyline


def _draw_polyline(
    image: bytearray,
    width: int,
    height: int,
    points: list[tuple[int, int]],
    color: Color,
) -> None:
    for start, end in zip(points, points[1:]):
        _draw_thick_line(image, width, height, start, end, color)


def _draw_thick_line(
    image: bytearray,
    width: int,
    height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    color: Color,
) -> None:
    for dx, dy in ((0, 0), (1, 0), (0, 1)):
        _draw_line(
            image,
            width,
            height,
            (start[0] + dx, start[1] + dy),
            (end[0] + dx, end[1] + dy),
            color,
        )


def _draw_projected_box(
    image: bytearray,
    width: int,
    height: int,
    points: list[tuple[int, int]],
) -> None:
    if len(points) != 8:
        return
    edges = [
        (0, 1),
        (0, 2),
        (0, 4),
        (3, 1),
        (3, 2),
        (3, 7),
        (5, 1),
        (5, 4),
        (5, 7),
        (6, 2),
        (6, 4),
        (6, 7),
    ]
    for start, end in edges:
        _draw_line(image, width, height, points[start], points[end], (155, 166, 184))


def _as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result
