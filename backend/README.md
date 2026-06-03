# Text23D Backend

FastAPI service for conversations, LLM-driven CAD generation, FreeCAD agent mode, and artifact delivery.

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
- `TEXT23D_GENERATION_MODE=script|agent`
- `TEXT23D_IMAGE_INPUT_ENABLED=false|true`
- `TEXT23D_IMAGE_MAX_UPLOAD_BYTES=5242880`
- `TEXT23D_IMAGE_MAX_COUNT_PER_MESSAGE=4`
- `TEXT23D_IMAGE_ALLOWED_CONTENT_TYPES=["image/png","image/jpeg","image/webp"]`
- `TEXT23D_OPENAI_API_KEY=...`
- `TEXT23D_ANTHROPIC_API_KEY=...`
- `TEXT23D_DEEPSEEK_API_KEY=...`
- `TEXT23D_DEEPSEEK_SUPPORTS_IMAGES=false|true`
- `TEXT23D_CAD_KERNEL=cadquery|freecad`
- `TEXT23D_CAD_RUNNER_PYTHON=...` if CadQuery lives in a separate Python environment
- `TEXT23D_CAD_RUNNER_SCRIPT=...` if the runner script is moved
- `TEXT23D_FREECAD_PYTHON=...` if using the FreeCAD runner or worker; prefer FreeCAD's bundled `python.exe` for agent mode
- `TEXT23D_FREECAD_AGENT_BACKEND=worker|replay`
- `TEXT23D_FREECAD_GUI_EXECUTABLE=...` optional fallback when the worker Python path is not set
- `TEXT23D_FREECAD_WORKER_VIEW_BACKEND=summary|gui`

DeepSeek V4 example:

```text
TEXT23D_LLM_PROVIDER=deepseek
TEXT23D_DEEPSEEK_API_KEY=your_deepseek_key
TEXT23D_DEEPSEEK_BASE_URL=https://api.deepseek.com
TEXT23D_DEEPSEEK_MODEL=deepseek-v4-flash
TEXT23D_DEEPSEEK_SUPPORTS_IMAGES=false
```

Use `deepseek-v4-pro` instead of `deepseek-v4-flash` if you want the more capable V4 model.

For another OpenAI-compatible API:

```text
TEXT23D_LLM_PROVIDER=openai_compatible
TEXT23D_OPENAI_COMPATIBLE_API_KEY=your_key
TEXT23D_OPENAI_COMPATIBLE_BASE_URL=https://provider.example.com
TEXT23D_OPENAI_COMPATIBLE_MODEL=model-id
TEXT23D_OPENAI_COMPATIBLE_SUPPORTS_IMAGES=false
```

FreeCAD generation example:

```text
TEXT23D_GENERATION_MODE=script
TEXT23D_CAD_KERNEL=freecad
TEXT23D_FREECAD_PYTHON=C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe
```

The FreeCAD path returns a native `model.FCStd` artifact for manual editing, plus STEP and STL preview artifacts.

FreeCAD agent mode example:

```text
TEXT23D_GENERATION_MODE=agent
TEXT23D_CAD_KERNEL=freecad
TEXT23D_LLM_PROVIDER=anthropic
TEXT23D_ANTHROPIC_API_KEY=your_anthropic_key
TEXT23D_FREECAD_AGENT_BACKEND=worker
TEXT23D_FREECAD_PYTHON=C:\Program Files\FreeCAD 1.1\bin\python.exe
TEXT23D_FREECAD_GUI_EXECUTABLE=
TEXT23D_FREECAD_WORKER_VIEW_BACKEND=summary
TEXT23D_AGENT_MAX_TOOL_CALLS=30
TEXT23D_AGENT_MAX_RUNTIME_SECONDS=300
TEXT23D_AGENT_MAX_CODE_CHARS=12000
```

Agent mode V1 supports `mock` for local smoke tests and `anthropic` for Claude-style tool use. The default FreeCAD agent backend starts a persistent FreeCAD worker per conversation, so follow-up prompts can modify the same live document. `get_view` returns a stable SVG object summary by default because native FreeCAD viewport PNG capture can hang on some Windows local sessions. Set `TEXT23D_FREECAD_WORKER_VIEW_BACKEND=gui` only when that path is stable on your machine. On Windows, point `TEXT23D_FREECAD_PYTHON` to FreeCAD's bundled `python.exe`; `FreeCAD.exe` can open a GUI window without answering the backend's stdin/stdout worker protocol. Set `TEXT23D_FREECAD_AGENT_BACKEND=replay` to use the older per-tool `FreeCADCmd` replay fallback.

Linux/headless deployments should run the same worker under a virtual display such as `xvfb-run` or a managed `Xvfb :99` with `DISPLAY=:99`. Text23D does not orchestrate Xvfb in this Windows-first version.

Image input example:

```text
TEXT23D_IMAGE_INPUT_ENABLED=true
TEXT23D_IMAGE_MAX_UPLOAD_BYTES=5242880
TEXT23D_IMAGE_MAX_COUNT_PER_MESSAGE=4
TEXT23D_IMAGE_ALLOWED_CONTENT_TYPES=["image/png","image/jpeg","image/webp"]
```

The browser uploads images as conversation attachments before submitting the chat message. The backend stores them locally, links them to the message, and includes them in provider context. Anthropic receives native image blocks; OpenAI-compatible providers default to a text-only attachment summary and only receive `image_url` blocks when `TEXT23D_OPENAI_COMPATIBLE_SUPPORTS_IMAGES=true` or `TEXT23D_DEEPSEEK_SUPPORTS_IMAGES=true`.

## Tests

```powershell
cd backend
pytest
```
