# Text23D FreeCAD Runner

This runner executes generated FreeCAD Python scripts in headless mode and exports:

- `model.FCStd` for native manual editing with the FreeCAD feature tree
- `model.step` for CAD exchange
- `preview.stl` for browser preview

The generated script must define:

```python
def build_model(doc):
    ...
    return [final_object]
```

Run a smoke test after installing FreeCAD:

```powershell
FreeCADCmd.exe freecad-runner\run_freecad.py `
  freecad-runner\examples\cube_with_hole.py `
  data\freecad-smoke-output
```

If `FreeCADCmd.exe` is not on PATH, set `TEXT23D_FREECAD_PYTHON` to its full path.
