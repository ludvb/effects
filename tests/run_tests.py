#!/usr/bin/env python3
"""Test runner for the effects package with coverage and filtering options."""

import argparse
import sys
from pathlib import Path

# Add src to path for development testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest  # type: ignore[import-not-found]


def main():
    """Run tests with various options."""
    parser = argparse.ArgumentParser(description="Run effects tests")
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Run only unit tests",
    )
    parser.add_argument(
        "--functional",
        action="store_true",
        help="Run only functional tests",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run with coverage report",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--failfast",
        "-x",
        action="store_true",
        help="Stop on first failure",
    )
    parser.add_argument(
        "--parallel",
        "-n",
        type=int,
        metavar="NUM",
        help="Run tests in parallel with NUM workers",
    )
    parser.add_argument(
        "--module",
        "-m",
        help="Run tests for specific module (e.g., 'effects', 'util')",
    )
    parser.add_argument(
        "--markers",
        "-k",
        help="Run tests matching given expression",
    )

    args = parser.parse_args()

    # Build pytest arguments
    pytest_args = []

    # Determine which tests to run
    if args.unit:
        pytest_args.append("tests/unit")
    elif args.functional:
        pytest_args.append("tests/functional")
    elif args.module:
        pytest_args.append(f"tests/unit/test_{args.module}.py")
    else:
        pytest_args.append("tests/")

    # Add coverage if requested
    if args.coverage:
        pytest_args.extend(
            [
                "--cov=effects",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov",
            ]
        )

    # Add verbosity
    if args.verbose:
        pytest_args.append("-vv")
    else:
        pytest_args.append("-q")

    # Add failfast
    if args.failfast:
        pytest_args.append("-x")

    # Add parallel execution
    if args.parallel:
        pytest_args.extend(["-n", str(args.parallel)])

    # Add marker expression
    if args.markers:
        pytest_args.extend(["-k", args.markers])

    # Show test summary
    pytest_args.append("-ra")

    print(f"Running: pytest {' '.join(pytest_args)}")
    sys.exit(pytest.main(pytest_args))


if __name__ == "__main__":
    main()
