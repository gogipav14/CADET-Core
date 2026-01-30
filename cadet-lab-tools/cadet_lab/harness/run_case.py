"""Run CADET simulations and capture results.

This module provides the main harness for executing CADET simulations
via subprocess, capturing outputs, and returning structured results.
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple, Union, Any
import numpy as np


@dataclass
class RunResult:
    """Result of a CADET simulation run.

    Attributes:
        return_code: Exit code from cadet-cli (0 = success).
        wall_time: Wall clock time in seconds.
        failure_reason: Description of failure if any, None on success.
        n_times: Number of solution time points.
        outlet_shape: Shape of outlet concentration array, or None if failed.
        solver_stats: Dictionary of solver statistics if available.
        stdout: Captured standard output from cadet-cli.
        stderr: Captured standard error from cadet-cli.
        log_file: Path to log file if separate logging was used.
        input_file: Path to the input HDF5 file.
        output_file: Path to the output HDF5 file, or None if failed.
    """

    return_code: int
    wall_time: float
    failure_reason: Optional[str]
    n_times: int
    outlet_shape: Optional[Tuple[int, ...]]
    solver_stats: Optional[dict]
    stdout: str
    stderr: str
    log_file: Optional[Path]
    input_file: Path
    output_file: Optional[Path]

    @property
    def success(self) -> bool:
        """Return True if simulation completed successfully."""
        return self.return_code == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Convert Path objects to strings
        d["input_file"] = str(self.input_file) if self.input_file else None
        d["output_file"] = str(self.output_file) if self.output_file else None
        d["log_file"] = str(self.log_file) if self.log_file else None
        # Convert tuple to list for JSON
        if d["outlet_shape"] is not None:
            d["outlet_shape"] = list(d["outlet_shape"])
        return d

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_report(self, path: Union[str, Path]) -> None:
        """Save result as JSON report file."""
        path = Path(path)
        path.write_text(self.to_json())


def run_case(
    input_file: Union[str, Path],
    cadet_cli_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    timeout: Optional[float] = None,
    _skip_cli_check: bool = False,
) -> RunResult:
    """Run a CADET simulation and return structured results.

    Args:
        input_file: Path to the input HDF5 file.
        cadet_cli_path: Path to the cadet-cli executable.
        output_dir: Directory for output files. Defaults to input file directory.
        timeout: Maximum time in seconds to wait for simulation. None = no limit.
        _skip_cli_check: Internal flag to skip CLI existence check (for testing).

    Returns:
        RunResult containing all captured data and statistics.

    Raises:
        FileNotFoundError: If input file or cadet-cli not found.
    """
    input_file = Path(input_file)
    cadet_cli_path = Path(cadet_cli_path)

    # Validate inputs
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    if not _skip_cli_check and not cadet_cli_path.exists():
        raise FileNotFoundError(f"cadet-cli not found: {cadet_cli_path}")

    # Determine output directory and file
    if output_dir is None:
        output_dir = input_file.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # CADET writes output to same file by default, or we can specify
    # For safety, we'll copy input to output location if different
    output_file = output_dir / f"{input_file.stem}_output.h5"

    # If output dir differs from input dir, copy input file
    if output_dir != input_file.parent:
        import shutil
        shutil.copy2(input_file, output_file)
        run_file = output_file
    else:
        # Run in place - CADET modifies the input file
        run_file = input_file
        output_file = input_file

    # Build command
    cmd = [str(cadet_cli_path), str(run_file)]

    # Run simulation
    start_time = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(output_dir),
        )
        return_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as e:
        wall_time = time.perf_counter() - start_time
        return RunResult(
            return_code=-1,
            wall_time=wall_time,
            failure_reason="TIMEOUT",
            n_times=0,
            outlet_shape=None,
            solver_stats=None,
            stdout=e.stdout or "",
            stderr=e.stderr or "",
            log_file=None,
            input_file=input_file,
            output_file=None,
        )
    except Exception as e:
        wall_time = time.perf_counter() - start_time
        return RunResult(
            return_code=-2,
            wall_time=wall_time,
            failure_reason=f"EXCEPTION: {type(e).__name__}: {e}",
            n_times=0,
            outlet_shape=None,
            solver_stats=None,
            stdout="",
            stderr=str(e),
            log_file=None,
            input_file=input_file,
            output_file=None,
        )

    wall_time = time.perf_counter() - start_time

    # Try to read output data
    n_times, outlet_shape, solver_stats = _read_output_if_exists(output_file)

    # Determine failure reason
    failure_reason = None
    if return_code != 0:
        failure_reason = _determine_failure_reason(return_code, stdout, stderr)

    return RunResult(
        return_code=return_code,
        wall_time=wall_time,
        failure_reason=failure_reason,
        n_times=n_times,
        outlet_shape=outlet_shape,
        solver_stats=solver_stats,
        stdout=stdout,
        stderr=stderr,
        log_file=None,
        input_file=input_file,
        output_file=output_file if output_file.exists() else None,
    )


def _read_output_if_exists(
    output_file: Path,
) -> Tuple[int, Optional[Tuple[int, ...]], Optional[dict]]:
    """Read basic info from output file if it exists.

    Returns (n_times, outlet_shape, solver_stats).
    """
    if not output_file.exists():
        return 0, None, None

    try:
        from cadet_lab.telemetry.read_hdf5 import read_solution

        solution = read_solution(output_file)

        n_times = len(solution.solution_times)

        # Get shape of first outlet profile
        outlet_shape = None
        if solution.outlet_profiles:
            first_profile = next(iter(solution.outlet_profiles.values()))
            outlet_shape = first_profile.shape

        return n_times, outlet_shape, solution.solver_stats

    except Exception:
        # If reading fails, return minimal info
        return 0, None, None


def _determine_failure_reason(
    return_code: int,
    stdout: str,
    stderr: str,
) -> str:
    """Determine failure reason from return code and output."""
    combined = stdout + stderr

    # Check for known IDAS failure patterns
    if "IDA_CONV_FAIL" in combined or "Newton" in combined and "fail" in combined.lower():
        return "CONVERGENCE_FAIL"

    if "IDA_ERR_FAIL" in combined or "error test" in combined.lower():
        return "ERROR_TEST_FAIL"

    if "maximum" in combined.lower() and "step" in combined.lower():
        return "MAX_STEPS_EXCEEDED"

    if "memory" in combined.lower():
        return "MEMORY_ERROR"

    if return_code != 0:
        return f"NONZERO_EXIT_{return_code}"

    return "UNKNOWN_FAILURE"
