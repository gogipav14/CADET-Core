"""Phase D Track 2a: GMRES Stress Testing Suite

Systematically stress-test GMRES to find bottlenecks:
- Peclet number sweep (dispersion-dominated to advection-dominated)
- Multi-component sweep (1 to 8 components)
- Tolerance sweep (loose to tight)
- Kinetics sweep (slow to fast binding)

Goal: Identify if GMRES iteration count grows beyond efficient baseline (4-6 iters/step).
Decision gate: If lin_iters_per_step > 20 OR scaling degradation → proceed to Track 2b.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

from cadet_lab.harness.run_case import run_case
from cadet_lab.telemetry.read_hdf5 import read_solution
from cadet_lab.config_gen.minimal_grm import create_minimal_grm_config


@dataclass
class GMRESStressResult:
    """Result from a single GMRES stress test.

    Attributes:
        test_name: Descriptive name of test
        parameter: Parameter being varied (e.g., 'peclet', 'n_comp')
        value: Value of parameter for this run
        ncol: Number of column discretization elements

        # Solver statistics
        num_steps: Number of time steps taken
        num_lin_iters: Total linear solver iterations
        lin_iters_per_step: Average iterations per step
        num_conv_fails: Number of convergence failures
        num_err_test_fails: Number of error test failures

        # Performance
        wall_time: Wall clock time (seconds)
        success: Whether simulation succeeded

        # Configuration
        abstol: Absolute tolerance
        reltol: Relative tolerance
    """
    test_name: str
    parameter: str
    value: float
    ncol: int

    # Solver stats
    num_steps: Optional[int] = None
    num_lin_iters: Optional[int] = None
    lin_iters_per_step: Optional[float] = None
    num_conv_fails: Optional[int] = None
    num_err_test_fails: Optional[int] = None

    # Performance
    wall_time: Optional[float] = None
    success: bool = False

    # Config
    abstol: float = 1e-6
    reltol: float = 1e-6

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class GMRESStressSuite:
    """Results from complete GMRES stress testing suite.

    Attributes:
        suite_name: Name of stress test suite
        results: List of GMRESStressResult for each test
        timestamp: ISO 8601 timestamp
        metadata: Additional metadata
    """
    suite_name: str
    results: List[GMRESStressResult]
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "suite_name": self.suite_name,
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def save(self, output_path: Path) -> None:
        """Save to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def find_bottlenecks(self, threshold: float = 20.0) -> List[GMRESStressResult]:
        """Find results where lin_iters_per_step exceeds threshold.

        Args:
            threshold: Maximum acceptable iterations per step

        Returns:
            List of results exceeding threshold
        """
        bottlenecks = []
        for r in self.results:
            if r.success and r.lin_iters_per_step is not None:
                if r.lin_iters_per_step > threshold:
                    bottlenecks.append(r)
        return bottlenecks

    def analyze_scaling(self, parameter: str) -> Dict[str, Any]:
        """Analyze how iterations scale with parameter.

        Args:
            parameter: Parameter name to analyze (e.g., 'peclet', 'ncol')

        Returns:
            Dictionary with scaling analysis
        """
        param_results = [r for r in self.results if r.parameter == parameter and r.success]
        if len(param_results) < 2:
            return {"error": "Insufficient data points"}

        # Sort by parameter value
        param_results.sort(key=lambda r: r.value)

        values = [r.value for r in param_results]
        iters = [r.lin_iters_per_step for r in param_results if r.lin_iters_per_step]

        if len(iters) < 2:
            return {"error": "Insufficient valid iteration counts"}

        # Check for degradation
        min_iters = min(iters)
        max_iters = max(iters)
        degradation_ratio = max_iters / min_iters if min_iters > 0 else float('inf')

        return {
            "parameter": parameter,
            "values": values,
            "lin_iters_per_step": iters,
            "min": min_iters,
            "max": max_iters,
            "degradation_ratio": degradation_ratio,
            "is_degrading": degradation_ratio > 2.0,  # More than 2× growth is concerning
        }


def run_gmres_stress_test(
    test_name: str,
    parameter: str,
    value: float,
    config_path: Path,
    cadet_cli_path: Path,
    output_dir: Path,
    ncol: int = 64,
    abstol: float = 1e-6,
    reltol: float = 1e-6,
) -> GMRESStressResult:
    """Run a single GMRES stress test.

    Args:
        test_name: Descriptive test name
        parameter: Parameter being varied
        value: Value of parameter
        config_path: Path to CADET HDF5 config (already generated)
        cadet_cli_path: Path to cadet-cli executable
        output_dir: Output directory
        ncol: Number of column elements
        abstol: Absolute tolerance
        reltol: Relative tolerance

    Returns:
        GMRESStressResult with solver statistics
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run CADET
    run_result = run_case(
        input_file=config_path,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
    )

    # Extract solver statistics
    num_steps = None
    num_lin_iters = None
    lin_iters_per_step = None
    num_conv_fails = None
    num_err_test_fails = None

    if run_result.solver_stats:
        num_steps = run_result.solver_stats.get("NUM_STEPS")
        num_lin_iters = run_result.solver_stats.get("NUM_LIN_ITERS")
        num_conv_fails = run_result.solver_stats.get("NUM_CONV_FAILS", 0)
        num_err_test_fails = run_result.solver_stats.get("NUM_ERR_TEST_FAILS", 0)

        if num_steps and num_lin_iters and num_steps > 0:
            lin_iters_per_step = num_lin_iters / num_steps

    return GMRESStressResult(
        test_name=test_name,
        parameter=parameter,
        value=value,
        ncol=ncol,
        num_steps=num_steps,
        num_lin_iters=num_lin_iters,
        lin_iters_per_step=lin_iters_per_step,
        num_conv_fails=num_conv_fails,
        num_err_test_fails=num_err_test_fails,
        wall_time=run_result.wall_time,
        success=run_result.success,
        abstol=abstol,
        reltol=reltol,
    )


def run_peclet_sweep(
    cadet_cli_path: Path,
    output_dir: Path,
    peclet_values: List[float] = None,
    ncol: int = 64,
) -> List[GMRESStressResult]:
    """Run Peclet number sweep from dispersion-dominated to advection-dominated.

    Args:
        cadet_cli_path: Path to cadet-cli
        output_dir: Output directory
        peclet_values: List of Peclet numbers to test
        ncol: Number of column elements

    Returns:
        List of GMRESStressResult
    """
    if peclet_values is None:
        peclet_values = [100, 500, 1000, 5000, 10000]

    results = []

    for peclet in peclet_values:
        test_name = f"peclet_{peclet}"
        print(f"\n{'='*60}")
        print(f"Running Peclet sweep: Pe={peclet}")
        print(f"{'='*60}")

        # Generate config
        config_path = output_dir / test_name / "config.h5"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        create_minimal_grm_config(
            output_path=config_path,
            velocity=1e-3,
            col_length=0.1,
            peclet=peclet,  # Override dispersion calculation
            binding_ka=0.0,  # No binding (pure transport)
            binding_kd=1.0,
            n_col=ncol,
            n_times=101,
            end_time=200.0,
        )

        # Run test
        result = run_gmres_stress_test(
            test_name=test_name,
            parameter="peclet",
            value=peclet,
            config_path=config_path,
            cadet_cli_path=cadet_cli_path,
            output_dir=output_dir / test_name,
            ncol=ncol,
        )

        results.append(result)

        # Print summary
        if result.success and result.lin_iters_per_step:
            print(f"Result: {result.lin_iters_per_step:.2f} iters/step ({result.num_steps} steps)")
        else:
            print(f"Result: FAILED")

    return results


def run_multicomponent_sweep(
    cadet_cli_path: Path,
    output_dir: Path,
    n_comp_values: List[int] = None,
    ncol: int = 64,
) -> List[GMRESStressResult]:
    """Run multi-component sweep to test GMRES with larger systems.

    Args:
        cadet_cli_path: Path to cadet-cli
        output_dir: Output directory
        n_comp_values: List of component counts
        ncol: Number of column elements

    Returns:
        List of GMRESStressResult
    """
    if n_comp_values is None:
        n_comp_values = [1, 2, 4, 8]

    results = []

    for n_comp in n_comp_values:
        test_name = f"ncomp_{n_comp}"
        print(f"\n{'='*60}")
        print(f"Running multi-component: n_comp={n_comp}")
        print(f"{'='*60}")

        # Generate config
        config_path = output_dir / test_name / "config.h5"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        create_minimal_grm_config(
            output_path=config_path,
            velocity=1e-3,
            col_length=0.1,
            col_dispersion=1e-6,
            binding_ka=0.0,  # No binding
            binding_kd=1.0,
            n_comp=n_comp,
            n_col=ncol,
            n_times=101,
            end_time=100.0,
        )

        # Run test
        result = run_gmres_stress_test(
            test_name=test_name,
            parameter="n_comp",
            value=float(n_comp),
            config_path=config_path,
            cadet_cli_path=cadet_cli_path,
            output_dir=output_dir / test_name,
            ncol=ncol,
        )

        results.append(result)

        # Print summary
        if result.success and result.lin_iters_per_step:
            print(f"Result: {result.lin_iters_per_step:.2f} iters/step ({result.num_steps} steps)")
        else:
            print(f"Result: FAILED")

    return results


def run_tolerance_sweep(
    cadet_cli_path: Path,
    output_dir: Path,
    abstol_values: List[float] = None,
    ncol: int = 64,
) -> List[GMRESStressResult]:
    """Run tolerance sweep from loose to tight.

    Args:
        cadet_cli_path: Path to cadet-cli
        output_dir: Output directory
        abstol_values: List of absolute tolerances (reltol scales with abstol)
        ncol: Number of column elements

    Returns:
        List of GMRESStressResult
    """
    if abstol_values is None:
        abstol_values = [1e-6, 1e-8, 1e-10, 1e-12]

    results = []

    for abstol in abstol_values:
        reltol = abstol  # Keep ratio constant
        test_name = f"abstol_{abstol:.0e}"
        print(f"\n{'='*60}")
        print(f"Running tolerance: ABSTOL={abstol:.0e}, RELTOL={reltol:.0e}")
        print(f"{'='*60}")

        # Generate config
        config_path = output_dir / test_name / "config.h5"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        create_minimal_grm_config(
            output_path=config_path,
            velocity=1e-3,
            col_length=0.1,
            col_dispersion=1e-6,
            binding_ka=0.0,  # No binding
            binding_kd=1.0,
            abstol=abstol,
            reltol=reltol,
            n_col=ncol,
            n_times=101,
            end_time=100.0,
        )

        # Run test
        result = run_gmres_stress_test(
            test_name=test_name,
            parameter="abstol",
            value=abstol,
            config_path=config_path,
            cadet_cli_path=cadet_cli_path,
            output_dir=output_dir / test_name,
            ncol=ncol,
            abstol=abstol,
            reltol=reltol,
        )

        results.append(result)

        # Print summary
        if result.success and result.lin_iters_per_step:
            print(f"Result: {result.lin_iters_per_step:.2f} iters/step ({result.num_steps} steps)")
        else:
            print(f"Result: FAILED")

    return results


def run_kinetics_sweep(
    cadet_cli_path: Path,
    output_dir: Path,
    ka_values: List[float] = None,
    ncol: int = 64,
) -> List[GMRESStressResult]:
    """Run binding kinetics sweep from slow to fast.

    Args:
        cadet_cli_path: Path to cadet-cli
        output_dir: Output directory
        ka_values: List of adsorption rate constants
        ncol: Number of column elements

    Returns:
        List of GMRESStressResult
    """
    if ka_values is None:
        ka_values = [1.0, 10.0, 100.0, 1000.0, 10000.0]

    results = []

    for ka in ka_values:
        kd = ka / 10.0  # Keep equilibrium constant fixed
        test_name = f"ka_{ka:.0e}"
        print(f"\n{'='*60}")
        print(f"Running kinetics: ka={ka:.0e}, kd={kd:.0e}")
        print(f"{'='*60}")

        # Generate config
        config_path = output_dir / test_name / "config.h5"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        create_minimal_grm_config(
            output_path=config_path,
            velocity=1e-3,
            col_length=0.1,
            col_dispersion=1e-6,
            binding_ka=ka,
            binding_kd=kd,
            inlet_concentration=1e-6,  # Dilute
            n_col=ncol,
            n_times=101,
            end_time=100.0,
        )

        # Run test
        result = run_gmres_stress_test(
            test_name=test_name,
            parameter="ka",
            value=ka,
            config_path=config_path,
            cadet_cli_path=cadet_cli_path,
            output_dir=output_dir / test_name,
            ncol=ncol,
        )

        results.append(result)

        # Print summary
        if result.success and result.lin_iters_per_step:
            print(f"Result: {result.lin_iters_per_step:.2f} iters/step ({result.num_steps} steps)")
        else:
            print(f"Result: FAILED")

    return results


def print_stress_summary(suite: GMRESStressSuite) -> None:
    """Print summary of stress test results.

    Args:
        suite: GMRESStressSuite with results
    """
    print(f"\n{'='*80}")
    print(f"GMRES Stress Test Summary: {suite.suite_name}")
    print(f"{'='*80}\n")

    # Group by parameter
    parameters = set(r.parameter for r in suite.results)

    for param in sorted(parameters):
        param_results = [r for r in suite.results if r.parameter == param]

        print(f"\n{param.upper()} Sweep:")
        print(f"{'-'*80}")
        print(f"{'Value':<15} {'Steps':<10} {'Lin Iters':<12} {'Iters/Step':<12} {'Status':<10}")
        print(f"{'-'*80}")

        for r in sorted(param_results, key=lambda x: x.value):
            value_str = f"{r.value:.0e}" if r.value >= 1000 else f"{r.value:.1f}"
            steps_str = str(r.num_steps) if r.num_steps else "N/A"
            lin_iters_str = str(r.num_lin_iters) if r.num_lin_iters else "N/A"
            iters_per_step_str = f"{r.lin_iters_per_step:.2f}" if r.lin_iters_per_step else "N/A"
            status_str = "✅" if r.success else "❌"

            print(f"{value_str:<15} {steps_str:<10} {lin_iters_str:<12} {iters_per_step_str:<12} {status_str:<10}")

        # Scaling analysis
        analysis = suite.analyze_scaling(param)
        if "error" not in analysis:
            print(f"\nScaling: min={analysis['min']:.2f}, max={analysis['max']:.2f}, ratio={analysis['degradation_ratio']:.2f}×")
            if analysis['is_degrading']:
                print(f"⚠️  WARNING: Degradation detected (>{2.0:.1f}× growth)")

    # Check for bottlenecks
    print(f"\n{'='*80}")
    print("Bottleneck Analysis (threshold: 20.0 iters/step)")
    print(f"{'='*80}")

    bottlenecks = suite.find_bottlenecks(threshold=20.0)
    if bottlenecks:
        print(f"\n⚠️  Found {len(bottlenecks)} bottleneck(s):")
        for b in bottlenecks:
            print(f"  - {b.test_name}: {b.lin_iters_per_step:.2f} iters/step")
    else:
        print("\n✅ No bottlenecks found - GMRES is efficient across all tests!")

    print(f"\n{'='*80}")
