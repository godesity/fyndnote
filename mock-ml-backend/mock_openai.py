"""Mock OpenAI-compatible server for DSPy E2E tests.

POST /v1/chat/completions → canned completion.
Preferred source: the request's response_format.json_schema properties
(enum → first enum value, string → "positive", array → [], integer/number →
3, object → {"start":0,"end":5,"entity":"x"}).
Fallback (dspy's JSONAdapter may send only {"type":"json_object"}): parse the
output field list out of the system prompt — "`name` (type): desc" — and
synthesize values of the right shape; select-like descs of the form
"one of 'a', 'b'" resolve to the first option.
"""

import json
import re

from fastapi import FastAPI, Request

app = FastAPI(title="mock-openai")

_FIELD_RE = re.compile(r"`(\w+)`\s*\((\w+)\)([^)]*)")
_OPTION_RE = re.compile(r"'([^']+)'")


def value_for(prop: dict):
    if prop.get("enum"):
        return prop["enum"][0]
    t = prop.get("type")
    if t == "string":
        return "positive"
    if t == "array":
        return []
    if t in ("integer", "number"):
        return 3
    if t == "object":
        return {"start": 0, "end": 5, "entity": "x"}
    return "positive"


def value_from_prompt(type_: str, desc: str):
    if type_ == "int":
        return 3
    if type_ in ("list", "tuple", "set"):
        return []
    if type_ == "dict":
        return {"start": 0, "end": 5, "entity": "x"}
    # str-like: honor "one of 'a', 'b'" enumerations in the field description
    options = _OPTION_RE.findall(desc or "")
    return options[0] if options else "positive"


def schema_props(body: dict) -> dict:
    try:
        js = body.get("response_format", {}).get("json_schema", {}) or {}
    except AttributeError:
        return {}
    # dspy versions spell this "schema" or "schema_"
    schema = js.get("schema") or js.get("schema_") or {}
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    return props if isinstance(props, dict) else {}


def fields_from_prompt(body: dict) -> dict:
    for msg in body.get("messages", []):
        content = msg.get("content") or ""
        if "output fields" not in content:
            continue
        section = content.split("output fields are:", 1)[-1]
        section = section.split("All interactions", 1)[0]
        return {
            name: value_from_prompt(type_, rest)
            for name, type_, rest in _FIELD_RE.findall(section)
        }
    return {}


def content_from_request(body: dict) -> str:
    props = schema_props(body)
    if props:
        return json.dumps({name: value_for(prop) for name, prop in props.items()})
    return json.dumps(fields_from_prompt(body))


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "openai/mock")
    content = content_from_request(body)
    return {
        "id": "mock-1",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
