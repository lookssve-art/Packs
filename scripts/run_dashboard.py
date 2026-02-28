#!/usr/bin/env python3
"""Launch the Streamlit live dashboard.

Usage: python scripts/run_dashboard.py
   or: streamlit run src/dashboard/app.py
"""

import os
import subprocess
import sys


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_path = os.path.join(project_root, "src", "dashboard", "app.py")

    print("Starting Packs EV Tracker Dashboard...")
    print(f"App: {app_path}")
    print("Open http://localhost:8501 in your browser.\n")

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", app_path,
         "--server.headless", "true",
         "--server.port", "8501"],
        cwd=project_root,
    )


if __name__ == "__main__":
    main()
