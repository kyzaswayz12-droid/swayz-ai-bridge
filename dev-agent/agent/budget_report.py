"""Read-only local budget report; never contacts providers or settles costs."""
import argparse
import json
from datetime import datetime,timezone
from .budget import BudgetStore
from pathlib import Path
from decimal import Decimal

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",required=True)
    parser.add_argument("--day",default=datetime.now(timezone.utc).date().isoformat())
    args=parser.parse_args(argv)
    if not Path(args.db).is_file():
        parser.error("Budget ledger does not exist")
    ledger=BudgetStore(args.db)
    try:
        summary=ledger.summary(args.day)
        summary["currency"]="USD"
        summary["daily_limit_usd"]="5.00"
        summary["remaining_accounted_usd"]=str(max(Decimal("0"),Decimal("5.00")-Decimal(summary["accounted_usd"])))
        print(json.dumps(summary,sort_keys=True))
    finally:
        ledger.close()

if __name__=="__main__":
    main()
