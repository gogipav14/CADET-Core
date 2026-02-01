#!/usr/bin/env python3
"""Run spatial convergence checks for all 4 stress cases.

This script verifies spatial discretization adequacy via refinement study.
Sharp_front uses iterative resolution finder, other cases use single 2× refinement check.
"""

import argparse
from pathlib import Path
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cadet_lab.stress_suite.cases import (
    case_first_step_fail,
    case_sharp_front,
    case_discontinuous_section,
    case_stiff_binding,
)
from cadet_lab.validation.spatial_convergence import run_spatial_convergence_check


def run_iterative_spatial_refinement(
    case_generator,
    case_kwargs,
    cadet_cli_path,
    output_dir,
    threshold,
    max_refinement_levels=3,
    require_trend_decrease=True,
):
    """Run iterative spatial refinement until convergence or max levels reached.

    Implements resolution finder mode for sharp_front:
    - Start with baseline (NELEM=8)
    - Refine by 2×: compare refined vs baseline
    - Check: scaled_rms_delta <= threshold AND delta(n+1) < delta(n)
    - If not met: refine again (16→32)
    - Continue until both conditions met OR max_levels reached

    Args:
        case_generator: Function that generates config.
        case_kwargs: Keyword arguments for case_generator.
        cadet_cli_path: Path to cadet-cli executable.
        output_dir: Directory where outputs will be stored.
        threshold: Scaled RMS threshold for convergence.
        max_refinement_levels: Maximum number of refinement iterations.
        require_trend_decrease: Whether to require delta(n+1) < delta(n).

    Returns:
        dict with convergence result and history.
    """
    from cadet_lab.validation.spatial_convergence import run_spatial_convergence_check

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    case_name = case_kwargs.get("_case_name", "unknown")

    convergence_history = []
    convergence_achieved = False
    refinement_level = 0
    prev_delta = None

    for level in range(max_refinement_levels):
        refinement_level = level + 1
        refinement_factor = 2 ** refinement_level

        print(f"\n  Refinement level {refinement_level}: factor={refinement_factor}×")

        # Run spatial convergence check
        level_output_dir = output_dir / f"level_{refinement_level}"
        result = run_spatial_convergence_check(
            case_generator=case_generator,
            case_kwargs=case_kwargs,
            cadet_cli_path=cadet_cli_path,
            output_dir=level_output_dir,
            spatial_refinement_factor=refinement_factor,
            threshold=threshold,
        )

        current_delta = result.scaled_rms_delta

        convergence_history.append({
            "level": refinement_level,
            "refinement_factor": refinement_factor,
            "baseline_resolution": result.baseline_resolution,
            "refined_resolution": result.refined_resolution,
            "linf_delta": result.linf_delta,
            "scaled_rms_delta": current_delta,
            "threshold_met": current_delta <= threshold,
        })

        print(f"    Scaled RMS delta: {current_delta:.6e}")
        print(f"    Threshold: {threshold:.6e}")
        print(f"    Threshold met: {current_delta <= threshold}")

        # Check convergence conditions
        threshold_met = current_delta <= threshold

        if require_trend_decrease and prev_delta is not None:
            trend_decreasing = current_delta < prev_delta
            print(f"    Trend decreasing: {trend_decreasing} (prev={prev_delta:.6e}, current={current_delta:.6e})")
        else:
            trend_decreasing = True

        # Converged if both conditions met
        if threshold_met and trend_decreasing:
            convergence_achieved = True
            print(f"  ✓ Convergence achieved at refinement level {refinement_level}")
            break

        if level == max_refinement_levels - 1:
            print(f"  ✗ Max refinement levels reached without convergence")

        prev_delta = current_delta

    # Build final result
    final_result = {
        "case_name": case_name,
        "convergence_achieved": convergence_achieved,
        "refinement_levels": refinement_level,
        "threshold": threshold,
        "require_trend_decrease": require_trend_decrease,
        "max_refinement_levels": max_refinement_levels,
        "convergence_history": convergence_history,
        "final_linf_delta": convergence_history[-1]["linf_delta"],
        "final_scaled_rms_delta": convergence_history[-1]["scaled_rms_delta"],
        "baseline_resolution": convergence_history[0]["baseline_resolution"],
        "recommended_resolution": convergence_history[-1]["refined_resolution"],
    }

    return final_result


def main():
    parser = argparse.ArgumentParser(
        description="Run spatial convergence checks for Phase C"
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

    args = parser.parse_args()

    # Case configurations
    case_configs = {
        "first_step_fail": {
            "generator": case_first_step_fail,
            "kwargs": {"init_step_size": 1.0, "_case_name": "first_step_fail"},
            "threshold": 1e-2,
            "mode": "single",  # Single 2× refinement check
        },
        "sharp_front": {
            "generator": case_sharp_front,
            "kwargs": {"peclet": 1000.0, "n_col": 8, "_case_name": "sharp_front"},
            "threshold": 1e-3,
            "mode": "iterative",  # Iterative resolution finder
        },
        "discontinuous_section": {
            "generator": case_discontinuous_section,
            "kwargs": {"pulse_duration": 1.0, "_case_name": "discontinuous_section"},
            "threshold": 1e-2,
            "mode": "single",
        },
        "stiff_binding": {
            "generator": case_stiff_binding,
            "kwargs": {"binding_ka": 1e4, "binding_kd": 1e2, "_case_name": "stiff_binding"},
            "threshold": 1e-2,
            "mode": "single",
        },
    }

    for case_name in args.cases:
        print(f"\n{'='*80}")
        print(f"Running spatial convergence check for {case_name}")
        print(f"{'='*80}")

        config = case_configs[case_name]
        case_output_dir = args.output_dir / case_name
        case_output_dir.mkdir(parents=True, exist_ok=True)

        if config["mode"] == "iterative":
            # Iterative resolution finder (sharp_front)
            print(f"\nMode: Iterative resolution finder")
            print(f"Threshold: {config['threshold']:.6e}")
            print(f"Max refinement levels: 3")

            result = run_iterative_spatial_refinement(
                case_generator=config["generator"],
                case_kwargs=config["kwargs"],
                cadet_cli_path=args.cadet_cli,
                output_dir=case_output_dir / "spatial_convergence",
                threshold=config["threshold"],
                max_refinement_levels=3,
                require_trend_decrease=True,
            )
        else:
            # Single 2× refinement check
            print(f"\nMode: Single 2× refinement check")
            print(f"Threshold: {config['threshold']:.6e}")

            spatial_result = run_spatial_convergence_check(
                case_generator=config["generator"],
                case_kwargs=config["kwargs"],
                cadet_cli_path=args.cadet_cli,
                output_dir=case_output_dir / "spatial_convergence",
                spatial_refinement_factor=2,
                threshold=config["threshold"],
            )

            # Convert to dict format
            result = {
                "case_name": spatial_result.case_name,
                "convergence_achieved": spatial_result.convergence_achieved,
                "refinement_levels": 1,
                "threshold": spatial_result.threshold,
                "baseline_resolution": spatial_result.baseline_resolution,
                "recommended_resolution": spatial_result.refined_resolution,
                "final_linf_delta": spatial_result.linf_delta,
                "final_scaled_rms_delta": spatial_result.scaled_rms_delta,
            }

        # Save artifact
        artifact_path = case_output_dir / "spatial_convergence.json"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        with open(artifact_path, "w") as f:
            json.dump(result, f, indent=2)

        print(f"\nArtifact saved: {artifact_path}")

        # Summary
        print(f"\nSummary for {case_name}:")
        print(f"  Convergence achieved: {result['convergence_achieved']}")
        print(f"  Refinement levels: {result['refinement_levels']}")
        print(f"  Final scaled RMS delta: {result['final_scaled_rms_delta']:.6e}")
        print(f"  Threshold: {result['threshold']:.6e}")


if __name__ == "__main__":
    main()
