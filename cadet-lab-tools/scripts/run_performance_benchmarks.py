#!/usr/bin/env python3
"""Phase D Performance Benchmarking: Scaled Problem Runner

Executes stress cases at varying spatial resolutions to reveal solver bottlenecks.
Targets 5-45 second runtimes to make optimization ROI measurable.

Usage:
    python run_performance_benchmarks.py --case sharp_front --nelem 64 --par_nelem 8
    python run_performance_benchmarks.py --scaling-study  # Run all tiers
"""

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import h5py

# Add cadet_lab to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cadet_lab.harness.run_case import run_case
from cadet_lab.stress_suite.cases import (
    case_sharp_front,
    case_stiff_binding,
    case_first_step_fail,
    case_discontinuous_section,
)
from cadet_lab.telemetry.kpis import compute_kpis


# Case generators
CASE_GENERATORS = {
    "sharp_front": case_sharp_front,
    "stiff_binding": case_stiff_binding,
    "first_step_fail": case_first_step_fail,
    "discontinuous_section": case_discontinuous_section,
}


def run_scaled_benchmark(
    case_name: str,
    nelem: int,
    par_nelem: int,
    cadet_cli_path: Path,
    output_dir: Path,
    recommended_settings: Optional[Dict] = None,
) -> Dict:
    """Run a stress case at specified spatial resolution with Phase C recommended tolerances.

    Args:
        case_name: Name of stress case (sharp_front, stiff_binding, etc.)
        nelem: Number of column elements
        par_nelem: Number of particle elements
        cadet_cli_path: Path to cadet-cli executable
        output_dir: Directory for output files
        recommended_settings: Optional dict with abstol, reltol from Phase C

    Returns:
        Dictionary with performance metrics
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load recommended settings from Phase C if not provided
    if recommended_settings is None:
        settings_path = Path(__file__).parent.parent.parent / "artifacts" / "phase_c_recommended_settings.json"
        if settings_path.exists():
            with open(settings_path) as f:
                all_settings = json.load(f)
                recommended_settings = all_settings.get(case_name, {})

    # Build case configuration
    case_generator = CASE_GENERATORS[case_name]
    case_kwargs = {}

    # Only sharp_front supports n_col parameter directly
    if case_name == "sharp_front":
        case_kwargs["n_col"] = nelem

    # Apply Phase C recommended tolerances if available
    if recommended_settings:
        if "abstol" in recommended_settings:
            case_kwargs["abstol"] = recommended_settings["abstol"]
        if "reltol" in recommended_settings:
            case_kwargs["reltol"] = recommended_settings["reltol"]

    # Generate input file
    config_path = output_dir / f"{case_name}_n{nelem}_p{par_nelem}_config.h5"
    case_generator(output_path=config_path, **case_kwargs)

    # Modify NELEM and PAR_NELEM in HDF5 file
    with h5py.File(config_path, "r+") as f:
        # Modify column discretization (NELEM)
        if case_name != "sharp_front":  # sharp_front already sets this
            disc = f["input/model/unit_001/discretization"]
            if "NELEM" in disc:
                del disc["NELEM"]
            disc.create_dataset("NELEM", data=nelem)

        # Modify particle discretization (PAR_NELEM) - all cases need this
        par_disc = f["input/model/unit_001/particle_type_000/discretization"]
        if "PAR_NELEM" in par_disc:
            del par_disc["PAR_NELEM"]
        par_disc.create_dataset("PAR_NELEM", data=par_nelem)

    # Run simulation
    result = run_case(
        input_file=config_path,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
    )

    # Compute KPIs
    kpis = compute_kpis(result)

    # Build performance metrics dictionary
    metrics = {
        "case_name": case_name,
        "spatial_resolution": {
            "nelem_col": nelem,
            "nelem_par": par_nelem,
            "state_dimension_estimate": nelem * par_nelem * 4,  # Approx: nelem * par_nelem * poly_degree
        },
        "tolerances": {
            "abstol": case_kwargs.get("abstol", "default"),
            "reltol": case_kwargs.get("reltol", "default"),
        },
        "performance": {
            "wall_time": kpis.wall_time,
            "num_steps": kpis.num_steps,
            "num_nonlin_iters": kpis.num_steps * 2 if kpis.num_steps else None,  # Estimate: ~2 Newton iters/step
            "num_err_test_fails": kpis.num_err_test_fails,
            "num_conv_fails": kpis.num_conv_fails,
        },
        "derived_metrics": {
            "wall_time_per_step": kpis.wall_time / kpis.num_steps if kpis.num_steps else None,
            "reject_ratio": kpis.reject_ratio,
        },
        "success": kpis.success,
        "failure_reason": kpis.failure_reason,
        "timestamp": datetime.now().isoformat(),
    }

    # Save individual result
    result_path = output_dir / f"{case_name}_n{nelem}_p{par_nelem}_metrics.json"
    with open(result_path, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Benchmark: {case_name} (NELEM={nelem}, PAR_NELEM={par_nelem})")
    print(f"{'='*60}")
    print(f"Success: {kpis.success}")
    if kpis.success:
        print(f"Wall time: {kpis.wall_time:.3f} s")
        print(f"Steps: {kpis.num_steps}")
        print(f"Wall time/step: {metrics['derived_metrics']['wall_time_per_step']:.6f} s")
        print(f"Err test fails: {kpis.num_err_test_fails}")
        print(f"Conv fails: {kpis.num_conv_fails}")
    else:
        print(f"Failure: {kpis.failure_reason}")
    print(f"Result saved: {result_path}")

    return metrics


def run_scaling_study(
    case_name: str,
    cadet_cli_path: Path,
    output_dir: Path,
) -> Dict[str, List[Dict]]:
    """Run 3-tier scaling study: baseline → medium → large.

    Args:
        case_name: Name of stress case
        cadet_cli_path: Path to cadet-cli executable
        output_dir: Directory for output files

    Returns:
        Dictionary with results per tier
    """
    output_dir = Path(output_dir) / f"scaling_study_{case_name}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define tiers
    tiers = {
        "baseline": {"nelem": 8, "par_nelem": 1},   # Phase C baseline
        "medium": {"nelem": 32, "par_nelem": 4},    # Intermediate
        "large": {"nelem": 64, "par_nelem": 8},     # Target: 15-45s runtime
    }

    results = {}
    for tier_name, tier_params in tiers.items():
        print(f"\n{'#'*60}")
        print(f"Running {tier_name.upper()} tier...")
        print(f"{'#'*60}")

        tier_output_dir = output_dir / tier_name
        metrics = run_scaled_benchmark(
            case_name=case_name,
            nelem=tier_params["nelem"],
            par_nelem=tier_params["par_nelem"],
            cadet_cli_path=cadet_cli_path,
            output_dir=tier_output_dir,
        )
        results[tier_name] = metrics

    # Save consolidated results
    study_path = output_dir / "scaling_study_results.json"
    with open(study_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Print scaling summary
    print(f"\n{'='*60}")
    print(f"SCALING STUDY SUMMARY: {case_name}")
    print(f"{'='*60}")
    print(f"{'Tier':<12} {'NELEM':<8} {'Wall Time':<12} {'Steps':<8} {'Time/Step':<12}")
    print(f"{'-'*60}")
    for tier_name, metrics in results.items():
        if metrics["success"]:
            nelem = metrics["spatial_resolution"]["nelem_col"]
            wall_time = metrics["performance"]["wall_time"]
            steps = metrics["performance"]["num_steps"]
            time_per_step = metrics["derived_metrics"]["wall_time_per_step"]
            print(f"{tier_name:<12} {nelem:<8} {wall_time:<12.3f} {steps:<8} {time_per_step:<12.6f}")
        else:
            print(f"{tier_name:<12} FAILED")

    print(f"\nFull results saved: {study_path}")
    return results


def analyze_bottleneck(scaling_results: Dict[str, Dict]) -> Dict:
    """Analyze scaling behavior to identify bottlenecks.

    Args:
        scaling_results: Results from run_scaling_study()

    Returns:
        Bottleneck analysis dictionary
    """
    baseline = scaling_results.get("baseline", {})
    medium = scaling_results.get("medium", {})
    large = scaling_results.get("large", {})

    if not (baseline.get("success") and large.get("success")):
        return {
            "bottleneck": "unknown",
            "reason": "Insufficient data (failed runs)",
        }

    # Extract key metrics
    baseline_time = baseline["performance"]["wall_time"]
    large_time = large["performance"]["wall_time"]
    baseline_steps = baseline["performance"]["num_steps"]
    large_steps = large["performance"]["num_steps"]

    baseline_nelem = baseline["spatial_resolution"]["nelem_col"]
    large_nelem = large["spatial_resolution"]["nelem_col"]

    # Expected scaling: state dimension grows as (NELEM * PAR_NELEM)^2 for Jacobian
    # So wall time should scale roughly quadratically if linear solver dominates
    spatial_scaling_factor = (large_nelem / baseline_nelem) ** 2
    observed_time_scaling = large_time / baseline_time
    step_scaling = large_steps / baseline_steps

    analysis = {
        "baseline_runtime": baseline_time,
        "large_runtime": large_time,
        "spatial_scaling_factor": spatial_scaling_factor,
        "observed_time_scaling": observed_time_scaling,
        "step_scaling": step_scaling,
        "time_per_step_baseline": baseline["derived_metrics"]["wall_time_per_step"],
        "time_per_step_large": large["derived_metrics"]["wall_time_per_step"],
    }

    # Determine bottleneck
    if observed_time_scaling > (spatial_scaling_factor * 1.5):
        # Time scaling worse than quadratic → linear solver likely bottleneck
        analysis["bottleneck"] = "linear_solver"
        analysis["recommendation"] = (
            "Preconditioning likely to help. "
            f"Observed scaling ({observed_time_scaling:.1f}×) >> spatial scaling ({spatial_scaling_factor:.1f}×). "
            "Implement physics-aware preconditioner (Schur complement, FFT diffusion)."
        )
    elif step_scaling > 2.0:
        # Steps grew significantly → time-stepping policy issue
        analysis["bottleneck"] = "step_count"
        analysis["recommendation"] = (
            f"Step count increased {step_scaling:.1f}× with spatial refinement. "
            "Investigate adaptive stepping policy or tighten tolerances."
        )
    elif observed_time_scaling < spatial_scaling_factor * 0.5:
        # Time scaling better than expected → overhead dominates
        analysis["bottleneck"] = "overhead"
        analysis["recommendation"] = (
            "Runtime dominated by overhead (I/O, setup). "
            "Solver optimization unlikely to help at this problem scale."
        )
    else:
        # Expected quadratic scaling
        analysis["bottleneck"] = "expected_scaling"
        analysis["recommendation"] = (
            f"Scaling is near-quadratic ({observed_time_scaling:.1f}× vs {spatial_scaling_factor:.1f}× expected). "
            "Solver is performing reasonably. Preconditioning may still provide modest gains."
        )

    return analysis


def main():
    parser = argparse.ArgumentParser(description="Phase D Performance Benchmarking")
    parser.add_argument(
        "--case",
        choices=list(CASE_GENERATORS.keys()),
        default="sharp_front",
        help="Stress case to run (default: sharp_front)"
    )
    parser.add_argument(
        "--nelem",
        type=int,
        help="Number of column elements (if not running scaling study)"
    )
    parser.add_argument(
        "--par_nelem",
        type=int,
        help="Number of particle elements (if not running scaling study)"
    )
    parser.add_argument(
        "--scaling-study",
        action="store_true",
        help="Run full 3-tier scaling study (baseline, medium, large)"
    )
    parser.add_argument(
        "--cadet-cli",
        type=Path,
        default=Path(__file__).parent.parent.parent / "build" / "src" / "cadet-cli" / "cadet-cli",
        help="Path to cadet-cli executable"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent.parent / "artifacts" / "phase_d_performance",
        help="Output directory for results"
    )

    args = parser.parse_args()

    # Verify cadet-cli exists
    if not args.cadet_cli.exists():
        print(f"Error: cadet-cli not found at {args.cadet_cli}", file=sys.stderr)
        print("Build CADET first or specify path with --cadet-cli", file=sys.stderr)
        sys.exit(1)

    # Run benchmark(s)
    if args.scaling_study:
        results = run_scaling_study(
            case_name=args.case,
            cadet_cli_path=args.cadet_cli,
            output_dir=args.output,
        )

        # Analyze bottleneck
        analysis = analyze_bottleneck(results)
        analysis_path = args.output / f"scaling_study_{args.case}" / "bottleneck_analysis.json"
        with open(analysis_path, 'w') as f:
            json.dump(analysis, f, indent=2)

        print(f"\n{'='*60}")
        print(f"BOTTLENECK ANALYSIS")
        print(f"{'='*60}")
        print(f"Bottleneck: {analysis['bottleneck']}")
        print(f"Recommendation: {analysis['recommendation']}")
        print(f"\nAnalysis saved: {analysis_path}")

    else:
        if args.nelem is None or args.par_nelem is None:
            print("Error: Must specify --nelem and --par_nelem, or use --scaling-study", file=sys.stderr)
            sys.exit(1)

        run_scaled_benchmark(
            case_name=args.case,
            nelem=args.nelem,
            par_nelem=args.par_nelem,
            cadet_cli_path=args.cadet_cli,
            output_dir=args.output,
        )


if __name__ == "__main__":
    main()
