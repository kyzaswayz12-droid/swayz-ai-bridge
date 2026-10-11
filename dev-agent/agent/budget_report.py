"""Read-only local budget report; never contacts providers or settles costs."""
import argparse
import json
from datetime import datetime,timezone
from .budget import BudgetStore

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",required=True)
    parser.add_argument("--day",default=datetime.now(timezone.utc).date().isoformat())
    args=parser.parse_args(argv)
    ledger=BudgetStore(args.db)
    try:
        print(json.dumps(ledger.summary(args.day),sort_keys=True))
    finally:
        ledger.close()

if __name__=="__main__":
    main()
