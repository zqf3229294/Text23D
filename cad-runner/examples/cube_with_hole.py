import cadquery as cq


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
