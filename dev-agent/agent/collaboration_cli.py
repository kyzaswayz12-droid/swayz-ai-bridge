"""Owner-invoked collaboration CLI. Defaults to offline, zero-spend mode.

This command never executes generated code, writes GitHub changes or trades.
The --execute flag is deliberately required for real paid provider calls.
"""
import argparse
import json
from pathlib import Path
from .live_collaboration import run_once

DEFAULT_TASK=("Review the Swayz trading project's risk-control architecture "
              "at a conceptual level. Propose automated tests only. "
              "Do not assume access to source files, change code, deploy, "
              "or execute trades.")

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--execute",action="store_true")
    p.add_argument("--secrets",type=Path,required=True)
    p.add_argument("--budget-db",type=Path,required=True)
    p.add_argument("--control-db",type=Path,required=True)
    p.add_argument("--openai-model",default="gpt-5-mini")
    p.add_argument("--claude-model",default="claude-haiku-4-5-20251001")
    args=p.parse_args(argv)
    result=run_once(DEFAULT_TASK,secrets=args.secrets,budget_db=args.budget_db,
                    control_db=args.control_db,openai_model=args.openai_model,
                    claude_model=args.claude_model,execute=args.execute)
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
