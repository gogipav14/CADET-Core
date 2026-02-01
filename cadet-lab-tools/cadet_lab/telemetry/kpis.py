"""Compute KPIs from CADET simulation results.

This module provides functions to compute key performance indicators
from simulation runs, including failure analysis and profile metrics.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional, Tuple, Union, Any
import numpy as np

from cadet_lab.harness.run_case import RunResult
from cadet_lab.telemetry.read_hdf5 import SolutionData


@dataclass
class RunKPIs:
    """Key Performance Indicators for a CADET simulation run.

    Attributes:
        success: Whether the simulation completed successfully.
        wall_time: Wall clock time in seconds.
        failure_reason: Description of failure, or None on success.
        n_solution_times: Number of solution time points.
        outlet_shape: Shape of outlet concentration array.
        num_steps: Total number of time steps taken by integrator.
        num_rhs_evals: Total number of RHS evaluations.
        num_err_test_fails: Number of error test failures.
        num_conv_fails: Number of convergence failures.
        num_lin_iters: Total linear solver iterations (None if not available).
        num_gmres_restarts: Total GMRES restarts (None if not available).
        reject_ratio: Ratio of rejected steps to total steps.
        profile_norms: Dictionary of norm values for each outlet profile.
    """

    success: bool
    wall_time: float
    failure_reason: Optional[str]
    n_solution_times: int
    outlet_shape: Optional[Tuple[int, ...]]
    num_steps: Optional[int] = None
    num_rhs_evals: Optional[int] = None
    num_err_test_fails: Optional[int] = None
    num_conv_fails: Optional[int] = None
    num_lin_iters: Optional[int] = None  # Total linear solver iterations
    num_gmres_restarts: Optional[int] = None  # GMRES restarts
    reject_ratio: Optional[float] = None
    profile_norms: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        if d["outlet_shape"] is not None:
            d["outlet_shape"] = list(d["outlet_shape"])
        return d


def compute_kpis(
    run_result: RunResult,
    solution_data: Optional[SolutionData] = None,
) -> RunKPIs:
    """Compute KPIs from a run result and optional solution data.

    Args:
        run_result: Result from run_case().
        solution_data: Optional solution data from read_solution().
            If not provided and output file exists, will attempt to read it.

    Returns:
        RunKPIs with computed metrics.
    """
    # Try to read solution data if not provided
    if solution_data is None and run_result.output_file:
        try:
            from cadet_lab.telemetry.read_hdf5 import read_solution
            solution_data = read_solution(run_result.output_file)
        except Exception:
            solution_data = None

    # Determine failure reason (may refine from run_result)
    failure_reason = run_result.failure_reason
    if failure_reason is None and run_result.return_code != 0:
        failure_reason = determine_failure_reason(
            return_code=run_result.return_code,
            stdout=run_result.stdout,
            stderr=run_result.stderr,
            solver_stats=run_result.solver_stats,
        )

    # Extract solver stats
    solver_stats = run_result.solver_stats or {}
    if solution_data and solution_data.solver_stats:
        solver_stats.update(solution_data.solver_stats)

    num_steps = solver_stats.get("NUM_STEPS")
    num_rhs_evals = solver_stats.get("NUM_RHS_EVALS")
    num_err_test_fails = solver_stats.get("NUM_ERR_TEST_FAILS")
    # Handle both old and new naming conventions (avoid `or` since 0 is falsy)
    num_conv_fails = solver_stats.get("NUM_NONLIN_CONV_FAILS")
    if num_conv_fails is None:
        num_conv_fails = solver_stats.get("NUM_CONV_FAILS")
    num_lin_iters = solver_stats.get("NUM_LIN_ITERS")
    num_gmres_restarts = solver_stats.get("NUM_GMRES_RESTARTS")

    # Compute reject ratio
    reject_ratio = None
    if num_steps and num_steps > 0 and num_err_test_fails is not None:
        reject_ratio = num_err_test_fails / num_steps

    # Compute profile norms
    profile_norms = {}
    if solution_data:
        for unit_id, profile in solution_data.outlet_profiles.items():
            profile_norms[unit_id] = compute_profile_norms(profile)

    return RunKPIs(
        success=run_result.success,
        wall_time=run_result.wall_time,
        failure_reason=failure_reason,
        n_solution_times=run_result.n_times,
        outlet_shape=run_result.outlet_shape,
        num_steps=num_steps,
        num_rhs_evals=num_rhs_evals,
        num_err_test_fails=num_err_test_fails,
        num_conv_fails=num_conv_fails,
        num_lin_iters=num_lin_iters,
        num_gmres_restarts=num_gmres_restarts,
        reject_ratio=reject_ratio,
        profile_norms=profile_norms,
    )


def determine_failure_reason(
    return_code: int,
    stdout: str,
    stderr: str,
    solver_stats: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Determine failure reason from available information.

    Checks return code, log output, and solver statistics to identify
    the most likely cause of failure.

    Args:
        return_code: Exit code from cadet-cli.
        stdout: Standard output from cadet-cli.
        stderr: Standard error from cadet-cli.
        solver_stats: Optional solver statistics dictionary.

    Returns:
        String describing failure reason, or None if successful.
    """
    if return_code == 0:
        return None

    combined = (stdout or "") + (stderr or "")

    # Check log output for IDAS failure patterns
    if "IDA_CONV_FAIL" in combined:
        return "CONVERGENCE_FAIL"

    if "Newton" in combined and ("fail" in combined.lower() or "converge" in combined.lower()):
        return "CONVERGENCE_FAIL"

    if "IDA_ERR_FAIL" in combined or "error test" in combined.lower():
        return "ERROR_TEST_FAIL"

    if "maximum" in combined.lower() and "step" in combined.lower():
        return "MAX_STEPS_EXCEEDED"

    if "IDA_MAX_STEPS" in combined:
        return "MAX_STEPS_EXCEEDED"

    # Check solver stats for high failure counts
    if solver_stats:
        err_fails = solver_stats.get("NUM_ERR_TEST_FAILS", 0)
        conv_fails = solver_stats.get("NUM_CONV_FAILS", 0)

        if err_fails > 50:
            return "ERROR_TEST_FAIL"
        if conv_fails > 20:
            return "CONVERGENCE_FAIL"

    # Generic failure
    if return_code != 0:
        return f"NONZERO_EXIT_{return_code}"

    return "UNKNOWN_FAILURE"


def compute_profile_norms(profile: np.ndarray) -> Dict[str, float]:
    """Compute various norms for a concentration profile.

    Args:
        profile: Numpy array of concentration values.
            Can be 1D (single component) or 2D (time x components).

    Returns:
        Dictionary with keys 'l2', 'linf', 'mean', 'max', 'min'.
    """
    if profile.size == 0:
        return {
            "l2": 0.0,
            "linf": 0.0,
            "mean": 0.0,
            "max": 0.0,
            "min": 0.0,
        }

    # Flatten for norm computation
    flat = profile.flatten()

    return {
        "l2": float(np.linalg.norm(flat)),
        "linf": float(np.max(np.abs(flat))),
        "mean": float(np.mean(flat)),
        "max": float(np.max(flat)),
        "min": float(np.min(flat)),
    }


def compute_failure_rate(results: list) -> float:
    """Compute failure rate from a list of RunResult objects.

    Args:
        results: List of RunResult objects.

    Returns:
        Fraction of runs that failed (0.0 to 1.0).
    """
    if not results:
        return 0.0

    failures = sum(1 for r in results if not r.success)
    return failures / len(results)


def compute_avg_steps_per_section(
    stats_list: list,
    n_sections: int = 1,
) -> float:
    """Compute average steps per section across runs.

    Args:
        stats_list: List of solver_stats dictionaries.
        n_sections: Number of sections per simulation.

    Returns:
        Average number of steps per section.
    """
    total_steps = 0
    count = 0

    for stats in stats_list:
        if stats and "NUM_STEPS" in stats:
            total_steps += stats["NUM_STEPS"]
            count += 1

    if count == 0:
        return 0.0

    return total_steps / (count * n_sections)
