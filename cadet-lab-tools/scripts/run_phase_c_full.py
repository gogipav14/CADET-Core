#!/usr/bin/env python3
"""Master script to orchestrate complete Phase C operationalization workflow.

This script executes all steps of Phase C in sequence:
1. Production work-precision sweeps (4 cases × 16 points)
2. Spatial convergence checks (with iterative refinement for sharp_front)
3. Tolerance recommendations generation
4. Full-state stress suite baseline

Total runtime: ~1-2 hours
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_command(cmd, description, env=None):
    """Run a subprocess command and handle errors."""
    print(f"\n{'='*80}")
    print(f"{description}")
    print(f"{'='*80}")
    print(f"Command: {' '.join(str(c) for c in cmd)}\n")

    result = subprocess.run(cmd, env=env)

    if result.returncode != 0:
        print(f"\n❌ ERROR: {description} failed with return code {result.returncode}")
        sys.exit(1)

    print(f"\n✓ {description} completed successfully")


def main():
    parser = argparse.ArgumentParser(
        description="Run complete Phase C operationalization workflow"
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
        default=Path("./artifacts"),
        help="Base output directory (default: ./artifacts)",
    )
    parser.add_argument(
        "--skip-sweeps",
        action="store_true",
        help="Skip work-precision sweeps (use existing artifacts)",
    )
    parser.add_argument(
        "--skip-spatial",
        action="store_true",
        help="Skip spatial convergence checks (use existing artifacts)",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip stress suite baseline",
    )

    args = parser.parse_args()

    scripts_dir = Path(__file__).parent
    validation_dir = scripts_dir.parent / "cadet_lab" / "validation"

    start_time = datetime.now()

    print(f"\n{'#'*80}")
    print(f"# Phase C Operationalization - Master Workflow")
    print(f"# Started: {start_time.isoformat()}")
    print(f"{'#'*80}")

    # Step 1: Production work-precision sweeps
    if not args.skip_sweeps:
        run_command(
            [
                sys.executable,
                scripts_dir / "run_production_sweeps.py",
                "--cadet-cli", args.cadet_cli,
                "--output-dir", args.output_dir,
            ],
            "Step 1: Production Work-Precision Sweeps (4 cases × 16 points)",
        )
    else:
        print(f"\n⏭️  Skipping Step 1 (--skip-sweeps)")

    # Step 2: Spatial convergence checks
    if not args.skip_spatial:
        run_command(
            [
                sys.executable,
                scripts_dir / "run_spatial_convergence.py",
                "--cadet-cli", args.cadet_cli,
                "--output-dir", args.output_dir,
            ],
            "Step 2: Spatial Convergence Checks (with iterative refinement)",
        )
    else:
        print(f"\n⏭️  Skipping Step 2 (--skip-spatial)")

    # Step 3: Tolerance recommendations
    run_command(
        [
            sys.executable,
            validation_dir / "recommend_settings.py",
            "--artifacts-dir", args.output_dir,
            "--output", args.output_dir / "phase_c_recommended_settings.json",
        ],
        "Step 3: Generate Tolerance Recommendations",
    )

    # Step 4: Full-state stress suite baseline
    if not args.skip_baseline:
        run_command(
            [
                sys.executable,
                scripts_dir / "run_stress_suite_baseline.py",
                "--cadet-cli", args.cadet_cli,
                "--output-dir", args.output_dir / "stress_suite_baseline",
                "--output-file", args.output_dir / "stress_suite_results_full_state.json",
            ],
            "Step 4: Full-State Stress Suite Baseline",
        )
    else:
        print(f"\n⏭️  Skipping Step 4 (--skip-baseline)")

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    print(f"\n{'#'*80}")
    print(f"# Phase C Operationalization - Complete!")
    print(f"# Finished: {end_time.isoformat()}")
    print(f"# Duration: {duration}")
    print(f"{'#'*80}")

    print(f"\nArtifacts generated:")
    print(f"  - Work-precision sweeps: {args.output_dir}/<case>/work_precision_full_state.json")
    print(f"  - Spatial convergence: {args.output_dir}/<case>/spatial_convergence.json")
    print(f"  - Recommended settings: {args.output_dir}/phase_c_recommended_settings.json")
    print(f"  - Stress suite baseline: {args.output_dir}/stress_suite_results_full_state.json")

    print(f"\nNext steps:")
    print(f"  1. Review recommendations: cat {args.output_dir}/phase_c_recommended_settings.json | jq")
    print(f"  2. Check Phase D decision in recommendations JSON")
    print(f"  3. Apply recommended tolerances to production workflows")
    print(f"  4. Consult PHASE_C_IMPLEMENTATION_GUIDE.md for detailed interpretation")


if __name__ == "__main__":
    main()
