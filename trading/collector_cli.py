"""Read-only command-line one-shot Kraken quote collector.

Run manually or from a supervised scheduler after staging approval.
No exchange credentials or order endpoints.
"""
import argparse
import asyncio
import json
import os
import sys
import httpx
from .collector_runner import collect_with_state
from .collector_state import CollectorStateStore
from .quote_archive import QuoteArchive

async def run(pair: str, state_path: str, archive_path: str) -> dict:
    state=CollectorStateStore(state_path)
    archive=QuoteArchive(archive_path)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            return await collect_with_state(client,archive,state,pair=pair)
    finally:
        archive.close()
        state.close()

def main():
    parser=argparse.ArgumentParser(description="Collect one public Kraken quote")
    parser.add_argument("--pair",choices=["XBTUSD","ETHUSD"],required=True)
    parser.add_argument("--state-db",required=True)
    parser.add_argument("--archive-db",required=True)
    args=parser.parse_args()
    try:
        result=asyncio.run(run(args.pair,args.state_db,args.archive_db))
    except Exception as exc:
        print(json.dumps({"ok":False,"error_type":type(exc).__name__}),file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"ok":True,**result}))

if __name__=="__main__":
    main()
