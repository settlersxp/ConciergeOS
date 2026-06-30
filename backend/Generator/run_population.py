#!/usr/bin/env python3
"""
Wrapper script for the Database Population step.

Runs all scripts in Section 2 (Database Population) in the correct order:
  1. populate_rooms.py          — Inserts room definitions into the database
  2. populate_reservations.py   — Creates guests and reservations data
  3. setup_performance_guests.py (optional) — Creates 13 dedicated test guests

Input files consumed:
  - Generator/rooms.json
  - Generator/all_names.json

Database tables modified:
  - Rooms
  - Guests
  - Reservations

Usage:
  python Generator/run_population.py
  python Generator/run_population.py --skip-performance
  python Generator/run_population.py --verbose
"""

import argparse
import os
import subprocess
import sys

# Script directory for resolving relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Core population scripts (always run)
POPULATION_SCRIPTS = [
    ("populate_rooms.py", "Room population"),
    ("populate_reservations.py", "Guest and reservation population"),
    ("seed_prompts.py", "Prompt version seeding"),
]

# Optional scripts (skip-able)
OPTIONAL_SCRIPTS = [
    ("setup_performance_guests.py", "Performance test guest setup"),
]


def run_script(script_name: str, label: str, verbose: bool = False) -> bool:
    """Run a single population script and return success status."""
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
        description="Run all Database Population scripts (Section 2).",
        epilog=(
            "Populates Rooms, Guests, and Reservations tables. "
            "By default also runs setup_performance_guests.py. "
            "Use --skip-performance to skip the optional performance guest setup."
        ),
    )
    parser.add_argument(
        "--skip-performance",
        action="store_true",
        help="Skip the optional setup_performance_guests.py script",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full script output (stdout and stderr)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  ConciergeOS — Database Population Wrapper")
    print("=" * 60)
    print()

    # Build the full script list
    scripts_to_run = list(POPULATION_SCRIPTS)
    if not args.skip_performance:
        scripts_to_run.append(OPTIONAL_SCRIPTS[0])

    success_count = 0
    total = len(scripts_to_run)

    for script_name, label in scripts_to_run:
        if run_script(script_name, label, verbose=args.verbose):
            success_count += 1
        else:
            print(f"\n[!] Stopping: '{label}' failed.")
            sys.exit(1)

    print()
    print("=" * 60)
    print(f"  Population complete: {success_count}/{total} scripts succeeded.")
    if args.skip_performance:
        print("  (setup_performance_guests.py was skipped)")
    print("=" * 60)


if __name__ == "__main__":
    main()