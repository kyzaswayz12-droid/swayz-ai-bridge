"""Bounded HTTPS provider transport; no requests on import.

Only fixed vendor origins are allowed. No arbitrary model-supplied URLs.
"""
import json
import urllib.request
import urllib.error

ENDPOINTS = {
    "openai": "https://api.openai.com/v1/responses",
    "anthropic": "https://api.anthropic.com/v1/messages",
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Provider redirects forbidden")

def provider_transport(provider: str, payload: dict, api_key: str, *,
                       opener=None, timeout=20) -> bytes:
    if provider not in ENDPOINTS:
        raise ValueError("Unknown provider")
    if not isinstance(api_key,str) or not api_key.strip() or "\r" in api_key or "\n" in api_key:
        raise ValueError("Invalid credential")
    if type(timeout) not in (int,float) or not 1 <= timeout <= 30:
        raise ValueError("Invalid provider timeout")
    data=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    if len(data)>131072:
        raise ValueError("Provider request too large")
    headers={"Content-Type":"application/json","Accept":"application/json"}
    if provider=="openai":
        headers["Authorization"]="Bearer "+api_key
    else:
        headers["x-api-key"]=api_key
        headers["anthropic-version"]="2023-06-01"
    req=urllib.request.Request(ENDPOINTS[provider],data=data,headers=headers,method="POST")
    opener=opener if opener is not None else urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req,timeout=timeout) as response:
            # Read at most 1 MiB plus a sentinel byte. Never echo response errors,
            # which might contain provider or user-controlled sensitive data.
            body=response.read(1024*1024+1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Provider HTTP status {exc.code}") from None
    if not isinstance(body,bytes) or len(body)>1024*1024:
        raise ValueError("Provider response too large")
    return body
