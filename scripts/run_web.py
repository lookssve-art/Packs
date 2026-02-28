#!/usr/bin/env python3
"""Start the web application with embedded collector.

Usage: python scripts/run_web.py
Opens http://localhost:8000
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from config.settings import Settings


def main():
    settings = Settings()
    print(f"Starting Packs EV Tracker Web App...")
    print(f"  API + Dashboard: http://{settings.web_host}:{settings.web_port}")
    print(f"  API Docs: http://{settings.web_host}:{settings.web_port}/docs")
    print(f"  Collector polling every {settings.poll_interval_seconds}s")
    print()

    uvicorn.run(
        "src.api.main:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
