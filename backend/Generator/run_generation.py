#!/usr/bin/env python3
"""
Wrapper script for the Data Generation step.

Runs all scripts in Section 1 (Data Generation) in the correct order:
  1. generate_names.py   — Generates name data across 8 writing systems
  2. generate_rooms.py   — Generates room definitions

Output files produced:
  - Generator/all_names.json
  - Generator/rooms.json
  - Generator/rooms.txt

Usage:
  python Generator/run_generation.py
  python Generator/run_generation.py --verbose
"""

import argparse
import os
import subprocess
import sys

# Script directory for resolving relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Generation scripts in execution order
GENERATION_SCRIPTS = [
    ("generate_names.py", "Name data generation"),
    ("generate_rooms.py", "Room definition generation"),
]


def run_script(script_name: str, label: str, verbose: bool = False) -> bool:
    """Run a single generator script and return success status."""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    print(f"[*] Running {label}... ({script_name})")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=SCRIPT_DIR,
            capture_output=not verbose,
            text=True,
        )
        if result.returncode == 0:
            print(f"[+] {label} completed successfully.")
            return True
        else:
            print(f"[-] {label} failed with exit code {result.returncode}.")
            if not verbose and (result.stdout or result.stderr):
                print(f"    Output: {result.stderr or result.stdout}")
            return False
    except FileNotFoundError:
        print(f"[-] Script not found: {script_path}")
        return False
    except Exception as e:
        print(f"[-] Error running {label}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run all Data Generation scripts (Section 1).",
        epilog="Generates all_names.json, rooms.json, and rooms.txt.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full script output (stdout and stderr)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  ConciergeOS — Data Generation Wrapper")
    print("=" * 60)
    print()

    success_count = 0
    total = len(GENERATION_SCRIPTS)

    for script_name, label in GENERATION_SCRIPTS:
        if run_script(script_name, label, verbose=args.verbose):
            success_count += 1
        else:
            print(f"\n[!] Stopping: '{label}' failed.")
            sys.exit(1)

    print()
    print("=" * 60)
    print(f"  Generation complete: {success_count}/{total} scripts succeeded.")
    print("=" * 60)


if __name__ == "__main__":
    main()