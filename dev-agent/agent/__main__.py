"""Read-only agent inspection commands. No provider calls or GitHub writes."""
import argparse
import json
from pathlib import Path
from .core import Policy, TaskStore
from .budget import BudgetStore, BudgetLimits

def main(argv=None):
    parser=argparse.ArgumentParser(description="Swayz development agent staging CLI")
    parser.add_argument("--data-dir",default=str(Path.home()/"swayz-agent"/"data"))
    command=parser.add_subparsers(dest="command",required=True)
    command.add_parser("status")
    command.add_parser("preflight")
    args=parser.parse_args(argv)
    directory=Path(args.data_dir).expanduser().resolve()
    if not directory.is_dir() or directory.is_symlink():
        parser.error("Data directory must exist and not be a symlink")
    if args.command=="preflight":
        policy=Policy("kyzaswayz12-droid/swayz-ai-bridge")
        print(json.dumps({
            "repository":policy.repository,
            "model_calls_enabled":policy.enable_model_calls,
            "git_writes_enabled":policy.enable_git_writes,
            "deployment_enabled":policy.enable_deployment,
            "live_trading_enabled":policy.enable_live_trading,
            "python_package":"dev-agent/agent"
        },indent=2))
        return
    db=directory/"tasks.sqlite3"
    if not db.is_file():
        print(json.dumps({"state":"not_initialized","tasks":{}},indent=2))
        return
    store=TaskStore(str(db))
    try:
        print(json.dumps({"state":"offline","tasks":store.status()},indent=2))
    finally:
        store.close()

if __name__=="__main__":
    main()
