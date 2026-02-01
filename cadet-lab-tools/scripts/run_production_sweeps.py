#!/usr/bin/env python3
"""Run production work-precision sweeps for all 4 stress cases.

This script generates complete 4×4 tolerance sweeps (16 points each) against
time-mode references for Phase C operationalization.
"""

import argparse
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cadet_lab.stress_suite.cases import (
    case_first_step_fail,
    case_sharp_front,
    case_discontinuous_section,
    case_stiff_binding,
)
from cadet_lab.validation.reference_protocol import run_reference
from cadet_lab.validation.tolerance_sweep import run_tolerance_sweep


def main():
    parser = argparse.ArgumentParser(
        description="Run production work-precision sweeps for Phase C"
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
        "--cases",
        nargs="+",
        choices=["first_step_fail", "sharp_front", "discontinuous_section", "stiff_binding"],
        default=["first_step_fail", "sharp_front", "discontinuous_section", "stiff_binding"],
        help="Cases to run (default: all)",
    )
    parser.add_argument(
        "--tolerance-factor",
        type=float,
        default=100.0,
        help="Tolerance tightening factor for time-mode reference (default: 100)",
    )

    args = parser.parse_args()

    # Case configurations
    case_configs = {
        "first_step_fail": {
            "generator": case_first_step_fail,
            "kwargs": {"init_step_size": 1.0, "_case_name": "first_step_fail"},
        },
        "sharp_front": {
            "generator": case_sharp_front,
            "kwargs": {"peclet": 1000.0, "n_col": 8, "_case_name": "sharp_front"},
        },
        "discontinuous_section": {
            "generator": case_discontinuous_section,
            "kwargs": {"pulse_duration": 1.0, "_case_name": "discontinuous_section"},
        },
        "stiff_binding": {
            "generator": case_stiff_binding,
            "kwargs": {"binding_ka": 1e4, "binding_kd": 1e2, "_case_name": "stiff_binding"},
        },
    }

    # Default tolerance grids (4×4 = 16 points)
    abstol_grid = [1e-9, 3e-9, 1e-8, 3e-8]
    reltol_grid = [1e-6, 3e-6, 1e-5, 3e-5]

    for case_name in args.cases:
        print(f"\n{'='*80}")
        print(f"Running production sweep for {case_name}")
        print(f"{'='*80}")

        config = case_configs[case_name]
        case_output_dir = args.output_dir / case_name
        case_output_dir.mkdir(parents=True, exist_ok=True)

        cache_dir = case_output_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Generate time-mode reference
        print(f"\nStep 1: Generating time-mode reference (tol_factor={args.tolerance_factor})...")
        reference_output, reference_config = run_reference(
            case_generator=config["generator"],
            case_kwargs=config["kwargs"],
            cadet_cli_path=args.cadet_cli,
            output_dir=case_output_dir / "reference",
            mode="time",
            tolerance_factor=args.tolerance_factor,
            cache_dir=cache_dir,
        )
        print(f"Reference generated: {reference_output}")

        # Step 2: Run 4×4 tolerance sweep
        print(f"\nStep 2: Running 4×4 tolerance sweep ({len(abstol_grid)}×{len(reltol_grid)} = {len(abstol_grid)*len(reltol_grid)} points)...")
        result = run_tolerance_sweep(
            case_generator=config["generator"],
            case_kwargs=config["kwargs"],
            cadet_cli_path=args.cadet_cli,
            output_dir=case_output_dir / "sweep",
            reference_output=reference_output,
            reference_config=reference_config,
            abstol_grid=abstol_grid,
            reltol_grid=reltol_grid,
        )

        # Step 3: Save artifact
        artifact_path = case_output_dir / "work_precision_full_state.json"
        result.save(artifact_path)
        print(f"\nArtifact saved: {artifact_path}")

        # Summary
        successful_points = sum(1 for p in result.sweep_points if p.get("success", False))
        print(f"\nSummary for {case_name}:")
        print(f"  Total points: {len(result.sweep_points)}")
        print(f"  Successful: {successful_points}")
        print(f"  Failed: {len(result.sweep_points) - successful_points}")

        if successful_points > 0:
            avg_steps = sum(
                p.get("num_steps", 0) for p in result.sweep_points if p.get("success", False)
            ) / successful_points
            print(f"  Average steps (successful): {avg_steps:.1f}")


if __name__ == "__main__":
    main()
