"""Standalone paper dashboard application; no broker credentials."""
import os
from .dashboard_api import create_dashboard_app

app=create_dashboard_app(os.environ.get("PAPER_JOURNAL_PATH","/data/paper.sqlite3"))
