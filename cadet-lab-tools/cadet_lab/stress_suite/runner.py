"""Stress test suite runner for CADET simulations.

This module provides functionality to run all stress test cases,
collect results, and generate summary reports.
"""

import json
import statistics
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime

from cadet_lab.stress_suite.cases import get_all_stress_cases
from cadet_lab.harness.run_case import run_case, RunResult
from cadet_lab.telemetry.kpis import compute_kpis, RunKPIs


@dataclass
class StressSuiteResult:
    """Results from running the stress test suite.

    Attributes:
        timestamp: ISO format timestamp of when suite was run.
        total_cases: Total number of test cases run.
        passed: Number of cases that completed successfully.
        failed: Number of cases that failed.
        failure_rate: Fraction of cases that failed (0.0 to 1.0).
        median_wall_time: Median wall clock time across all runs.
        median_err_test_fails: Median error test failures across all runs.
        median_conv_fails: Median convergence failures across all runs.
        case_results: Dictionary mapping case names to individual results.
        full_state_metrics: Optional dictionary of full-state metrics per case.
    """

    timestamp: str
    total_cases: int
    passed: int
    failed: int
    failure_rate: float
    median_wall_time: Optional[float]
    median_err_test_fails: Optional[float]
    median_conv_fails: Optional[float]
    case_results: Dict[str, dict]
    full_state_metrics: Optional[Dict[str, dict]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Union[str, Path]) -> None:
        """Save results to JSON file."""
        Path(path).write_text(self.to_json())


@dataclass
class CaseResult:
    """Result for a single stress test case.

    Attributes:
        name: Name of the stress test case.
        success: Whether the simulation completed successfully.
        return_code: Exit code from CADET.
        wall_time: Wall clock time in seconds.
        failure_reason: Description of failure, or None on success.
        num_steps: Total time steps taken.
        num_err_test_fails: Number of error test failures.
        num_conv_fails: Number of convergence failures.
        input_file: Path to input HDF5 file.
        output_file: Path to output HDF5 file, or None if failed.
    """

    name: str
    success: bool
    return_code: int
    wall_time: float
    failure_reason: Optional[str]
    num_steps: Optional[int]
    num_err_test_fails: Optional[int]
    num_conv_fails: Optional[int]
    input_file: str
    output_file: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def run_stress_suite(
    cadet_cli_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    cases: Optional[List[str]] = None,
    timeout: Optional[float] = 300.0,
    full_state_mode: bool = False,
) -> StressSuiteResult:
    """Run all stress test cases and collect results.

    Args:
        cadet_cli_path: Path to the cadet-cli executable.
        output_dir: Directory for output files. Uses temp directory if None.
        cases: List of case names to run. Runs all if None.
        timeout: Timeout in seconds for each case.
        full_state_mode: Enable full-state output and metrics computation.

    Returns:
        StressSuiteResult containing summary and individual case results.
    """
    cadet_cli_path = Path(cadet_cli_path)

    # Use temp directory if none specified
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="cadet_stress_"))
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Get available stress cases
    all_cases = get_all_stress_cases()

    # Filter cases if specified
    if cases is not None:
        all_cases = [(n, f, k) for n, f, k in all_cases if n in cases]

    # Run each case
    case_results: Dict[str, dict] = {}
    full_state_metrics_dict: Dict[str, dict] = {} if full_state_mode else None
    wall_times: List[float] = []
    err_test_fails: List[int] = []
    conv_fails: List[int] = []
    passed = 0
    failed = 0

    for case_name, case_func, default_kwargs in all_cases:
        # Generate input file
        input_file = output_dir / f"{case_name}_input.h5"
        try:
            # Add enable_full_state_output if in full_state_mode
            kwargs = {**default_kwargs}
            if full_state_mode:
                kwargs["enable_full_state_output"] = True
            case_func(output_path=input_file, **kwargs)
        except Exception as e:
            # Case generation failed
            case_results[case_name] = CaseResult(
                name=case_name,
                success=False,
                return_code=-1,
                wall_time=0.0,
                failure_reason=f"CONFIG_ERROR: {e}",
                num_steps=None,
                num_err_test_fails=None,
                num_conv_fails=None,
                input_file=str(input_file),
                output_file=None,
            ).to_dict()
            failed += 1
            continue

        # Run simulation
        try:
            result = run_case(
                input_file=input_file,
                cadet_cli_path=cadet_cli_path,
                output_dir=output_dir,
                timeout=timeout,
            )
        except Exception as e:
            # Execution failed
            case_results[case_name] = CaseResult(
                name=case_name,
                success=False,
                return_code=-2,
                wall_time=0.0,
                failure_reason=f"EXECUTION_ERROR: {e}",
                num_steps=None,
                num_err_test_fails=None,
                num_conv_fails=None,
                input_file=str(input_file),
                output_file=None,
            ).to_dict()
            failed += 1
            continue

        # Compute KPIs
        kpis = compute_kpis(result)

        # Compute full-state metrics if enabled
        if full_state_mode and result.success and result.output_file:
            try:
                from cadet_lab.telemetry.read_hdf5 import read_solution
                # Use Path object for output_file (Path already imported at module level)
                output_path = result.output_file if isinstance(result.output_file, Path) else Path(result.output_file)
                solution_data = read_solution(output_path, read_full_state=True)
                # Store basic full-state info (can add metrics later if reference available)
                full_state_metrics_dict[case_name] = {
                    "has_bulk": len(solution_data.bulk_profiles) > 0,
                    "has_particle": len(solution_data.particle_profiles) > 0,
                    "has_solid": len(solution_data.solid_profiles) > 0,
                    "has_coordinates": len(solution_data.coordinates.get("axial", {})) > 0,
                }
            except Exception as e:
                full_state_metrics_dict[case_name] = {
                    "error": str(e),
                }

        # Record result
        case_result = CaseResult(
            name=case_name,
            success=result.success,
            return_code=result.return_code,
            wall_time=result.wall_time,
            failure_reason=kpis.failure_reason,
            num_steps=kpis.num_steps,
            num_err_test_fails=kpis.num_err_test_fails,
            num_conv_fails=kpis.num_conv_fails,
            input_file=str(input_file),
            output_file=str(result.output_file) if result.output_file else None,
        )
        case_results[case_name] = case_result.to_dict()

        # Accumulate statistics
        wall_times.append(result.wall_time)
        if kpis.num_err_test_fails is not None:
            err_test_fails.append(kpis.num_err_test_fails)
        if kpis.num_conv_fails is not None:
            conv_fails.append(kpis.num_conv_fails)

        if result.success:
            passed += 1
        else:
            failed += 1

    # Compute summary statistics
    total = passed + failed
    failure_rate = failed / total if total > 0 else 0.0
    median_wall = statistics.median(wall_times) if wall_times else None
    median_err = statistics.median(err_test_fails) if err_test_fails else None
    median_conv = statistics.median(conv_fails) if conv_fails else None

    return StressSuiteResult(
        timestamp=datetime.utcnow().isoformat(),
        total_cases=total,
        passed=passed,
        failed=failed,
        failure_rate=failure_rate,
        median_wall_time=median_wall,
        median_err_test_fails=median_err,
        median_conv_fails=median_conv,
        case_results=case_results,
        full_state_metrics=full_state_metrics_dict,
    )


def run_single_case(
    case_name: str,
    cadet_cli_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    timeout: Optional[float] = 300.0,
    **case_kwargs,
) -> CaseResult:
    """Run a single stress test case.

    Args:
        case_name: Name of the stress test case.
        cadet_cli_path: Path to the cadet-cli executable.
        output_dir: Directory for output files.
        timeout: Timeout in seconds.
        **case_kwargs: Additional arguments for the case generator.

    Returns:
        CaseResult for the single case.

    Raises:
        ValueError: If case_name is not recognized.
    """
    # Find case generator
    all_cases = {n: (f, k) for n, f, k in get_all_stress_cases()}
    if case_name not in all_cases:
        raise ValueError(f"Unknown case: {case_name}. Available: {list(all_cases.keys())}")

    case_func, default_kwargs = all_cases[case_name]
    kwargs = {**default_kwargs, **case_kwargs}

    # Set up output directory
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix=f"cadet_{case_name}_"))
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Generate input
    input_file = output_dir / f"{case_name}_input.h5"
    case_func(output_path=input_file, **kwargs)

    # Run
    result = run_case(
        input_file=input_file,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
        timeout=timeout,
    )

    # Compute KPIs
    kpis = compute_kpis(result)

    return CaseResult(
        name=case_name,
        success=result.success,
        return_code=result.return_code,
        wall_time=result.wall_time,
        failure_reason=kpis.failure_reason,
        num_steps=kpis.num_steps,
        num_err_test_fails=kpis.num_err_test_fails,
        num_conv_fails=kpis.num_conv_fails,
        input_file=str(input_file),
        output_file=str(result.output_file) if result.output_file else None,
    )
