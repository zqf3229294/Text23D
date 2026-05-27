import FreeCAD as App
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
