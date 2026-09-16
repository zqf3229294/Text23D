# Text23D Mechanical

Text23D Mechanical is an AI-assisted mechanical design platform for generating and refining 3D parametric CAD models from conversational input.

This repository currently contains the first local MVP scaffold:

- Angular frontend with a left-side chat panel and right-side Three.js CAD preview.
- Python/FastAPI backend for conversations, generation jobs, artifacts, and provider adapters.
- Local CadQuery runner that exports `STEP` for CAD download and `GLB` for browser preview.
- Optional FreeCAD runner that exports editable `FCStd`, `STEP`, and `STL` preview files.
- Optional FreeCAD agent mode that streams backend tool progress and view updates to the browser.
- SQLite plus filesystem storage for local single-user development.

The default LLM provider is `mock`, so the stack can be tested before connecting OpenAI or Anthropic credentials.

## Live Demo

A public demo is hosted at [https://www.littletreenuts.com](https://www.littletreenuts.com).
Use it to try the browser-based 3D CAD generation workflow without setting up the project locally.
This is an early beta demo. Features may be incomplete or change without notice.

## Contact

Questions or suggestions about this site's design or construction? Email
[info@littletreenuts.com](mailto:info@littletreenuts.com).

## Repository Layout

```text
backend/      FastAPI API, SQLite persistence, provider adapters, tests
cad-runner/   Local script that executes generated CadQuery scripts
freecad-runner/ Local script that executes generated FreeCAD scripts
frontend/     Angular standalone app with Three.js preview
docs/         Architecture and API notes
data/         Local runtime files, ignored by Git
```

See [docs/FOLDER_STRUCTURE.md](docs/FOLDER_STRUCTURE.md) for an annotated map
of the complete repository, subsystem boundaries, and generated local paths.

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
- `deepseek`: DeepSeek API through its OpenAI-compatible Chat Completions endpoint.
- `openai_compatible`: generic OpenAI-compatible Chat Completions provider.

For real providers, add the corresponding API key and model value in `.env`.

## CAD Kernels

Use `TEXT23D_CAD_KERNEL` to choose the script target:

```text
TEXT23D_CAD_KERNEL=cadquery
```

or:

```text
TEXT23D_CAD_KERNEL=freecad
TEXT23D_FREECAD_PYTHON=C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe
```

CadQuery produces `STEP` and `GLB`. FreeCAD produces `FCStd`, `STEP`, and `STL`; the `FCStd` artifact keeps the FreeCAD document tree for manual editing.

## Generation Modes

The default mode is one-shot script generation:

```text
TEXT23D_GENERATION_MODE=script
```

Agent mode is opt-in and currently targets FreeCAD:

```text
TEXT23D_GENERATION_MODE=agent
TEXT23D_CAD_KERNEL=freecad
TEXT23D_LLM_PROVIDER=anthropic
TEXT23D_ANTHROPIC_API_KEY=your_anthropic_key
TEXT23D_ANTHROPIC_AGENT_PROMPT_CACHE=true
TEXT23D_ANTHROPIC_AGENT_PROMPT_CACHE_TTL=5m
TEXT23D_FREECAD_AGENT_BACKEND=worker
TEXT23D_FREECAD_PYTHON=C:\Program Files\FreeCAD 1.1\bin\python.exe
TEXT23D_FREECAD_GUI_EXECUTABLE=
TEXT23D_FREECAD_WORKER_VIEW_BACKEND=pyvista
```

In agent mode the backend owns the LLM key, runs the tool loop, executes the FreeCAD tool subset, stores intermediate events, and streams status/view updates to the browser over WebSocket. The default FreeCAD agent backend uses a persistent worker per conversation for live document edits. `TEXT23D_FREECAD_WORKER_VIEW_BACKEND=pyvista` exports a temporary FreeCAD STL preview and renders a backend PNG with PyVista, then sends that PNG back to Claude in Anthropic agent mode. Install it with `python -m pip install -e ".[render]"` from `backend`. If VTK/OpenGL cannot initialize, the backend falls back to a CPU STL renderer; if mesh rendering fails entirely, it returns a stable SVG object summary. On Windows, set `TEXT23D_FREECAD_PYTHON` to FreeCAD's bundled `python.exe`; launching the worker through `FreeCAD.exe` can open the GUI without responding to the backend worker protocol. Set `TEXT23D_FREECAD_WORKER_VIEW_BACKEND=gui` only when native FreeCAD viewport PNG screenshots are stable on your machine. Use `TEXT23D_LLM_PROVIDER=mock` for a local smoke test without an external model, or set `TEXT23D_FREECAD_AGENT_BACKEND=replay` to use the older `FreeCADCmd` replay fallback.

For Anthropic agent mode, `TEXT23D_ANTHROPIC_AGENT_PROMPT_CACHE=true` enables automatic prompt caching across the Claude tool loop. Start with `TEXT23D_ANTHROPIC_AGENT_PROMPT_CACHE_TTL=5m`; switch to `1h` only when long pauses between follow-up turns matter enough to justify the higher cache-write price.

DeepSeek agent mode uses the OpenAI-compatible Responses API. Use its vision model to let the agent inspect FreeCAD view screenshots and user image attachments:

```text
TEXT23D_GENERATION_MODE=agent
TEXT23D_CAD_KERNEL=freecad
TEXT23D_LLM_PROVIDER=deepseek
TEXT23D_DEEPSEEK_API_KEY=your_deepseek_key
TEXT23D_DEEPSEEK_BASE_URL=https://api.deepseek.com
TEXT23D_DEEPSEEK_MODEL=deepseek-v4-flash-vision-exp
TEXT23D_DEEPSEEK_SUPPORTS_IMAGES=true
TEXT23D_FREECAD_AGENT_BACKEND=worker
```

`deepseek-v4-flash-vision-exp` is the DeepSeek model that accepts image inputs. Keep `TEXT23D_DEEPSEEK_SUPPORTS_IMAGES=false` only for text-only DeepSeek models; agent tool calls still work, but FreeCAD screenshots are sent as metadata rather than images.

For future Linux/headless deployment, run the worker under `xvfb-run` or a managed `Xvfb :99` with `DISPLAY=:99`; this Windows-first version does not manage Xvfb itself.

Image input remains off by default behind a feature flag:

```text
TEXT23D_IMAGE_INPUT_ENABLED=false
TEXT23D_IMAGE_MAX_UPLOAD_BYTES=5242880
TEXT23D_IMAGE_MAX_COUNT_PER_MESSAGE=4
TEXT23D_IMAGE_ALLOWED_CONTENT_TYPES=["image/png","image/jpeg","image/webp"]
```

When enabled, the frontend shows an image attachment control. Images are uploaded to the backend first, linked to the chat message, stored under the conversation artifact folder, and passed to multimodal-capable providers as image context. Provider/model support still matters: Anthropic receives native image blocks, OpenAI receives Responses API image blocks, and OpenAI-compatible providers default to text-only attachment summaries unless their image support flag is enabled.

DeepSeek V4 example:

```text
TEXT23D_LLM_PROVIDER=deepseek
TEXT23D_DEEPSEEK_API_KEY=your_deepseek_key
TEXT23D_DEEPSEEK_BASE_URL=https://api.deepseek.com
TEXT23D_DEEPSEEK_MODEL=deepseek-v4-flash
TEXT23D_DEEPSEEK_SUPPORTS_IMAGES=false
```

Use `deepseek-v4-pro` for higher-quality CAD script generation if the extra cost is acceptable.

## API

Core endpoints:

- `POST /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `POST /api/conversations/{conversation_id}/messages`
- `GET /api/generations/{generation_id}`
- `GET /api/generations/{generation_id}/events`
- `WS /api/generations/{generation_id}/stream`
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

## License

Text23D Mechanical is released under the MIT License. See [LICENSE](LICENSE)
for details.

If you copied or adapted source from MIT-licensed upstream projects, keep the
upstream copyright and license notices with those portions of the code. See
[NOTICE](NOTICE) for the project attribution note.

## Scope

This is a local single-user prototype. It does not include authentication, multi-user isolation, image input, engineering simulation, production deployment, or a hardened multi-tenant sandbox.

Generated CadQuery and FreeCAD code runs directly on the local machine in subprocesses. Agent mode logs tool calls and limits runtime/tool/code size, but it is still a local prototype rather than a hardened sandbox.
