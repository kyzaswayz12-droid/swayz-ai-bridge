"""Inspect safe metadata from a captured OpenAI Responses API body.

Never prints generated content, credentials, or raw provider JSON.
"""
import json

def openai_metadata(raw: bytes) -> dict:
    if not isinstance(raw,bytes) or len(raw)>1024*1024:
        raise ValueError("Invalid response size")
    data=json.loads(raw)
    if not isinstance(data,dict):
        raise ValueError("Invalid response schema")
    usage=data.get("usage") or {}
    if not isinstance(usage,dict):
        usage={}
    details=usage.get("output_tokens_details") or {}
    if not isinstance(details,dict):
        details={}
    outputs=data.get("output") or []
    if not isinstance(outputs,list):
        outputs=[]
    return {
        "status":str(data.get("status","unknown"))[:40],
        "incomplete_reason":str((data.get("incomplete_details") or {}).get("reason","none"))[:80]
            if isinstance(data.get("incomplete_details") or {},dict) else "unknown",
        "input_tokens":usage.get("input_tokens") if type(usage.get("input_tokens")) is int else None,
        "output_tokens":usage.get("output_tokens") if type(usage.get("output_tokens")) is int else None,
        "reasoning_tokens":details.get("reasoning_tokens") if type(details.get("reasoning_tokens")) is int else None,
        "output_items":len(outputs),
        "output_text_present":any(
            isinstance(item,dict) and any(
                isinstance(part,dict) and part.get("type")=="output_text" and bool(part.get("text"))
                for part in item.get("content",[]) if isinstance(item.get("content",[]),list)
            ) for item in outputs
        )
    }
