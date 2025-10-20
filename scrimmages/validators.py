# scrimmages/validators.py
from __future__ import annotations
from typing import Any, Dict, Tuple, Optional
from pydantic import BaseModel, Field, ValidationError, create_model, conint, confloat, constr

PY_TYPES = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}

def _pydantic_type(field: Dict[str, Any]):
    py = field.get("py_type", "str")
    base = PY_TYPES.get(py, str)
    # numeric bounds
    if base is int:
        ge, le = field.get("ge"), field.get("le")
        return conint(ge=ge) if ge is not None or le is not None else int
    if base is float:
        ge, le = field.get("ge"), field.get("le")
        return confloat(ge=ge) if ge is not None or le is not None else float
    # regex/choices for strings
    if base is str:
        regex = field.get("regex")
        if regex:
            return constr(regex=regex)
        return str
    return base

def build_model_from_schema(schema: Dict[str, Any]):
    """
    schema: dict[field_name] -> {py_type, required, default, choices, ge/le/regex}
    """
    fields: Dict[str, Tuple[Any, Any]] = {}
    for name, spec in (schema or {}).items():
        typ = _pydantic_type(spec)
        required = spec.get("required", False)
        default = ... if required else spec.get("default", None)
        # choices (enum) handled via validation in create_model validators
        fields[name] = (typ, default)
    return create_model("ScrimmageDynamicModel", **fields)  # type: ignore

def validate_custom_fields(scrimmage_type, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    schema = scrimmage_type.custom_field_schema or {}
    Model = build_model_from_schema(schema)
    try:
        Model(**(data or {}))
    except ValidationError as e:
        # return error structure friendly to DRF
        return {err["loc"][0]: err["msg"] for err in e.errors()}
    # enforce 'choices' manually if defined
    for k, spec in schema.items():
        if "choices" in spec and k in (data or {}):
            if data[k] not in spec["choices"]:
                return {k: f"Must be one of {spec['choices']}"}
    # cross-field logic example:
    if "min_age" in (data or {}) and "max_age" in (data or {}):
        if data["min_age"] > data["max_age"]:
            return {"min_age": "min_age cannot be greater than max_age"}
    return None
