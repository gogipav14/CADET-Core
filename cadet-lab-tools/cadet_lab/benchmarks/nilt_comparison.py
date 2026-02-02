"""NILT vs CADET benchmark comparison engine for Phase D Track 1.

Provides utilities to run NILT vs CADET benchmarks across multiple scaling
tiers, measuring accuracy and speedup for linear problems.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any
import time
import json
import numpy as np

from cadet_lab.nilt import fft_nilt, eps_im_max
from cadet_lab.nilt.compare_to_cadet import (
    ComparisonResult,
    compute_comparison_metrics,
    interpolate_to_common_grid,
)
from cadet_lab.harness.run_case import run_case
from cadet_lab.telemetry.read_hdf5 import read_solution
from cadet_lab.benchmarks.problem_registry import ProblemDefinition, ScalingTier


@dataclass
class NiltBenchmarkResult:
    """Result from NILT vs CADET benchmark at a single scaling tier.

    Attributes:
        problem_id: Problem identifier
        tier_name: Scaling tier name (e.g., "small", "medium")
        ncol: Number of column cells
        npar: Number of particle cells
        dofs: Total degrees of freedom

        # Accuracy metrics
        rmse: Root mean squared error
        l2_norm: L2 norm of difference
        linf_norm: L∞ norm of difference
        relative_l2_error: Relative L2 error

        # Performance metrics
        nilt_time: NILT solve time (seconds)
        cadet_time: CADET solve time (seconds)
        speedup: Speedup factor (cadet_time / nilt_time)

        # NILT convergence diagnostics
        eps_im: Imaginary component diagnostic (should be ~1e-10)
        nilt_success: Whether NILT converged successfully

        # CADET solver stats
        cadet_steps: Number of time steps taken by CADET
        cadet_success: Whether CADET succeeded
    """
    problem_id: str
    tier_name: str
    ncol: int
    npar: int
    dofs: int

    # Accuracy
    rmse: float
    l2_norm: float
    linf_norm: float
    relative_l2_error: float

    # Performance
    nilt_time: float
    cadet_time: float
    speedup: float

    # Diagnostics
    eps_im: float
    nilt_success: bool
    cadet_steps: Optional[int] = None
    cadet_success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class NiltScalingStudy:
    """Results from NILT scaling study across multiple tiers.

    Attributes:
        problem_id: Problem identifier
        results: List of NiltBenchmarkResult for each tier
        timestamp: ISO 8601 timestamp
        metadata: Additional metadata
    """
    problem_id: str
    results: List[NiltBenchmarkResult]
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "problem_id": self.problem_id,
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def save(self, output_path: Path) -> None:
        """Save to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


def run_nilt_vs_cadet_benchmark(
    problem: ProblemDefinition,
    tier: ScalingTier,
    transfer_function: Callable,
    cadet_cli_path: Path,
    output_dir: Path,
    nilt_params: Optional[Dict[str, Any]] = None,
) -> NiltBenchmarkResult:
    """Run NILT vs CADET benchmark at a single scaling tier.

    Args:
        problem: ProblemDefinition for the test case
        tier: ScalingTier configuration (ncol, npar, etc.)
        transfer_function: Transfer function f_hat(s) for NILT
        cadet_cli_path: Path to cadet-cli executable
        output_dir: Directory for outputs
        nilt_params: Optional NILT parameters (alpha, N, etc.)

    Returns:
        NiltBenchmarkResult with accuracy and performance metrics

    Raises:
        RuntimeError: If CADET simulation fails
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up NILT parameters
    if nilt_params is None:
        nilt_params = {
            "alpha": 0.5,  # CFL-informed default
            "N": 256,      # FFT size
            "t_final": 100.0,
        }

    # === Run NILT ===
    t_final = nilt_params["t_final"]
    n_times = 201  # Standard number of time points for CADET

    nilt_start = time.time()
    try:
        # fft_nilt signature: (F, a, T, N) where T is half-period
        # Returns: (f, t, z_ifft, eps_im)
        y_nilt, t_grid_nilt, z_ifft, eps_im_val = fft_nilt(
            F=transfer_function,
            a=nilt_params["alpha"],
            T=t_final / 2.0,  # Half-period (aliasing period = 2T)
            N=nilt_params["N"],
        )
        nilt_time = time.time() - nilt_start
        nilt_success = True
    except Exception as e:
        print(f"NILT failed: {e}")
        nilt_time = float("inf")
        nilt_success = False
        # Create dummy arrays
        t_grid_nilt = np.linspace(0, t_final, 201)
        y_nilt = np.zeros_like(t_grid_nilt)
        eps_im_val = float("inf")

    # === Run CADET ===
    # Generate CADET config with tier's spatial resolution
    config_path = output_dir / f"config_{tier.name}.h5"
    problem_params = problem.default_params.copy()
    problem_params["n_col"] = tier.ncol
    problem_params["n_par"] = tier.npar
    problem_params["n_times"] = n_times
    problem_params["end_time"] = t_final

    problem.generator(output_path=config_path, **problem_params)

    # Run CADET
    cadet_start = time.time()
    run_result = run_case(
        input_file=config_path,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
    )
    cadet_time = time.time() - cadet_start

    if not run_result.success:
        raise RuntimeError(
            f"CADET simulation failed: {run_result.failure_reason}"
        )

    # Read CADET output
    solution = read_solution(run_result.output_file)

    # Extract outlet concentration (assume single component, last unit is outlet)
    outlet_unit = max(solution.outlet_profiles.keys())  # e.g., "unit_002"
    y_cadet_2d = solution.outlet_profiles[outlet_unit]

    # Handle multi-dimensional output (time x components)
    if y_cadet_2d.ndim == 2:
        y_cadet = y_cadet_2d[:, 0]  # Take first component
    else:
        y_cadet = y_cadet_2d

    t_grid_cadet = solution.solution_times

    # === Compare on common grid ===
    t_common, y_nilt_interp, y_cadet_interp = interpolate_to_common_grid(
        t_grid_nilt, y_nilt,  # NILT already returns real part
        t_grid_cadet, y_cadet,
        n_points=200,
    )

    comparison = compute_comparison_metrics(y_nilt_interp, y_cadet_interp, t_common)

    # === Compute speedup ===
    speedup = cadet_time / nilt_time if nilt_time > 0 else 0.0

    # === Extract CADET solver stats ===
    cadet_steps = None
    if run_result.solver_stats:
        cadet_steps = run_result.solver_stats.get("NUM_STEPS")

    return NiltBenchmarkResult(
        problem_id=problem.id,
        tier_name=tier.name,
        ncol=tier.ncol,
        npar=tier.npar,
        dofs=tier.expected_dofs,
        rmse=comparison.rmse,
        l2_norm=comparison.l2_norm,
        linf_norm=comparison.linf_norm,
        relative_l2_error=comparison.relative_l2_error,
        nilt_time=nilt_time,
        cadet_time=cadet_time,
        speedup=speedup,
        eps_im=eps_im_val,
        nilt_success=nilt_success,
        cadet_steps=cadet_steps,
        cadet_success=run_result.success,
    )


def run_scaling_study(
    problem: ProblemDefinition,
    transfer_function: Callable,
    cadet_cli_path: Path,
    output_dir: Path,
    tiers: Optional[List[ScalingTier]] = None,
    nilt_params: Optional[Dict[str, Any]] = None,
) -> NiltScalingStudy:
    """Run NILT vs CADET scaling study across multiple tiers.

    Args:
        problem: ProblemDefinition for the test case
        transfer_function: Transfer function f_hat(s) for NILT
        cadet_cli_path: Path to cadet-cli executable
        output_dir: Directory for outputs
        tiers: Optional list of ScalingTier configs (uses problem.scaling_tiers if None)
        nilt_params: Optional NILT parameters

    Returns:
        NiltScalingStudy with results for all tiers
    """
    from datetime import datetime

    if tiers is None:
        tiers = problem.scaling_tiers

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for tier in tiers:
        print(f"\n{'='*60}")
        print(f"Running {problem.name} @ {tier.name} (NCOL={tier.ncol}, NPAR={tier.npar})")
        print(f"{'='*60}")

        tier_output_dir = output_dir / tier.name

        result = run_nilt_vs_cadet_benchmark(
            problem=problem,
            tier=tier,
            transfer_function=transfer_function,
            cadet_cli_path=cadet_cli_path,
            output_dir=tier_output_dir,
            nilt_params=nilt_params,
        )

        results.append(result)

        # Print summary
        print(f"\nResults for {tier.name}:")
        print(f"  RMSE: {result.rmse:.6e}")
        print(f"  Relative L2 error: {result.relative_l2_error:.6e}")
        print(f"  NILT time: {result.nilt_time:.4f} s")
        print(f"  CADET time: {result.cadet_time:.4f} s")
        print(f"  Speedup: {result.speedup:.2f}×")
        print(f"  ε_Im: {result.eps_im:.6e}")

    return NiltScalingStudy(
        problem_id=problem.id,
        results=results,
        timestamp=datetime.now().isoformat(),
        metadata={
            "nilt_params": nilt_params or {},
            "n_tiers": len(tiers),
        },
    )


def print_scaling_summary(study: NiltScalingStudy) -> None:
    """Print summary table of scaling study results.

    Args:
        study: NiltScalingStudy to summarize
    """
    print(f"\n{'='*80}")
    print(f"NILT vs CADET Scaling Study: {study.problem_id}")
    print(f"{'='*80}\n")

    # Header
    print(f"{'Tier':<10} {'NCOL':<6} {'DOFs':<8} {'RMSE':<12} {'Rel L2':<12} {'Speedup':<10}")
    print(f"{'-'*80}")

    # Rows
    for r in study.results:
        print(
            f"{r.tier_name:<10} {r.ncol:<6} {r.dofs:<8} "
            f"{r.rmse:<12.6e} {r.relative_l2_error:<12.6e} {r.speedup:<10.2f}×"
        )

    print(f"\n{'='*80}")

    # Check accuracy criteria
    all_accurate = all(r.rmse < 1e-6 and r.relative_l2_error < 0.01 for r in study.results)
    if all_accurate:
        print("✅ All tiers meet accuracy criteria (RMSE < 1e-6, Rel L2 < 1%)")
    else:
        print("⚠️  Some tiers fail accuracy criteria")

    # Scaling analysis
    if len(study.results) >= 2:
        small_speedup = study.results[0].speedup
        large_speedup = study.results[-1].speedup
        print(f"\n📊 Scaling: {small_speedup:.1f}× (small) → {large_speedup:.1f}× (xlarge)")

        if large_speedup > small_speedup * 3:
            print("✅ Superlinear speedup scaling (excellent for NILT)")
        elif large_speedup > small_speedup:
            print("✅ Positive speedup scaling")
        else:
            print("⚠️  Speedup does not scale with problem size")
