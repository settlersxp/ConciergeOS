#!/usr/bin/env python3
"""
Wrapper script for the Error Setup step.

Runs all scripts in Section 3 (Error Setup) in the correct order:
  1. setup_errors.py          — Injects controlled errors into reservations
  2. shift_reservations.py    — Optional: shifts all reservation dates

Output files produced:
  - Generator/erroneous_reservations.json

Database tables modified:
  - Reservations (error injection only)

Usage:
  python Generator/run_errors.py
  python Generator/run_errors.py --skip-shift
  python Generator/run_errors.py --verbose
"""

import argparse
import os
import subprocess
import sys

# Script directory for resolving relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Core error setup scripts (always run)
ERROR_SCRIPTS = [
    ("setup_errors.py", "Controlled error injection"),
]

# Optional scripts (skip-able)
OPTIONAL_ERROR_SCRIPTS = [
    ("shift_reservations.py", "Reservation date shifting"),
]


def run_script(script_name: str, label: str, verbose: bool = False) -> bool:
    """Run a single error setup script and return success status."""
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
        description="Run all Error Setup scripts (Section 3).",
        epilog=(
            "Injects controlled errors into existing reservations for "
            "testing error detection features. By default also runs "
            "shift_reservations.py. Use --skip-shift to skip date shifting."
        ),
    )
    parser.add_argument(
        "--skip-shift",
        action="store_true",
        help="Skip the optional shift_reservations.py script",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full script output (stdout and stderr)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  ConciergeOS — Error Setup Wrapper")
    print("=" * 60)
    print()

    # Build the full script list
    scripts_to_run = list(ERROR_SCRIPTS)
    if not args.skip_shift:
        scripts_to_run.append(OPTIONAL_ERROR_SCRIPTS[0])

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
    print(f"  Error setup complete: {success_count}/{total} scripts succeeded.")
    if args.skip_shift:
        print("  (shift_reservations.py was skipped)")
    print("=" * 60)


if __name__ == "__main__":
    main()