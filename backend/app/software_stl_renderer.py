from __future__ import annotations

import math
import re
import struct
import zlib
from pathlib import Path
from typing import Iterable

Point3 = tuple[float, float, float]
Triangle = tuple[Point3, Point3, Point3]
Point2 = tuple[float, float]
Color = tuple[int, int, int]


def render_stl_preview_software(
    mesh_path: Path,
    output_path: Path,
    *,
    window_size: tuple[int, int] = (1280, 960),
) -> dict[str, object]:
    triangles = _read_stl_triangles(mesh_path)
    if not triangles:
        raise RuntimeError(f"Preview mesh has no triangles: {mesh_path}")

    width, height = window_size
    image = _new_image(width, height, (255, 255, 255))
    views = [
        ("ISO", (1.0, -1.0, 0.85), (0.0, 0.0, 1.0)),
        ("TOP", (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
        ("FRONT", (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ("RIGHT", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ]
    tile_width = width // 2
    tile_height = height // 2

    for index, (title, direction, up_hint) in enumerate(views):
        row, col = divmod(index, 2)
        viewport = (
            col * tile_width,
            row * tile_height,
            tile_width,
            tile_height,
        )
        _draw_view(image, width, height, viewport, triangles, title, direction, up_hint)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_png(output_path, width, height, image)
    return {
        "mesh_path": str(mesh_path),
        "image_path": str(output_path),
        "triangle_count": len(triangles),
        "window_size": [width, height],
        "views": ["ISO", "TOP", "FRONT", "RIGHT"],
        "renderer": "software",
    }


def _read_stl_triangles(path: Path) -> list[Triangle]:
    data = path.read_bytes()
    triangles = _read_binary_stl(data)
    if triangles:
        return triangles
    return _read_ascii_stl(data)


def _read_binary_stl(data: bytes) -> list[Triangle]:
    if len(data) < 84:
        return []
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + triangle_count * 50
    if triangle_count == 0 or expected_size != len(data):
        return []

    triangles: list[Triangle] = []
    offset = 84
    for _ in range(triangle_count):
        values = struct.unpack_from("<12f", data, offset)
        triangles.append(
            (
                (values[3], values[4], values[5]),
                (values[6], values[7], values[8]),
                (values[9], values[10], values[11]),
            )
        )
        offset += 50
    return triangles


def _read_ascii_stl(data: bytes) -> list[Triangle]:
    text = data.decode("utf-8", errors="ignore")
    vertices = [
        (float(match.group(1)), float(match.group(2)), float(match.group(3)))
        for match in re.finditer(
            r"vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)",
            text,
        )
    ]
    return [
        (vertices[index], vertices[index + 1], vertices[index + 2])
        for index in range(0, len(vertices) - 2, 3)
    ]


def _draw_view(
    image: bytearray,
    width: int,
    height: int,
    viewport: tuple[int, int, int, int],
    triangles: list[Triangle],
    title: str,
    direction: Point3,
    up_hint: Point3,
) -> None:
    x0, y0, view_width, view_height = viewport
    _draw_rect(image, width, height, x0, y0, view_width, view_height, (230, 235, 242))
    _draw_text(image, width, height, x0 + 18, y0 + 18, title, (24, 32, 43), scale=3)

    right, up = _camera_axes(direction, up_hint)
    projected = [
        tuple(_project_point(point, right, up) for point in triangle)
        for triangle in triangles
    ]
    bounds = _bounds_2d(point for triangle in projected for point in triangle)
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

    bbox_points = _projected_bbox_points(triangles, right, up)
    _draw_projected_box(image, width, height, [to_screen(point) for point in bbox_points])

    max_triangles = 9000
    step = max(1, math.ceil(len(projected) / max_triangles))
    for triangle in projected[::step]:
        a, b, c = [to_screen(point) for point in triangle]
        _draw_line(image, width, height, a, b, (72, 83, 100))
        _draw_line(image, width, height, b, c, (72, 83, 100))
        _draw_line(image, width, height, c, a, (72, 83, 100))


def _camera_axes(direction: Point3, up_hint: Point3) -> tuple[Point3, Point3]:
    forward = _normalize(direction)
    up_source = _normalize(up_hint)
    right = _normalize(_cross(up_source, forward))
    if _length(right) < 1e-9:
        right = (1.0, 0.0, 0.0)
    up = _normalize(_cross(forward, right))
    return right, up


def _project_point(point: Point3, right: Point3, up: Point3) -> Point2:
    return (_dot(point, right), _dot(point, up))


def _projected_bbox_points(
    triangles: list[Triangle],
    right: Point3,
    up: Point3,
) -> list[Point2]:
    xs = [point[0] for triangle in triangles for point in triangle]
    ys = [point[1] for triangle in triangles for point in triangle]
    zs = [point[2] for triangle in triangles for point in triangle]
    corners = [
        (x, y, z)
        for x in (min(xs), max(xs))
        for y in (min(ys), max(ys))
        for z in (min(zs), max(zs))
    ]
    return [_project_point(point, right, up) for point in corners]


def _draw_projected_box(
    image: bytearray,
    width: int,
    height: int,
    points: list[tuple[int, int]],
) -> None:
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
        _draw_line(image, width, height, points[start], points[end], (145, 158, 178))


def _bounds_2d(points: Iterable[Point2]) -> tuple[float, float, float, float] | None:
    values = list(points)
    if not values:
        return None
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return min(xs), max(xs), min(ys), max(ys)


def _new_image(width: int, height: int, color: Color) -> bytearray:
    r, g, b = color
    return bytearray([r, g, b] * width * height)


def _set_pixel(
    image: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: Color,
) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    offset = (y * width + x) * 3
    image[offset : offset + 3] = bytes(color)


def _draw_line(
    image: bytearray,
    width: int,
    height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    color: Color,
) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        _set_pixel(image, width, height, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        twice_error = 2 * error
        if twice_error >= dy:
            error += dy
            x0 += sx
        if twice_error <= dx:
            error += dx
            y0 += sy


def _draw_rect(
    image: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: Color,
) -> None:
    _draw_line(image, width, height, (x, y), (x + rect_width - 1, y), color)
    _draw_line(
        image,
        width,
        height,
        (x, y + rect_height - 1),
        (x + rect_width - 1, y + rect_height - 1),
        color,
    )
    _draw_line(image, width, height, (x, y), (x, y + rect_height - 1), color)
    _draw_line(
        image,
        width,
        height,
        (x + rect_width - 1, y),
        (x + rect_width - 1, y + rect_height - 1),
        color,
    )


_FONT = {
    "F": ["11111", "10000", "11110", "10000", "10000", "10000", "10000"],
    "G": ["01110", "10000", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "11111", "10001", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
}


def _draw_text(
    image: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    color: Color,
    *,
    scale: int = 2,
) -> None:
    cursor = x
    for char in text.upper():
        glyph = _FONT.get(char)
        if glyph is None:
            cursor += 4 * scale
            continue
        for row, line in enumerate(glyph):
            for col, value in enumerate(line):
                if value != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        _set_pixel(
                            image,
                            width,
                            height,
                            cursor + col * scale + dx,
                            y + row * scale + dy,
                            color,
                        )
        cursor += 6 * scale


def _write_png(path: Path, width: int, height: int, image: bytearray) -> None:
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(image[y * stride : (y + 1) * stride])

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    png.extend(chunk(b"IDAT", zlib.compress(bytes(raw), level=6)))
    png.extend(chunk(b"IEND", b""))
    path.write_bytes(png)


def _dot(left: Point3, right: Point3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _cross(left: Point3, right: Point3) -> Point3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _length(vector: Point3) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: Point3) -> Point3:
    length = _length(vector)
    if length < 1e-9:
        return (0.0, 0.0, 0.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)
