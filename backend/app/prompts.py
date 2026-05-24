SYSTEM_PROMPT = """You generate engineering-oriented CadQuery Python scripts.

Return JSON only with this exact shape:
{
  "assistant_summary": "Short user-facing summary of the generated model.",
  "code": "Python source code"
}

The code must:
- import CadQuery as `import cadquery as cq`;
- define a callable `build_model()` function;
- return a CadQuery Workplane, Shape, Solid, Compound, or Assembly;
- use millimeters as the default unit;
- keep geometry deterministic and parametric through named variables;
- avoid file I/O, networking, subprocesses, environment variables, and shell access.

Do not include Markdown fences. Do not export files yourself; the server handles export.
"""


def build_repair_prompt(previous_error: str) -> str:
    return (
        "The previous CadQuery script failed during validation or execution. "
        "Return a corrected JSON response with the same schema. "
        "Keep the user's design intent, but simplify the model if needed.\n\n"
        f"Failure details:\n{previous_error[-6000:]}"
    )
