import hashlib
import hmac
import json
from app.github_review import verify_github_signature,select_review_candidate

REPO="kyzaswayz12-droid/swayz-ai-bridge"
SHA="a"*40

def payload(action="synchronize",repository=REPO,head_repo=REPO):
    return json.dumps({
        "action":action,"number":3,
        "repository":{"full_name":repository},
        "pull_request":{"number":3,
            "head":{"sha":SHA,"repo":{"full_name":head_repo}},
            "base":{"ref":"feature/swayz-trading-foundation"}}
    }).encode()

def choose(body):
    return select_review_candidate(body,"pull_request",allowed_repository=REPO,
        allowed_base=frozenset({"main","feature/swayz-trading-foundation"}))

def test_signature_verified_against_raw_body():
    body=payload()
    sig="sha256="+hmac.new(b"test-secret",body,hashlib.sha256).hexdigest()
    assert verify_github_signature(body,sig,"test-secret")
    assert not verify_github_signature(body+b" ",sig,"test-secret")
    assert not verify_github_signature(body,sig,"other-secret")
    assert not verify_github_signature(body,"sha256=bad","test-secret")
    assert not verify_github_signature(body,sig,"")

def test_valid_review_candidate():
    result=choose(payload())
    assert result.repository==REPO
    assert result.pull_number==3
    assert result.head_sha==SHA

def test_reject_other_repos_and_forks():
    assert choose(payload(repository="someone/other")) is None
    assert choose(payload(head_repo="someone/fork")) is None

def test_reject_unrelated_event_and_action():
    assert select_review_candidate(payload(),"push",allowed_repository=REPO,
        allowed_base=frozenset({"main"})) is None
    assert choose(payload(action="closed")) is None

def test_reject_bad_commit_sha():
    body=json.loads(payload())
    body["pull_request"]["head"]["sha"]="not-a-sha"
    assert choose(json.dumps(body).encode()) is None
