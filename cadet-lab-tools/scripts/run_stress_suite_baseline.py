#!/usr/bin/env python3
"""Run full-state stress suite baseline for Phase C.

This script generates comprehensive full-state stress suite results with all 4 cases
using baseline settings, serving as a benchmark for measuring improvements.
"""

import argparse
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cadet_lab.stress_suite.runner import run_stress_suite


def main():
    parser = argparse.ArgumentParser(
        description="Run full-state stress suite baseline"
    )
    parser.add_argument(
        "--cadet-cli",
        type=Path,
        required=True,
        help="Path to cadet-cli executable",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./artifacts/stress_suite_baseline"),
        help="Output directory (default: ./artifacts/stress_suite_baseline)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("./artifacts/stress_suite_results_full_state.json"),
        help="Output JSON file (default: ./artifacts/stress_suite_results_full_state.json)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("Running Full-State Stress Suite Baseline for Phase C")
    print("=" * 80)

    # Run stress suite with full-state mode enabled
    results = run_stress_suite(
        cadet_cli_path=args.cadet_cli,
        output_dir=args.output_dir,
        full_state_mode=True,
    )

    # Save results
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    results.save(args.output_file)

    print(f"\n{'=' * 80}")
    print("Stress Suite Baseline Complete")
    print(f"{'=' * 80}")
    print(f"\nResults saved to: {args.output_file}")

    # Summary
    print(f"\nSummary:")
    print(f"  Total cases: {results.total_cases}")
    print(f"  Passed: {results.passed}")
    print(f"  Failed: {results.failed}")
    print(f"  Failure rate: {results.failure_rate:.2%}")

    if results.median_wall_time:
        print(f"  Median wall time: {results.median_wall_time:.3f} s")
    if results.median_err_test_fails is not None:
        print(f"  Median err_test_fails: {results.median_err_test_fails:.0f}")
    if results.median_conv_fails is not None:
        print(f"  Median conv_fails: {results.median_conv_fails:.0f}")

    # Per-case breakdown
    print(f"\nPer-Case Results:")
    for case_name, case_data in results.case_results.items():
        status = "PASS" if case_data.get("success") else "FAIL"
        steps = case_data.get("num_steps", "N/A")
        err_fails = case_data.get("num_err_test_fails", "N/A")
        conv_fails = case_data.get("num_conv_fails", "N/A")
        print(f"  {case_name:25s} [{status}]  steps={steps:>4}  err_fails={err_fails:>2}  conv_fails={conv_fails:>2}")

    # Full-state metrics (if available)
    if results.full_state_metrics:
        print(f"\nFull-State Metrics Available:")
        for case_name in results.full_state_metrics.keys():
            print(f"  - {case_name}")


if __name__ == "__main__":
    main()
