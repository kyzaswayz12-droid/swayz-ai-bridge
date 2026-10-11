"""Provider HTTP adapters with injectable transports; no network calls on import.

Provider requests are disabled until a separate, owner-approved dispatcher
implements budget reservation, timeouts, retry policy and secret management.
"""
import json
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class ModelResponse:
    text: str
    input_tokens: int
    output_tokens: int

def _require_text(value, name):
    if not isinstance(value,str) or not value.strip() or len(value)>32768:
        raise ValueError(f"Invalid {name}")
    return value

def _parse_json(body: bytes):
    if len(body)>1024*1024:
        raise ValueError("Provider response too large")
    data=json.loads(body)
    if not isinstance(data,dict):
        raise ValueError("Malformed provider response")
    return data

def openai_response(body: bytes) -> ModelResponse:
    data=_parse_json(body)
    pieces=[]
    for item in data.get("output",[]):
        if not isinstance(item,dict):
            continue
        for content in item.get("content",[]):
            if isinstance(content,dict) and content.get("type")=="output_text":
                pieces.append(content.get("text",""))
    usage=data.get("usage",{})
    if not isinstance(usage,dict):
        raise ValueError("Invalid token usage")
    text=_require_text("".join(pieces),"OpenAI response")
    inp=usage.get("input_tokens")
    out=usage.get("output_tokens")
    if type(inp) is not int or type(out) is not int or inp<0 or out<0:
        raise ValueError("Invalid token usage")
    return ModelResponse(text,inp,out)

def anthropic_response(body: bytes) -> ModelResponse:
    data=_parse_json(body)
    pieces=[x.get("text","") for x in data.get("content",[])
            if isinstance(x,dict) and x.get("type")=="text"]
    usage=data.get("usage",{})
    if not isinstance(usage,dict):
        raise ValueError("Invalid token usage")
    text=_require_text("".join(pieces),"Claude response")
    inp=usage.get("input_tokens")
    out=usage.get("output_tokens")
    if type(inp) is not int or type(out) is not int or inp<0 or out<0:
        raise ValueError("Invalid token usage")
    return ModelResponse(text,inp,out)

def prepare_openai_request(model: str, instruction: str, task: str, *, max_output_tokens=1500):
    _require_text(model,"model")
    _require_text(instruction,"instruction")
    _require_text(task,"task")
    if type(max_output_tokens) is not int or not 1<=max_output_tokens<=4096:
        raise ValueError("Invalid output cap")
    return {"model":model,"instructions":instruction,"input":task,
            "max_output_tokens":max_output_tokens,"store":False}

def prepare_anthropic_request(model: str, instruction: str, task: str, *, max_tokens=1500, structured_review=False):
    _require_text(model,"model")
    _require_text(instruction,"instruction")
    _require_text(task,"task")
    if type(max_tokens) is not int or not 1<=max_tokens<=4096:
        raise ValueError("Invalid output cap")
    payload={"model":model,"system":instruction,
            "messages":[{"role":"user","content":task}],"max_tokens":max_tokens}
    if structured_review:
        payload["output_config"]={"format":{"type":"json_schema","schema":review_json_schema()}}
    return payload
