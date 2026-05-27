# Text23D Mechanical Architecture

## Runtime flow

1. Angular creates a conversation through `POST /api/conversations`.
2. The user submits a prompt through `POST /api/conversations/{id}/messages`.
3. FastAPI stores the user message, creates a queued generation, and starts a background generation task.
4. The generation service sends conversation context to the configured provider adapter.
5. The provider returns JSON with `assistant_summary` and CAD-kernel-specific Python code defining `build_model()`.
6. The backend validates the code with AST checks and writes it into a per-generation artifact folder.
7. The selected local runner executes the script in a subprocess.
8. CadQuery exports `model.step` and `preview.glb`; FreeCAD exports `model.FCStd`, `model.step`, and `preview.stl`.
9. Angular polls `GET /api/generations/{id}` and loads GLB or STL through Three.js when ready.

## Storage

SQLite stores conversations, messages, generation state, artifact paths, and errors. The filesystem stores generated scripts, STEP files, GLB previews, and logs under `TEXT23D_STORAGE_DIR`.

The default local paths are:

- database: `data/text23d.sqlite3`
- artifacts: `data/artifacts`

## Provider adapters

Provider selection is controlled by `TEXT23D_LLM_PROVIDER`:

- `mock`: deterministic local provider for development and tests.
- `openai`: uses the OpenAI Python SDK Responses API path with structured output parsing.
- `anthropic`: uses the Anthropic Python SDK Messages API and parses JSON from the response.

All providers implement the same internal contract: conversation messages in, `assistant_summary` plus CadQuery source out.

## Safety boundary

The backend performs AST validation before execution and blocks unsafe imports/calls. Generated CadQuery code now runs directly on the local machine in a subprocess, so this is not a security sandbox.

- subprocess timeout from the backend
- per-generation output directory

This is suitable for a local single-user MVP. Do not expose this mode to untrusted users or multi-tenant production traffic.
