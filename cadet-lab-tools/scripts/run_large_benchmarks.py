#!/usr/bin/env python3
"""Run Phase D-1 large benchmarks to stress linear solver.

This script runs enlarged benchmark cases designed to take seconds (not milliseconds)
and expose linear solver bottlenecks where preconditioning could provide significant speedup.
"""

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Any

from cadet_lab.stress_suite.large_cases import get_large_benchmark_suite
from cadet_lab.telemetry.read_hdf5 import read_solution
import subprocess


def run_single_benchmark(
    case_name: str,
    case_generator,
    case_kwargs: Dict[str, Any],
    cadet_cli_path: Path,
    artifacts_dir: Path,
) -> Dict[str, Any]:
    """Run a single large benchmark case and collect metrics.

    Args:
        case_name: Name of the case (e.g., "large_sharp_front_spatial").
        case_generator: Function to generate the case HDF5 file.
        case_kwargs: Keyword arguments for the case generator.
        cadet_cli_path: Path to cadet-cli executable.
        artifacts_dir: Directory to store artifacts.

    Returns:
        Dictionary with benchmark results including metrics and linear solver stats.
    """
    print(f"\n{'='*60}")
    print(f"Running benchmark: {case_name}")
    print(f"{'='*60}")

    # Create case-specific artifacts directory
    case_dir = artifacts_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    # Generate input file
    input_path = case_dir / "input.h5"
    output_path = case_dir / "output.h5"

    print(f"Generating input: {input_path}")
    print(f"Configuration: {case_kwargs}")

    case_generator(
        output_path=input_path,
        cadet_path=cadet_cli_path,
        **case_kwargs,
    )

    # Run CADET simulation
    print(f"Running simulation...")
    start_time = time.time()

    try:
        result = subprocess.run(
            [str(cadet_cli_path), str(input_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        wall_time = time.time() - start_time

        if result.returncode != 0:
            print(f"CADET failed with return code {result.returncode}")
            print(f"STDERR: {result.stderr}")
            return {
                "case_name": case_name,
                "success": False,
                "error": result.stderr,
                "wall_time": wall_time,
            }

        print(f"Simulation completed in {wall_time:.2f} seconds")

    except subprocess.TimeoutExpired:
        print(f"Simulation timed out after 600 seconds")
        return {
            "case_name": case_name,
            "success": False,
            "error": "Timeout after 600 seconds",
        }

    # Read solver statistics from output
    print(f"Reading solver statistics from output...")
    solution_data = read_solution(output_path)
    solver_stats = solution_data.solver_stats

    if solver_stats is None:
        print(f"Warning: No solver statistics found in output")
        solver_stats = {}

    # Extract KPIs directly from solver_stats
    num_steps = solver_stats.get("NUM_STEPS", 0)
    num_rhs_evals = solver_stats.get("NUM_RHS_EVALS", 0)
    num_linsol_setups = solver_stats.get("NUM_LINSOL_SETUPS", 0)
    num_err_test_fails = solver_stats.get("NUM_ERR_TEST_FAILS", 0)
    num_nonlin_conv_fails = solver_stats.get("NUM_NONLIN_CONV_FAILS", 0)
    num_nonlin_iters = solver_stats.get("NUM_NONLIN_ITERS", 0)
    num_lin_iters = solver_stats.get("NUM_LIN_ITERS", 0)
    num_gmres_restarts = solver_stats.get("NUM_GMRES_RESTARTS", 0)

    # Prepare result dictionary
    result_dict = {
        "case_name": case_name,
        "success": True,
        "configuration": case_kwargs,
        "wall_time": wall_time,
        "solver_stats": solver_stats,
        "kpis": {
            "num_steps": num_steps,
            "num_rhs_evals": num_rhs_evals,
            "num_linsol_setups": num_linsol_setups,
            "num_err_test_fails": num_err_test_fails,
            "num_nonlin_conv_fails": num_nonlin_conv_fails,
            "num_nonlin_iters": num_nonlin_iters,
            "num_lin_iters": num_lin_iters,
            "num_gmres_restarts": num_gmres_restarts,
            "wall_time": wall_time,
        },
    }

    # Calculate derived metrics
    if num_steps and num_steps > 0:
        result_dict["derived_metrics"] = {
            "wall_time_per_step": wall_time / num_steps,
            "lin_iters_per_step": num_lin_iters / num_steps if num_lin_iters else 0,
            "nonlin_iters_per_step": num_nonlin_iters / num_steps if num_nonlin_iters else 0,
            "rhs_evals_per_step": num_rhs_evals / num_steps if num_rhs_evals else 0,
        }

        # Analyze bottleneck
        lin_iters_per_step = result_dict["derived_metrics"]["lin_iters_per_step"]
        if lin_iters_per_step > 80:
            bottleneck = "STRONG preconditioning payoff expected"
        elif lin_iters_per_step > 50:
            bottleneck = "MODERATE preconditioning payoff expected"
        elif lin_iters_per_step > 20:
            bottleneck = "WEAK preconditioning payoff expected"
        else:
            bottleneck = "Linear solver not bottleneck"

        result_dict["bottleneck_assessment"] = bottleneck

        print(f"\nResults Summary:")
        print(f"  Wall time: {wall_time:.2f} seconds")
        print(f"  NUM_STEPS: {num_steps}")
        print(f"  NUM_LIN_ITERS: {num_lin_iters}")
        print(f"  Lin iters per step: {lin_iters_per_step:.1f}")
        print(f"  Bottleneck assessment: {bottleneck}")

    return result_dict


def main():
    """Run all large benchmarks and save results."""
    # Get benchmark suite to extract available case names
    benchmark_suite = get_large_benchmark_suite()
    available_cases = [name for name, _, _ in benchmark_suite]

    parser = argparse.ArgumentParser(
        description="Run Phase D-1 large benchmarks"
    )
    parser.add_argument(
        "--cadet-cli",
        type=Path,
        default=Path("/home/gogip/github_repos/CADET-Core/build/src/cadet-cli/cadet-cli"),
        help="Path to cadet-cli executable",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("./artifacts/phase_d_large_benchmarks"),
        help="Directory to store benchmark artifacts",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=available_cases + ["all"],
        default=["all"],
        help="Which cases to run (default: all)",
    )

    args = parser.parse_args()

    # Filter cases if specified
    if "all" not in args.cases:
        benchmark_suite = [
            (name, gen, kwargs) for name, gen, kwargs in benchmark_suite
            if name in args.cases
        ]

    print(f"Running {len(benchmark_suite)} benchmark cases")
    print(f"CADET CLI: {args.cadet_cli}")
    print(f"Artifacts: {args.artifacts_dir}")

    # Run all benchmarks
    results = []
    for case_name, case_generator, default_kwargs in benchmark_suite:
        result = run_single_benchmark(
            case_name=case_name,
            case_generator=case_generator,
            case_kwargs=default_kwargs,
            cadet_cli_path=args.cadet_cli,
            artifacts_dir=args.artifacts_dir,
        )
        results.append(result)

    # Save consolidated results
    output_file = args.artifacts_dir / "baseline_results.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(
            {
                "metadata": {
                    "phase": "D-1",
                    "description": "Large benchmark baseline results",
                    "cadet_cli": str(args.cadet_cli),
                },
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"\n{'='*60}")
    print(f"All benchmarks complete!")
    print(f"Results saved to: {output_file}")
    print(f"{'='*60}\n")

    # Summary table
    print("Summary:")
    print(f"{'Case':<35} {'Wall Time':>12} {'Lin Iters':>12} {'Iters/Step':>12}")
    print("-" * 72)
    for result in results:
        if result["success"] and "derived_metrics" in result:
            print(f"{result['case_name']:<35} "
                  f"{result['wall_time']:>11.2f}s "
                  f"{result['kpis']['num_lin_iters']:>12} "
                  f"{result['derived_metrics']['lin_iters_per_step']:>12.1f}")
        else:
            print(f"{result['case_name']:<35} FAILED")


if __name__ == "__main__":
    main()
