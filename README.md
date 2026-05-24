# Text23D Mechanical

Text23D Mechanical is an AI-assisted mechanical design platform for generating and refining 3D parametric CAD models from conversational input.

This repository currently contains the first local MVP scaffold:

- Angular frontend with a left-side chat panel and right-side Three.js CAD preview.
- Python/FastAPI backend for conversations, generation jobs, artifacts, and provider adapters.
- Docker-isolated CadQuery runner that exports `STEP` for CAD download and `GLB` for browser preview.
- SQLite plus filesystem storage for local single-user development.

The default LLM provider is `mock`, so the stack can be tested before connecting OpenAI or Anthropic credentials.

## Repository Layout

```text
backend/      FastAPI API, SQLite persistence, provider adapters, tests
cad-runner/   Docker image that executes generated CadQuery scripts
frontend/     Angular standalone app with Three.js preview
docs/         Architecture and API notes
data/         Local runtime files, ignored by Git
```

## Prerequisites

- Python 3.11+
- Node.js LTS and npm
- Docker Desktop

On this machine, Node/npm and Docker were not available on PATH during scaffolding, and `python` resolved to the Windows app alias instead of a working interpreter. Install or fix those tools before running the full app locally.

## Quick Start

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Build the CadQuery runner image:

```powershell
docker build -t text23d-cad-runner:local cad-runner
```

Start the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
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
