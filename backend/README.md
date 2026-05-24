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

- `TEXT23D_LLM_PROVIDER=mock|openai|anthropic`
- `TEXT23D_OPENAI_API_KEY=...`
- `TEXT23D_ANTHROPIC_API_KEY=...`
- `TEXT23D_CAD_RUNNER_PYTHON=...` if CadQuery lives in a separate Python environment
- `TEXT23D_CAD_RUNNER_SCRIPT=...` if the runner script is moved

## Tests

```powershell
cd backend
pytest
```
