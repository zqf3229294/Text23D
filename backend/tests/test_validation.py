import pytest

from app.validation import CodeValidationError, validate_cadquery_code


def test_valid_cadquery_code_passes():
    validate_cadquery_code(
        'import cadquery as cq\n\ndef build_model():\n    return cq.Workplane("XY").box(1, 2, 3)\n'
    )


def test_missing_build_model_fails():
    with pytest.raises(CodeValidationError, match="build_model"):
        validate_cadquery_code('import cadquery as cq\nresult = cq.Workplane("XY").box(1, 1, 1)\n')


def test_forbidden_import_fails():
    with pytest.raises(CodeValidationError, match="Import is not allowed"):
        validate_cadquery_code('import os\n\ndef build_model():\n    return "bad"\n')


def test_forbidden_function_call_fails():
    with pytest.raises(CodeValidationError, match="Blocked function call"):
        validate_cadquery_code('import cadquery as cq\n\ndef build_model():\n    return eval("1")\n')
