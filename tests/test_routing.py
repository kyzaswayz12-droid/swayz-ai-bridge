import hashlib
import hmac
from app.core import parse_command, Command, valid_signature

def test_commands():
    assert parse_command("  CHATGPT: hello")==Command("openai","hello")
    assert parse_command("claude: hi")==Command("anthropic","hi")
    assert parse_command("@claude hi") is None
    assert parse_command("claude:").problem=="empty"
    assert parse_command("claude: "+"x"*4001).problem=="too_long"

def test_signature():
    body=b'{"hello":true}'
    ts="1000"
    sig="v0="+hmac.new(b"secret",b"v0:1000:"+body,hashlib.sha256).hexdigest()
    assert valid_signature(body,ts,sig,"secret",now=1001)
    assert not valid_signature(body+b"x",ts,sig,"secret",now=1001)
    assert not valid_signature(body,ts,sig,"secret",now=1400)
