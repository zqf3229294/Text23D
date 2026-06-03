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

## Persistent Agent Worker

Agent mode can use `freecad_worker.py` to keep one live FreeCAD document open per
conversation. This worker requires GUI-capable FreeCAD because `get_view` captures
real viewport PNG screenshots.

Windows example:

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" `
  freecad-runner\freecad_worker.py
```

Text23D normally starts this process for you when:

```text
TEXT23D_GENERATION_MODE=agent
TEXT23D_CAD_KERNEL=freecad
TEXT23D_FREECAD_AGENT_BACKEND=worker
TEXT23D_FREECAD_PYTHON=C:\Program Files\FreeCAD 1.1\bin\python.exe
TEXT23D_FREECAD_GUI_EXECUTABLE=
TEXT23D_FREECAD_WORKER_VIEW_BACKEND=summary
```

`TEXT23D_FREECAD_GUI_EXECUTABLE` is only a fallback when
`TEXT23D_FREECAD_PYTHON` is not set. On Windows, launching the worker through
`FreeCAD.exe` may show the GUI but fail to answer the JSON-lines protocol.
`TEXT23D_FREECAD_WORKER_VIEW_BACKEND=summary` avoids native viewport capture;
set it to `gui` only when `FreeCADGui.ActiveView.saveImage()` is stable locally.

Linux/headless deployments should run GUI FreeCAD under a virtual display such as
`xvfb-run` or a managed `Xvfb :99` with `DISPLAY=:99`. Text23D does not manage Xvfb
in the Windows-first worker version.
