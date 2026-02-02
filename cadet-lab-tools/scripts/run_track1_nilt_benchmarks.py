#!/usr/bin/env python3
"""Run Phase D Track 1: NILT vs CADET benchmarks.

Executes scaling studies for 6 linear problems across 4 spatial tiers,
measuring accuracy and speedup.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cadet_lab.benchmarks.problem_registry import get_problem
from cadet_lab.benchmarks.nilt_problem_suite import (
    get_all_linear_problems,
    get_transfer_function_for_problem,
)
from cadet_lab.benchmarks.nilt_comparison import (
    run_scaling_study,
    print_scaling_summary,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run Phase D Track 1: NILT vs CADET benchmarks"
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
        default=Path("./artifacts/acceleration_benchmarks/track1"),
        help="Base output directory (default: ./artifacts/acceleration_benchmarks/track1)",
    )
    parser.add_argument(
        "--problems",
        nargs="+",
        choices=get_all_linear_problems(),
        default=get_all_linear_problems(),
        help="Problems to run (default: all 6)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.5,
        help="NILT alpha parameter (CFL-informed, default: 0.5)",
    )
    parser.add_argument(
        "--nilt-n",
        type=int,
        default=256,
        help="NILT FFT size (default: 256)",
    )

    args = parser.parse_args()

    # NILT parameters
    nilt_params = {
        "alpha": args.alpha,
        "N": args.nilt_n,
        "t_final": 100.0,
    }

    print("=" * 80)
    print("PHASE D TRACK 1: NILT vs CADET Benchmarks")
    print("=" * 80)
    print(f"Date: {datetime.now().isoformat()}")
    print(f"CADET CLI: {args.cadet_cli}")
    print(f"Output dir: {args.output_dir}")
    print(f"Problems: {len(args.problems)}")
    print(f"NILT params: alpha={nilt_params['alpha']}, N={nilt_params['N']}")
    print("=" * 80)

    # Run scaling studies
    all_results = {}

    for problem_id in args.problems:
        print(f"\n\n{'#' * 80}")
        print(f"# Problem: {problem_id}")
        print(f"{'#' * 80}")

        # Get problem definition
        problem = get_problem(problem_id)

        # Get transfer function
        transfer_func = get_transfer_function_for_problem(problem_id)

        # Run scaling study
        problem_output_dir = args.output_dir / problem_id

        try:
            study = run_scaling_study(
                problem=problem,
                transfer_function=transfer_func,
                cadet_cli_path=args.cadet_cli,
                output_dir=problem_output_dir,
                nilt_params=nilt_params,
            )

            # Save results
            study.save(problem_output_dir / f"{problem_id}_scaling_study.json")

            # Print summary
            print_scaling_summary(study)

            all_results[problem_id] = study

        except Exception as e:
            print(f"\n❌ ERROR: {problem_id} failed: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Final summary
    print("\n\n" + "=" * 80)
    print("TRACK 1 COMPLETION SUMMARY")
    print("=" * 80)

    successful = len(all_results)
    total = len(args.problems)
    print(f"\nCompleted: {successful}/{total} problems")

    if successful > 0:
        print("\nProblems completed:")
        for problem_id in all_results.keys():
            print(f"  ✅ {problem_id}")

    failed = total - successful
    if failed > 0:
        print(f"\n⚠️  {failed} problem(s) failed")

    print(f"\nResults saved to: {args.output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
