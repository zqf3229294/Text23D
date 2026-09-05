# Text23D Mechanical Architecture

## Runtime flow

### Script mode

1. Angular creates a conversation through `POST /api/conversations`.
2. The user submits a prompt through `POST /api/conversations/{id}/messages`.
3. FastAPI stores the user message, creates a queued generation, and starts a background generation task.
4. The generation service sends conversation context to the configured provider adapter.
5. The provider returns JSON with `assistant_summary` and CAD-kernel-specific Python code defining `build_model()`.
6. The backend validates the code with AST checks and writes it into a per-generation artifact folder.
7. The selected local runner executes the script in a subprocess.
8. CadQuery exports `model.step` and `preview.glb`; FreeCAD exports `model.FCStd`, `model.step`, and `preview.stl`.
9. Angular polls `GET /api/generations/{id}` and loads GLB or STL through Three.js when ready.

### FreeCAD agent mode

Agent mode is enabled only with:

```text
TEXT23D_GENERATION_MODE=agent
TEXT23D_CAD_KERNEL=freecad
```

The backend becomes the agent host:

1. FastAPI creates a generation and starts `CADAgent`.
2. The agent opens a server-managed `FreeCADSession`.
3. For `mock`, the agent runs a deterministic local tool sequence. For `anthropic`, the agent calls Claude with FreeCAD tool definitions. For `deepseek`, the agent calls DeepSeek's OpenAI-compatible Responses API with equivalent function definitions.
4. Tool calls are dispatched through the FreeCAD gateway: `create_document`, `execute_code`, `get_objects`, `get_object`, `get_view`, and `export_model`.
5. The default gateway starts a persistent GUI-capable FreeCAD worker per conversation and communicates over JSON lines on stdin/stdout. On Windows this should launch through FreeCAD's bundled `python.exe`; `FreeCAD.exe` is only a fallback because GUI executables may not keep stdout connected.
6. The worker keeps the live document open across generations, executes validated snippets directly, and exports `FCStd`, `STEP`, and `STL`. For `get_view`, `TEXT23D_FREECAD_WORKER_VIEW_BACKEND=pyvista` exports a temporary STL mesh and renders a backend PNG screenshot with PyVista, falling back to a CPU STL renderer when VTK/OpenGL is unavailable; Anthropic and vision-enabled DeepSeek agent modes send that PNG back to the model as an image tool result. `summary` returns a stable SVG object summary, and native FreeCAD viewport screenshots remain available with `TEXT23D_FREECAD_WORKER_VIEW_BACKEND=gui`.
7. `TEXT23D_FREECAD_AGENT_BACKEND=replay` keeps the older per-tool `FreeCADCmd` script replay fallback.
8. Each status, tool call, result, view asset, error, and final artifact event is stored in SQLite.
9. Angular loads event history with `GET /api/generations/{id}/events` and receives live updates through `WS /api/generations/{id}/stream`.
10. Final artifacts remain server generated: `model.FCStd`, `model.step`, `preview.stl`, script, and tool log.

## Storage

SQLite stores conversations, messages, image attachment metadata, generation state, generation events, artifact paths, and errors. The filesystem stores uploaded image attachments, generated scripts, STEP files, GLB/STL previews, FreeCAD files, event assets, and logs under `TEXT23D_STORAGE_DIR`.

The default local paths are:

- database: `data/text23d.sqlite3`
- artifacts: `data/artifacts`

## Provider adapters

Provider selection is controlled by `TEXT23D_LLM_PROVIDER`:

- `mock`: deterministic local provider for development and tests.
- `openai`: uses the OpenAI Python SDK Responses API path with structured output parsing.
- `anthropic`: uses the Anthropic Python SDK Messages API and parses JSON from the response.
- `deepseek`: uses DeepSeek through an OpenAI-compatible Chat Completions path.
- `openai_compatible`: generic OpenAI-compatible Chat Completions provider.

Script-mode providers implement the same internal contract: conversation messages in, `assistant_summary` plus CAD-kernel-specific source out.

Agent mode supports `mock`, `anthropic`, and `deepseek`. DeepSeek vision agent mode requires `deepseek-v4-flash-vision-exp` with `TEXT23D_DEEPSEEK_SUPPORTS_IMAGES=true`; it receives FreeCAD screenshots as `input_image` function outputs. Generic OpenAI-compatible providers continue to work in script mode.

Image input is guarded by `TEXT23D_IMAGE_INPUT_ENABLED`. When enabled, the browser uploads raw image bytes to the backend before message submission. The message references uploaded attachment IDs, and provider adapters convert stored images into the provider's multimodal format.

## Safety boundary

The backend performs AST validation before execution and blocks unsafe imports/calls. Generated CadQuery and FreeCAD code now runs directly on the local machine in subprocesses, so this is not a security sandbox.

- subprocess timeout from the backend
- per-generation output directory
- agent max tool calls, runtime, and code size limits
- backend-only LLM API keys and tool execution

This is suitable for a local single-user MVP. Do not expose this mode to untrusted users or multi-tenant production traffic.
