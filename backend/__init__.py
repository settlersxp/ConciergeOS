"""ConciergeOS Backend Package.

This package provides the FastAPI application for ConciergeOS hotel management system.
"""

from pathlib import Path

# Ensure the backend directory is on the Python path so that
# `from app.xxx` imports work from any entry point script.
_package_dir = Path(__file__).resolve().parent
if str(_package_dir) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_package_dir))