# Text23D Repository Structure

This guide introduces the source layout of the entire Text23D Mechanical
platform. It covers the version-controlled application code and the local
runtime directories created while developing or running the platform.

## Platform at a glance

| Path | Responsibility | Main technology |
| --- | --- | --- |
| `backend/` | HTTP/WebSocket API, generation orchestration, persistence, LLM adapters, validation, and rendering helpers | Python, FastAPI, SQLite |
| `frontend/` | Conversational CAD workbench and interactive model preview | Angular, TypeScript, Three.js |
| `cad-runner/` | Isolated command-line entry point for generated CadQuery scripts | Python, CadQuery |
| `freecad-runner/` | One-shot and persistent-worker entry points for generated FreeCAD scripts | Python, FreeCAD |
| `docs/` | Cross-platform architecture, API, and repository documentation | Markdown |
| `data/` | Local database, uploads, generated scripts, artifacts, previews, and logs | Runtime data; ignored by Git |

The normal request path is:

```text
Angular UI
  -> FastAPI routes
  -> generation service
  -> LLM provider or FreeCAD agent
  -> CadQuery/FreeCAD runner
  -> data/ artifacts and SQLite state
  -> API/WebSocket updates
  -> Three.js preview
```

## Annotated tree

The tree below represents the source-controlled platform. `data/` is also
shown because it is an important runtime boundary, although its contents are
intentionally not committed.

```text
Text23D/
|-- .env.example                   # Template for all TEXT23D_* settings
|-- .gitignore                     # Python, Angular, environment, and runtime exclusions
|-- LICENSE                        # MIT license
|-- NOTICE                         # Project attribution notice
|-- README.md                      # Product overview, setup, and operating modes
|
|-- backend/                       # FastAPI application and backend test suite
|   |-- README.md                  # Backend setup and environment reference
|   |-- pyproject.toml             # Python package metadata and dependency groups
|   |-- app/
|   |   |-- __init__.py            # Marks app as a Python package
|   |   |-- main.py                # Application composition, CORS, health route, static UI
|   |   |-- api.py                 # REST and WebSocket endpoints
|   |   |-- config.py              # Typed TEXT23D_* configuration
|   |   |-- models.py              # Pydantic API models, statuses, and event types
|   |   |-- db.py                  # SQLite schema and repository operations
|   |   |-- serializers.py         # Database-row to API-model conversion
|   |   |-- service.py             # Generation lifecycle, retries, cancellation, artifacts
|   |   |-- validation.py          # AST validation for generated CAD Python
|   |   |-- prompts.py             # CAD-kernel system and repair prompts
|   |   |-- runner.py              # Backend subprocess adapters for both CAD kernels
|   |   |-- agent.py               # Agent-mode LLM/tool loop and event reporting
|   |   |-- freecad_agent.py       # FreeCAD sessions, tools, worker/replay gateways
|   |   |-- solid_view_renderer.py # CPU rendering from FreeCAD solid edge data
|   |   |-- pyvista_renderer.py    # PyVista STL rendering with fallback handling
|   |   |-- pyvista_render_worker.py
|   |   |                           # Subprocess entry point for PyVista rendering
|   |   |-- software_stl_renderer.py
|   |   |                           # Dependency-light CPU renderer for STL fallback
|   |   `-- providers/             # LLM-provider abstraction layer
|   |       |-- __init__.py         # Exposes provider construction API
|   |       |-- base.py             # Shared response model and provider protocol
|   |       |-- factory.py          # Selects a provider from configuration
|   |       |-- mock.py             # Deterministic local/test provider
|   |       |-- openai_provider.py  # OpenAI Responses API adapter
|   |       |-- anthropic_provider.py
|   |       |                       # Anthropic Messages API adapter
|   |       |-- chat_completions_provider.py
|   |       |                       # DeepSeek/generic OpenAI-compatible adapter
|   |       |-- multimodal.py       # Provider-specific image/message formatting
|   |       `-- json_utils.py       # Structured CAD response parsing
|   `-- tests/
|       |-- __init__.py
|       |-- conftest.py             # Shared settings, fake runner, and app fixtures
|       |-- test_api.py             # HTTP, upload, generation, stream, cancellation tests
|       |-- test_agent_mode.py      # FreeCAD agent/worker/tool-loop coverage
|       |-- test_generation_repair.py
|       |                           # Validation failure and repair-retry coverage
|       |-- test_local_runner.py    # Runner selection and subprocess command tests
|       |-- test_multimodal_provider.py
|       |                           # Image-aware provider message formatting tests
|       |-- test_provider_factory.py
|       |                           # Provider selection/configuration tests
|       |-- test_pyvista_renderer.py
|       |                           # PyVista failure/fallback coverage
|       |-- test_solid_view_renderer.py
|       |                           # Solid projection renderer coverage
|       `-- test_validation.py      # Generated-code safety checks
|
|-- cad-runner/                     # CadQuery execution boundary
|   |-- README.md                   # Runner contract and smoke-test instructions
|   |-- run_cadquery.py             # Loads build_model(); exports STEP and GLB
|   |-- examples/
|   |   `-- cube_with_hole.py       # Minimal valid generated-script example
|   `-- tests/
|       `-- test_run_cadquery.py    # CLI validation and real-export tests
|
|-- freecad-runner/                 # FreeCAD execution boundary
|   |-- README.md                   # One-shot runner and worker instructions
|   |-- run_freecad.py              # One-shot FCStd, STEP, and STL exporter
|   |-- freecad_worker.py           # Persistent JSON-lines agent worker
|   `-- examples/
|       `-- cube_with_hole.py       # Minimal valid FreeCAD script example
|
|-- frontend/                       # Standalone Angular application
|   |-- README.md                   # Frontend setup and backend URL notes
|   |-- package.json                # npm scripts and direct dependencies
|   |-- package-lock.json           # Reproducible npm dependency lock
|   |-- angular.json                # Build, serve, test, asset, and budget settings
|   |-- karma.conf.js               # Karma/Jasmine browser-test configuration
|   |-- tsconfig.json               # Shared TypeScript compiler settings
|   |-- tsconfig.app.json           # Application TypeScript target
|   |-- tsconfig.spec.json          # Test TypeScript target
|   |-- public/
|   |   |-- .gitkeep                # Keeps the static public directory in Git
|   |   `-- web.config              # IIS API proxy and Angular fallback rewrites
|   `-- src/
|       |-- index.html              # Browser document shell
|       |-- main.ts                 # Angular bootstrap entry point
|       |-- styles.css              # Application-wide styling and design tokens
|       |-- assets/
|       |   `-- images/
|       |       |-- Favicon.png     # Browser icon
|       |       |-- Logo.png        # Graphic product mark
|       |       `-- Logo_Text.png   # Product wordmark
|       |-- environments/
|       |   |-- environment.ts      # Development API base URL
|       |   `-- environment.prod.ts # Same-origin production API base URL
|       `-- app/
|           |-- app.config.ts       # Root Angular providers
|           |-- app.component.ts    # Conversation/generation state coordinator
|           |-- app.component.html  # Workbench layout composition
|           |-- app.component.css   # Root workbench and footer styles
|           |-- models.ts           # Frontend API/domain interfaces
|           |-- services/
|           |   `-- api.service.ts  # REST, artifact, upload, and WebSocket URLs
|           `-- components/
|               |-- chat-panel/
|               |   |-- chat-panel.component.ts
|               |   |               # Prompt, images, progress, cancellation, downloads
|               |   |-- chat-panel.component.html
|               |   |               # Chat and generation-progress markup
|               |   |-- chat-panel.component.css
|               |   |               # Chat panel styling
|               |   `-- chat-panel.component.spec.ts
|               |                   # Chat panel behavior tests
|               `-- model-viewer/
|                   |-- model-viewer.component.ts
|                   |               # Three.js scene plus GLB/STL loading
|                   |-- model-viewer.component.html
|                   |               # Viewer canvas and overlays
|                   |-- model-viewer.component.css
|                   |               # Viewer styling
|                   `-- model-viewer.component.spec.ts
|                                   # Viewer state and artifact URL tests
|
|-- docs/
|   |-- API.md                       # Endpoint contracts and examples
|   |-- ARCHITECTURE.md              # Script/agent flows, storage, and safety
|   `-- FOLDER_STRUCTURE.md          # This repository map
|
`-- data/                            # Local runtime state; ignored by Git
    |-- text23d.sqlite3              # Default SQLite database
    `-- artifacts/
        `-- conversations/
            `-- <conversation-id>/
                |-- attachments/     # Uploaded reference images
                |-- freecad-worker.log
                |                    # Persistent worker protocol log, when used
                `-- generations/
                    `-- <generation-id>/
                        |-- attempt_<n>/          # Script mode
                        |   |-- model.py
                        |   |-- model.step
                        |   |-- preview.glb or preview.stl
                        |   |-- model.FCStd       # FreeCAD only
                        |   |-- objects.json      # FreeCAD only
                        |   `-- run.log or validation.log
                        `-- agent/                # FreeCAD agent mode
                            |-- view_<n>.png or .svg
                            |                       # View assets referenced by events
                            |-- worker-tool-calls.log or tool-calls.log
                            `-- final/
                                |-- live_session.py
                                |-- objects.json
                                |-- model.FCStd
                                |-- model.step
                                `-- preview.stl
```

Runtime artifact details vary by generation mode and CAD kernel. Script-mode
attempts live below `attempt_<n>/`; agent-mode working files and final exports
live below `agent/` and `agent/final/`.

## Backend responsibilities

The backend uses a layered flow so HTTP concerns, orchestration, and CAD
execution stay separate:

1. `main.py` creates the application and wires configuration, persistence,
   provider, runner, session manager, agent, and generation service together.
2. `api.py` validates HTTP/WebSocket input and delegates state changes.
3. `service.py` owns generation status, repair attempts, cancellation, and the
   choice between script mode and agent mode.
4. `providers/` turns conversation context into generated CAD source. In agent
   mode, `agent.py` instead runs the supported model/tool loop.
5. `validation.py` checks generated Python before it reaches a CAD process.
6. `runner.py` invokes `cad-runner/` or `freecad-runner/` as a subprocess.
7. `db.py` and the configured storage directory preserve API state and files.

The CAD runners are deliberately outside `backend/app/`. They are executable
boundaries that may need their own Python interpreter because CadQuery and
FreeCAD have native/runtime-specific dependencies.

## Frontend responsibilities

`AppComponent` is the page-level coordinator. It creates the conversation,
uploads optional images, submits prompts, polls generation state, consumes live
generation events, and passes state into two focused child components:

- `ChatPanelComponent` owns prompt composition, attachment selection, event
  history, status display, cancellation, and artifact download links.
- `ModelViewerComponent` owns the Three.js scene and loads the available GLB
  (CadQuery) or STL (FreeCAD) preview.
- `ApiService` is the single browser-side boundary for backend URLs and calls.
- `models.ts` mirrors the backend's public API shapes.

## CAD execution modes

| Mode | Backend entry | Execution entry | Main outputs |
| --- | --- | --- | --- |
| CadQuery script | `service.py` -> `LocalCadRunner` | `cad-runner/run_cadquery.py` | `model.step`, `preview.glb` |
| FreeCAD script | `service.py` -> `LocalFreeCADRunner` | `freecad-runner/run_freecad.py` | `model.FCStd`, `model.step`, `preview.stl` |
| FreeCAD agent, worker | `agent.py` -> `WorkerFreeCADSession` | `freecad-runner/freecad_worker.py` | Live document updates, views, final FreeCAD artifacts |
| FreeCAD agent, replay | `agent.py` -> `ReplayFreeCADSession` | One-shot FreeCAD runner | Rebuilt state and final FreeCAD artifacts |

## Where to make common changes

| Change | Start here | Often related |
| --- | --- | --- |
| Add or modify an endpoint | `backend/app/api.py` | `models.py`, `serializers.py`, `docs/API.md`, `test_api.py` |
| Change database state | `backend/app/db.py` | `models.py`, `serializers.py`, backend tests |
| Change the generation lifecycle | `backend/app/service.py` | `agent.py`, `runner.py`, generation tests |
| Add an LLM provider | `backend/app/providers/` | `config.py`, `.env.example`, provider tests |
| Change generated-code rules | `backend/app/validation.py` | `prompts.py`, `test_validation.py` |
| Add a FreeCAD agent tool | `backend/app/freecad_agent.py` | `agent.py`, `freecad_worker.py`, `test_agent_mode.py` |
| Change CAD exports | The applicable runner directory | `backend/app/runner.py`, viewer artifact handling |
| Change API calls or shared UI types | `frontend/src/app/services/api.service.ts` | `frontend/src/app/models.ts` |
| Change chat/generation UX | `frontend/src/app/components/chat-panel/` | `app.component.ts` |
| Change 3D preview behavior | `frontend/src/app/components/model-viewer/` | Three.js dependencies and viewer tests |
| Change deployment-time frontend routing | `frontend/public/web.config` | Production environment settings |

## Local-only and generated directories

The following paths may appear in a working copy but are not part of the
canonical source tree:

- `.env`: local settings and secrets copied from `.env.example`.
- `.venv/`, `.venv-*`, `venv/`: Python environments, including a separate
  CadQuery interpreter such as `.venv-cadquery/`.
- `frontend/node_modules/`: installed npm packages.
- `frontend/dist/`: production Angular build output. When present, FastAPI can
  serve `frontend/dist/text23d-frontend/browser/`.
- `frontend/.angular/` and `coverage/`: Angular caches and test coverage.
- `data/` and `backend/data/`: SQLite databases and generated/uploaded files.
- `.pytest_cache/`, `.pytest-tmp*/`, `__pycache__/`, `.ruff_cache/`, and
  `.mypy_cache/`: test, bytecode, lint, and type-check caches.

Do not add generated artifacts, installed dependencies, local databases, or
secrets to the source tree. The repository's `.gitignore` is the authoritative
list of exclusions.

## Suggested reading order

For a new contributor:

1. Start with the root `README.md` to run the platform.
2. Use this document to find the subsystem you need.
3. Read `docs/ARCHITECTURE.md` for runtime behavior and safety boundaries.
4. Read `docs/API.md` when changing frontend/backend communication.
5. Use each subsystem's `README.md` for its environment and smoke tests.
