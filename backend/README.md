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

## Environment

Copy the root `.env.example` to `.env` and adjust:

- `TEXT23D_LLM_PROVIDER=mock|openai|anthropic`
- `TEXT23D_OPENAI_API_KEY=...`
- `TEXT23D_ANTHROPIC_API_KEY=...`
- `TEXT23D_CAD_RUNNER_IMAGE=text23d-cad-runner:local`

Build the runner image from the repository root before using real CAD execution:

```powershell
docker build -t text23d-cad-runner:local cad-runner
```

## Tests

```powershell
cd backend
pytest
```
