"""Tolerance recommendation engine for Phase C operationalization.

This module implements acceptance gates and selection algorithms to identify
optimal tolerance settings per case based on work-precision sweeps.
"""

from pathlib import Path
from typing import Union, Optional, List, Dict, Any
from datetime import datetime
import json


# Acceptance gate thresholds
SCALED_RMS_GLOBAL_MAX = 1.0  # Default (within tolerance-scaled error)
SCALED_RMS_GLOBAL_MAX_STRICT = 0.5  # Optional strict profile
MAX_ERR_TEST_FAILS = 10  # Stability constraint


def find_optimal_tolerances(
    sweep_points: List[Dict[str, Any]],
    scaled_rms_threshold: float = SCALED_RMS_GLOBAL_MAX,
    linf_threshold: Optional[float] = None,
    max_err_test_fails: int = MAX_ERR_TEST_FAILS,
) -> Optional[Dict[str, Any]]:
    """Select cheapest sweep point meeting acceptance gates.

    Args:
        sweep_points: List of tolerance sweep point dictionaries.
        scaled_rms_threshold: Maximum scaled RMS error allowed.
        linf_threshold: Optional maximum L-infinity error allowed.
        max_err_test_fails: Maximum error test failures allowed.

    Returns:
        Dictionary with optimal point, or None if all points fail gates.
    """
    # Filter points meeting gates
    valid_points = []

    for point in sweep_points:
        # Must be successful
        if not point.get("success", False):
            continue

        # Check scaled RMS gate
        scaled_rms = point.get("scaled_rms_error")
        if scaled_rms is None or scaled_rms > scaled_rms_threshold:
            continue

        # Check L-infinity gate (if specified)
        if linf_threshold is not None:
            linf_error = point.get("linf_error")
            if linf_error is None or linf_error > linf_threshold:
                continue

        # Check error test fail gate
        err_test_fails = point.get("num_err_test_fails", 0)
        if err_test_fails > max_err_test_fails:
            continue

        valid_points.append(point)

    if not valid_points:
        return None

    # Minimize num_steps (primary cost metric)
    optimal = min(valid_points, key=lambda p: p.get("num_steps", float("inf")))

    return optimal


def compute_phase_d_trigger_decision(
    case_results: Dict[str, Dict[str, Any]],
    step_threshold: int = 500,
) -> Dict[str, Any]:
    """Determine if Phase D (solver/preconditioning work) is warranted.

    Phase D Trigger Conditions (ANY of):
    1. Convergence pressure: num_conv_fails > 0
    2. Step budget pressure: min_steps_meeting_gates > step_threshold
    3. Spatial under-resolution dominates: spatial_converged and min_abstol_for_gates < 1e-9
    4. Stability cliffs: large metric jumps between neighboring tolerance points

    Args:
        case_results: Dictionary mapping case names to their results.
        step_threshold: Step count threshold for triggering Phase D.

    Returns:
        Dictionary with triggered flag, reasons, and notes.
    """
    triggered = False
    reasons = []

    # Check each case for trigger conditions
    for case_name, result in case_results.items():
        optimal = result.get("optimal_tolerances")

        if optimal is None:
            # No valid point found - strong Phase D signal
            triggered = True
            reasons.append(f"{case_name}: No tolerance point meeting gates")
            continue

        # Condition 1: Convergence failures
        num_conv_fails = optimal.get("num_conv_fails", 0)
        if num_conv_fails > 0:
            triggered = True
            reasons.append(
                f"{case_name}: Convergence failures detected ({num_conv_fails})"
            )

        # Condition 2: Step budget pressure
        num_steps = optimal.get("num_steps", 0)
        if num_steps > step_threshold:
            triggered = True
            reasons.append(
                f"{case_name}: High step count ({num_steps} > {step_threshold})"
            )

        # Condition 3: Very tight tolerances required
        abstol = optimal.get("abstol", 1e-6)
        if abstol < 1e-9:
            triggered = True
            reasons.append(
                f"{case_name}: Very tight abstol required ({abstol:.2e})"
            )

    # Summary
    if not triggered:
        notes = "No Phase D triggers detected. Step advisor successfully handles err_test_fails. No solver work warranted at this time."
    else:
        notes = f"Phase D triggered by {len(reasons)} condition(s). Solver/preconditioning work recommended."

    return {
        "triggered": triggered,
        "reasons": reasons,
        "notes": notes,
    }


def generate_recommendations(
    artifacts_dir: Union[str, Path],
    output_path: Union[str, Path],
    scaled_rms_threshold: float = SCALED_RMS_GLOBAL_MAX,
    step_threshold: int = 500,
) -> Dict[str, Any]:
    """Generate Phase C recommended settings from work-precision artifacts.

    Args:
        artifacts_dir: Directory containing work_precision_full_state.json per case.
        output_path: Where to save phase_c_recommended_settings.json.
        scaled_rms_threshold: Scaled RMS threshold for acceptance gates.
        step_threshold: Step count threshold for Phase D trigger.

    Returns:
        Dictionary with recommendations.
    """
    artifacts_dir = Path(artifacts_dir)
    output_path = Path(output_path)

    # Case names
    case_names = [
        "first_step_fail",
        "sharp_front",
        "discontinuous_section",
        "stiff_binding",
    ]

    # Load work-precision results
    case_results = {}

    for case_name in case_names:
        work_precision_file = (
            artifacts_dir / case_name / "work_precision_full_state.json"
        )

        if not work_precision_file.exists():
            print(f"Warning: {work_precision_file} not found, skipping {case_name}")
            continue

        with open(work_precision_file, "r") as f:
            data = json.load(f)

        sweep_points = data.get("sweep_points", [])

        # Find optimal tolerances
        optimal = find_optimal_tolerances(
            sweep_points=sweep_points,
            scaled_rms_threshold=scaled_rms_threshold,
        )

        case_results[case_name] = {
            "optimal_tolerances": optimal,
            "total_sweep_points": len(sweep_points),
            "successful_points": sum(1 for p in sweep_points if p.get("success", False)),
        }

    # Compute Phase D trigger decision
    phase_d_decision = compute_phase_d_trigger_decision(
        case_results=case_results,
        step_threshold=step_threshold,
    )

    # Build recommendations
    recommendations = {
        "metadata": {
            "gates": {
                "scaled_rms_global": scaled_rms_threshold,
                "max_err_test_fails": MAX_ERR_TEST_FAILS,
            },
            "timestamp": datetime.now().isoformat(),
        },
        "phase_d_decision": phase_d_decision,
    }

    # Add per-case recommendations
    for case_name, result in case_results.items():
        optimal = result["optimal_tolerances"]

        if optimal is None:
            recommendations[case_name] = {
                "status": "FAILED",
                "note": "No tolerance point meeting acceptance gates",
            }
        else:
            recommendations[case_name] = {
                "abstol": optimal.get("abstol"),
                "reltol": optimal.get("reltol"),
                "expected_steps": optimal.get("num_steps"),
                "accuracy": {
                    "scaled_rms_error": optimal.get("scaled_rms_error"),
                    "linf_error": optimal.get("linf_error"),
                },
                "solver_stats": {
                    "num_err_test_fails": optimal.get("num_err_test_fails"),
                    "num_conv_fails": optimal.get("num_conv_fails"),
                    "wall_time": optimal.get("wall_time"),
                },
            }

    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(recommendations, f, indent=2)

    print(f"Recommendations saved to: {output_path}")

    return recommendations


def print_recommendations_summary(recommendations: Dict[str, Any]) -> None:
    """Print human-readable summary of recommendations."""
    print("\n" + "=" * 80)
    print("PHASE C RECOMMENDED SETTINGS SUMMARY")
    print("=" * 80)

    # Phase D decision
    phase_d = recommendations.get("phase_d_decision", {})
    print(f"\nPhase D Decision: {'TRIGGERED' if phase_d.get('triggered') else 'NOT TRIGGERED'}")
    print(f"  {phase_d.get('notes', 'N/A')}")

    if phase_d.get("reasons"):
        print("\nReasons:")
        for reason in phase_d["reasons"]:
            print(f"  - {reason}")

    # Per-case settings
    print("\n" + "-" * 80)
    print("Recommended Settings per Case:")
    print("-" * 80)

    case_names = [
        "first_step_fail",
        "sharp_front",
        "discontinuous_section",
        "stiff_binding",
    ]

    for case_name in case_names:
        if case_name not in recommendations:
            continue

        case_rec = recommendations[case_name]

        print(f"\n{case_name}:")

        if case_rec.get("status") == "FAILED":
            print(f"  Status: FAILED")
            print(f"  Note: {case_rec.get('note')}")
        else:
            print(f"  ABSTOL: {case_rec.get('abstol'):.2e}")
            print(f"  RELTOL: {case_rec.get('reltol'):.2e}")
            print(f"  Expected steps: {case_rec.get('expected_steps')}")
            accuracy = case_rec.get("accuracy", {})
            print(f"  Scaled RMS error: {accuracy.get('scaled_rms_error', 0):.6e}")
            print(f"  L-inf error: {accuracy.get('linf_error', 0):.6e}")
            solver = case_rec.get("solver_stats", {})
            print(f"  Error test fails: {solver.get('num_err_test_fails', 0)}")
            print(f"  Convergence fails: {solver.get('num_conv_fails', 0)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Phase C tolerance recommendations"
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("./artifacts"),
        help="Directory containing work_precision_full_state.json per case",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./artifacts/phase_c_recommended_settings.json"),
        help="Output path for recommendations",
    )
    parser.add_argument(
        "--scaled-rms-threshold",
        type=float,
        default=SCALED_RMS_GLOBAL_MAX,
        help="Scaled RMS threshold for acceptance gates (default: 1.0)",
    )
    parser.add_argument(
        "--step-threshold",
        type=int,
        default=500,
        help="Step count threshold for Phase D trigger (default: 500)",
    )

    args = parser.parse_args()

    recommendations = generate_recommendations(
        artifacts_dir=args.artifacts_dir,
        output_path=args.output,
        scaled_rms_threshold=args.scaled_rms_threshold,
        step_threshold=args.step_threshold,
    )

    print_recommendations_summary(recommendations)
