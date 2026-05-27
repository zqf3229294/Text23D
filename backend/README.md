# Text23D Backend

FastAPI service for conversations, LLM-driven CadQuery generation, and CAD artifact delivery.

## Local setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

The default provider is `mock`, so the API can be exercised before connecting an external LLM.
Generated CadQuery scripts run locally in a subprocess. CadQuery currently needs a Python version with compatible native wheels; Python 3.11 or 3.12 is recommended.

If your backend Python is 3.11 or 3.12, you can install CadQuery into the same venv:

```powershell
python -m pip install -e ".[cad]"
```

If your backend Python is newer, such as Python 3.14, create a separate Python 3.11 or 3.12 environment with CadQuery installed and point `TEXT23D_CAD_RUNNER_PYTHON` at that environment's `python.exe`.

Example:

```powershell
py -3.12 -m venv ..\.venv-cadquery
..\.venv-cadquery\Scripts\python.exe -m pip install cadquery
```

Then set this in the root `.env`:

```text
TEXT23D_CAD_RUNNER_PYTHON=C:\Development\Text23D\.venv-cadquery\Scripts\python.exe
```

## Environment

Copy the root `.env.example` to `.env` and adjust:

- `TEXT23D_LLM_PROVIDER=mock|openai|anthropic|deepseek|openai_compatible`
- `TEXT23D_OPENAI_API_KEY=...`
- `TEXT23D_ANTHROPIC_API_KEY=...`
- `TEXT23D_DEEPSEEK_API_KEY=...`
- `TEXT23D_CAD_KERNEL=cadquery|freecad`
- `TEXT23D_CAD_RUNNER_PYTHON=...` if CadQuery lives in a separate Python environment
- `TEXT23D_CAD_RUNNER_SCRIPT=...` if the runner script is moved
- `TEXT23D_FREECAD_PYTHON=...` if using the FreeCAD runner

DeepSeek V4 example:

```text
TEXT23D_LLM_PROVIDER=deepseek
TEXT23D_DEEPSEEK_API_KEY=your_deepseek_key
TEXT23D_DEEPSEEK_BASE_URL=https://api.deepseek.com
TEXT23D_DEEPSEEK_MODEL=deepseek-v4-flash
```

Use `deepseek-v4-pro` instead of `deepseek-v4-flash` if you want the more capable V4 model.

For another OpenAI-compatible API:

```text
TEXT23D_LLM_PROVIDER=openai_compatible
TEXT23D_OPENAI_COMPATIBLE_API_KEY=your_key
TEXT23D_OPENAI_COMPATIBLE_BASE_URL=https://provider.example.com
TEXT23D_OPENAI_COMPATIBLE_MODEL=model-id
```

FreeCAD generation example:

```text
TEXT23D_CAD_KERNEL=freecad
TEXT23D_FREECAD_PYTHON=C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe
```

The FreeCAD path returns a native `model.FCStd` artifact for manual editing, plus STEP and STL preview artifacts.

## Tests

```powershell
cd backend
pytest
```
