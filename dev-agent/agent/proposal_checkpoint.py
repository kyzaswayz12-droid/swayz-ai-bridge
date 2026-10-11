"""Local fail-closed proposal checkpoint, never stores API keys or raw reviews."""
import hashlib
import json
import os
from pathlib import Path

def save_proposal(directory: Path, proposal: str) -> dict:
    if not isinstance(proposal,str) or not proposal.strip() or len(proposal)>32768:
        raise ValueError("Invalid proposal")
    directory=Path(directory)
    if directory.is_symlink():
        raise PermissionError("Symlink directory refused")
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(directory,0o700)
    digest=hashlib.sha256(proposal.encode("utf-8")).hexdigest()
    path=directory/(digest+".json")
    data={"proposal_sha256":digest,"proposal":proposal,"review_state":"pending"}
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
    try:
        fd=os.open(path,flags,0o600)
    except FileExistsError:
        return {"proposal_sha256":digest,"saved":False,"path":str(path)}
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(data,f)
    return {"proposal_sha256":digest,"saved":True,"path":str(path)}
