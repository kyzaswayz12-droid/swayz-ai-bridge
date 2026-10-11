import json
import unittest
from agent.http_transport import provider_transport

class Response:
    def __init__(self,data): self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n):
        assert n==1024*1024+1
        return self.data

class Opener:
    def __init__(self,response=b'{"ok":true}'):
        self.response=response
        self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        return Response(self.response)

class TransportTests(unittest.TestCase):
    def test_openai_endpoint_and_auth(self):
        opener=Opener()
        body=provider_transport("openai",{"model":"test"},"dummy",opener=opener)
        self.assertEqual(body,b'{"ok":true}')
        request,timeout=opener.calls[0]
        self.assertEqual(request.full_url,"https://api.openai.com/v1/responses")
        self.assertEqual(request.get_header("Authorization"),"Bearer dummy")
        self.assertEqual(timeout,20)

    def test_anthropic_endpoint(self):
        opener=Opener()
        provider_transport("anthropic",{"model":"test"},"dummy",opener=opener)
        req,_=opener.calls[0]
        self.assertEqual(req.full_url,"https://api.anthropic.com/v1/messages")
        self.assertEqual(req.get_header("X-api-key"),"dummy")

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            provider_transport("arbitrary",{},"dummy",opener=Opener())

    def test_response_limit(self):
        with self.assertRaises(ValueError):
            provider_transport("openai",{},"dummy",opener=Opener(b"x"*(1024*1024+1)))

    def test_header_injection_rejected(self):
        with self.assertRaises(ValueError):
            provider_transport("openai",{},"bad\nkey",opener=Opener())
