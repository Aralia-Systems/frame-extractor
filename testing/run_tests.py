#!/usr/bin/env python
"""
Test runner script for frame-extractor.

Usage:
    python testing/run_tests.py [options]
    
Examples:
    python testing/run_tests.py                    # Run all tests
    python testing/run_tests.py --coverage          # Run with coverage report
    python testing/run_tests.py --verbose           # Verbose output
    python testing/run_tests.py --unit              # Unit tests only
    python testing/run_tests.py --integration       # Integration tests only
"""

import sys
import subprocess
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run frame-extractor test suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate coverage report'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--unit',
        action='store_true',
        help='Run unit tests only (skip integration)'
    )
    parser.add_argument(
        '--integration',
        action='store_true',
        help='Run integration tests only'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Include debug logging'
    )
    parser.add_argument(
        '--no-capture',
        action='store_true',
        help='Show print statements and logging'
    )
    parser.add_argument(
        '--markers',
        type=str,
        help='Run tests matching marker expression'
    )
    parser.add_argument(
        '--keyword',
        type=str,
        help='Run tests matching keyword expression'
    )
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = ['pytest', 'testing/', '--tb=short']
    
    if args.verbose:
        cmd.append('-vv')
    else:
        cmd.append('-v')
    
    if args.coverage:
        cmd.extend(['--cov=frame_extractor', '--cov-report=html', '--cov-report=term'])
    
    if args.unit:
        cmd.extend(['-m', 'not integration'])
    elif args.integration:
        cmd.extend(['-m', 'integration'])
    
    if args.markers:
        cmd.extend(['-m', args.markers])
    
    if args.keyword:
        cmd.extend(['-k', args.keyword])
    
    if args.debug:
        cmd.append('--log-cli-level=DEBUG')
    
    if args.no_capture:
        cmd.append('-s')
    
    # Run pytest
    print(f"Running: {' '.join(cmd)}")
    print("-" * 80)
    
    result = subprocess.run(cmd)
    
    # Print summary
    print("-" * 80)
    if args.coverage:
        print("\nCoverage report generated in: htmlcov/index.html")
    
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
