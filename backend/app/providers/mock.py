from .base import CADGenerationResponse


class MockLLMProvider:
    async def generate_cad(
        self,
        messages: list[dict[str, str]],
        previous_error: str | None = None,
    ) -> CADGenerationResponse:
        prompt = _latest_user_prompt(messages)
        code = _cube_with_hole() if "hole" in prompt.lower() else _simple_bracket()
        summary = (
            "Generated a 40 mm cube with a 10 mm vertical through-hole."
            if "hole" in prompt.lower()
            else "Generated a simple parametric mounting bracket concept."
        )
        if previous_error:
            summary += " The script was simplified after a repair attempt."
        return CADGenerationResponse(assistant_summary=summary, code=code)


def _latest_user_prompt(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _cube_with_hole() -> str:
    return '''import cadquery as cq


def build_model():
    side = 40.0
    hole_diameter = 10.0
    return (
        cq.Workplane("XY")
        .box(side, side, side)
        .faces(">Z")
        .workplane()
        .hole(hole_diameter)
    )
'''


def _simple_bracket() -> str:
    return '''import cadquery as cq


def build_model():
    base_length = 80.0
    base_width = 38.0
    base_thickness = 8.0
    upright_height = 48.0
    upright_thickness = 8.0
    hole_diameter = 6.0

    base = (
        cq.Workplane("XY")
        .box(base_length, base_width, base_thickness)
        .edges("|Z")
        .fillet(2.0)
    )
    upright = (
        cq.Workplane("XY")
        .box(upright_thickness, base_width, upright_height)
        .translate((-base_length / 2 + upright_thickness / 2, 0, upright_height / 2))
    )
    mounting_holes = (
        cq.Workplane("XY")
        .pushPoints([(-25, 0), (25, 0)])
        .circle(hole_diameter / 2)
        .extrude(base_thickness * 3)
    )
    return base.union(upright).cut(mounting_holes)
'''
