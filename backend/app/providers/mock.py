from .base import CADGenerationResponse


class MockLLMProvider:
    async def generate_cad(
        self,
        messages: list[dict[str, str]],
        previous_error: str | None = None,
        cad_kernel: str = "cadquery",
    ) -> CADGenerationResponse:
        prompt = _latest_user_prompt(messages)
        if cad_kernel == "freecad":
            code = (
                _freecad_cube_with_hole()
                if "hole" in prompt.lower()
                else _freecad_simple_bracket()
            )
        else:
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


def _freecad_cube_with_hole() -> str:
    return '''import FreeCAD as App
import Part


def build_model(doc):
    side = 40.0
    hole_radius = 5.0

    cube = doc.addObject("Part::Box", "BaseCube")
    cube.Length = side
    cube.Width = side
    cube.Height = side

    hole = doc.addObject("Part::Cylinder", "ThroughHoleTool")
    hole.Radius = hole_radius
    hole.Height = side * 2.0
    hole.Placement = App.Placement(
        App.Vector(side / 2.0, side / 2.0, -side / 2.0),
        App.Rotation(),
    )

    cut = doc.addObject("Part::Cut", "CubeWithThroughHole")
    cut.Base = cube
    cut.Tool = hole
    doc.recompute()
    return [cut]
'''


def _freecad_simple_bracket() -> str:
    return '''import FreeCAD as App
import Part


def build_model(doc):
    base_length = 80.0
    base_width = 38.0
    base_thickness = 8.0
    upright_height = 48.0
    upright_thickness = 8.0
    hole_radius = 3.0

    base = doc.addObject("Part::Box", "BasePlate")
    base.Length = base_length
    base.Width = base_width
    base.Height = base_thickness

    upright = doc.addObject("Part::Box", "VerticalWeb")
    upright.Length = upright_thickness
    upright.Width = base_width
    upright.Height = upright_height
    upright.Placement = App.Placement(
        App.Vector(0.0, 0.0, base_thickness),
        App.Rotation(),
    )

    fuse = doc.addObject("Part::Fuse", "BracketBlank")
    fuse.Base = base
    fuse.Tool = upright

    hole_a = doc.addObject("Part::Cylinder", "LeftMountingHoleTool")
    hole_a.Radius = hole_radius
    hole_a.Height = base_thickness * 3.0
    hole_a.Placement = App.Placement(
        App.Vector(22.0, base_width / 2.0, -base_thickness),
        App.Rotation(),
    )

    cut_a = doc.addObject("Part::Cut", "BracketWithLeftHole")
    cut_a.Base = fuse
    cut_a.Tool = hole_a

    hole_b = doc.addObject("Part::Cylinder", "RightMountingHoleTool")
    hole_b.Radius = hole_radius
    hole_b.Height = base_thickness * 3.0
    hole_b.Placement = App.Placement(
        App.Vector(58.0, base_width / 2.0, -base_thickness),
        App.Rotation(),
    )

    cut_b = doc.addObject("Part::Cut", "BracketWithMountingHoles")
    cut_b.Base = cut_a
    cut_b.Tool = hole_b
    doc.recompute()
    return [cut_b]
'''
