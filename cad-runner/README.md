# Text23D Local CadQuery Runner

This script executes a generated CadQuery script directly on the local machine and exports:

- `model.step`
- `preview.glb`

The input script must define `build_model()` and return a CadQuery `Workplane`, shape, or `Assembly`.

Run a local smoke test from the repository root after installing CadQuery. Python 3.11 or 3.12 is recommended because CadQuery depends on native CAD wheels.

```powershell
.\.venv-cadquery\Scripts\python.exe cad-runner\run_cadquery.py `
  cad-runner\examples\cube_with_hole.py `
  data\smoke-output
```

The backend calls this script in a subprocess. By default it uses the backend Python executable. To use a separate CadQuery environment, set:

```text
TEXT23D_CAD_RUNNER_PYTHON=C:\Path\To\python.exe
```
