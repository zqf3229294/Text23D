# Text23D CadQuery Runner

This image executes a generated CadQuery script and exports:

- `/work/output/model.step`
- `/work/output/preview.glb`
- `/work/output/run.log` written by the backend process outside the container

Build from the repository root:

```powershell
docker build -t text23d-cad-runner:local cad-runner
```

Smoke test:

```powershell
docker run --rm --network none `
  -v ${PWD}\cad-runner\examples\cube_with_hole.py:/work/model.py:ro `
  -v ${PWD}\data\smoke-output:/work/output `
  text23d-cad-runner:local `
  python /opt/text23d/run_cadquery.py /work/model.py /work/output
```
