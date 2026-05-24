# Text23D Mechanical

Text23D Mechanical is an AI-assisted mechanical design platform for generating and refining 3D parametric CAD models from conversational input.

This repository currently contains the first local MVP scaffold:

- Angular frontend with a left-side chat panel and right-side Three.js CAD preview.
- Python/FastAPI backend for conversations, generation jobs, artifacts, and provider adapters.
- Local CadQuery runner that exports `STEP` for CAD download and `GLB` for browser preview.
- SQLite plus filesystem storage for local single-user development.

The default LLM provider is `mock`, so the stack can be tested before connecting OpenAI or Anthropic credentials.

## Repository Layout

```text
backend/      FastAPI API, SQLite persistence, provider adapters, tests
cad-runner/   Local script that executes generated CadQuery scripts
frontend/     Angular standalone app with Three.js preview
docs/         Architecture and API notes
data/         Local runtime files, ignored by Git
```

## Prerequisites

- Python 3.11+
- Node.js LTS and npm
- CadQuery installed in the backend Python environment, or in a separate Python environment referenced by `TEXT23D_CAD_RUNNER_PYTHON`

CadQuery depends on native CAD wheels that may lag the newest Python releases. Python 3.11 or 3.12 is recommended for the local CAD runner.

## Quick Start

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Start the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

For real CAD export, install CadQuery into a Python 3.11 or 3.12 environment. If the backend venv uses 3.11 or 3.12, run:

```powershell
python -m pip install -e ".[cad]"
```

If the backend venv uses a newer Python such as 3.14, create a separate runner environment:

```powershell
py -3.12 -m venv ..\.venv-cadquery
..\.venv-cadquery\Scripts\python.exe -m pip install cadquery
```

Then set this in the root `.env`:

```text
TEXT23D_CAD_RUNNER_PYTHON=C:\Development\Text23D\.venv-cadquery\Scripts\python.exe
```

Start the frontend in another shell:

```powershell
cd frontend
npm install
npm start
```

Open `http://localhost:4200`.

## LLM Providers

Use `.env` to choose a provider:

```text
TEXT23D_LLM_PROVIDER=mock
```

Supported values:

- `mock`: deterministic development provider.
- `openai`: OpenAI SDK provider using structured JSON output.
- `anthropic`: Anthropic SDK provider that parses the required JSON response.

For real providers, add the corresponding API key and model value in `.env`.

## API

Core endpoints:

- `POST /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `POST /api/conversations/{conversation_id}/messages`
- `GET /api/generations/{generation_id}`
- `GET /api/generations/{generation_id}/artifacts/{kind}`

See [docs/API.md](docs/API.md) for examples.

## Testing

Backend tests:

```powershell
cd backend
pytest
```

Runner tests:

```powershell
cd cad-runner
pytest
```

Frontend tests:

```powershell
cd frontend
npm test
```

## Scope

This is a local single-user prototype. It does not include authentication, multi-user isolation, image input, engineering simulation, production deployment, or a hardened multi-tenant sandbox.

Generated CadQuery code runs directly on the local machine in a subprocess. Use this only for local development with trusted prompts and provider settings.
