"""Adaptive step-size advisor for CADET simulations.

This module provides tools to detect excessive error test failures and
automatically retry with reduced initial step sizes.
"""

from pathlib import Path
from typing import Union, Optional, Tuple
import shutil
import h5py

from cadet_lab.harness.run_case import RunResult


def detect_excessive_err_fails(
    result: RunResult,
    err_fail_threshold: int = 5,
) -> bool:
    """Detect if simulation has excessive error test failures.

    Uses direct threshold on num_err_test_fails metric without heuristics.

    Args:
        result: RunResult from run_case().
        err_fail_threshold: Threshold for excessive failures (default: 5).

    Returns:
        True if num_err_test_fails >= threshold, False otherwise.
    """
    if not result.solver_stats:
        return False

    num_err_test_fails = result.solver_stats.get("NUM_ERR_TEST_FAILS", 0)
    return num_err_test_fails >= err_fail_threshold


def run_with_step_advisor(
    input_file: Union[str, Path],
    cadet_cli_path: Union[str, Path],
    output_dir: Union[str, Path],
    err_fail_threshold: int = 5,
    step_reduction_factor: float = 10.0,
    max_retries: int = 2,
) -> Tuple[RunResult, int]:
    """Run simulation with adaptive step-size advisor.

    If excessive error test failures detected, retries with reduced INIT_STEP_SIZE.

    Args:
        input_file: Path to input HDF5 configuration file.
        cadet_cli_path: Path to cadet-cli executable.
        output_dir: Directory for outputs.
        err_fail_threshold: Threshold for excessive error failures (default: 5).
        step_reduction_factor: Factor to reduce INIT_STEP_SIZE by (default: 10).
        max_retries: Maximum number of retries (default: 2).

    Returns:
        Tuple of (final_result, num_retries).
    """
    from cadet_lab.harness.run_case import run_case

    input_file = Path(input_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initial run
    result = run_case(
        input_file=input_file,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
    )

    num_retries = 0

    # Check if retry needed
    while detect_excessive_err_fails(result, err_fail_threshold) and num_retries < max_retries:
        num_retries += 1

        # Create modified config with reduced step size
        retry_config = output_dir / f"retry_{num_retries}.h5"
        _reduce_init_step_size(input_file, retry_config, step_reduction_factor ** num_retries)

        # Run with reduced step size
        result = run_case(
            input_file=retry_config,
            cadet_cli_path=cadet_cli_path,
            output_dir=output_dir,
        )

        # If retry succeeds with fewer failures, accept it
        if not detect_excessive_err_fails(result, err_fail_threshold):
            break

    return result, num_retries


def _reduce_init_step_size(
    input_file: Path,
    output_file: Path,
    reduction_factor: float,
) -> None:
    """Copy config and reduce INIT_STEP_SIZE by reduction_factor.

    Optionally sets MAX_STEP_SIZE for discontinuous cases.

    Args:
        input_file: Source config file.
        output_file: Destination config file.
        reduction_factor: Factor to divide INIT_STEP_SIZE by.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(input_file, output_file)

    with h5py.File(output_file, "r+") as f:
        time_int = f["input/solver/time_integrator"]

        # Reduce INIT_STEP_SIZE
        if "INIT_STEP_SIZE" in time_int:
            old_init_step = float(time_int["INIT_STEP_SIZE"][()])
            new_init_step = old_init_step / reduction_factor
            del time_int["INIT_STEP_SIZE"]
            time_int.create_dataset("INIT_STEP_SIZE", data=new_init_step)

            # Optionally set MAX_STEP_SIZE to limit step growth for discontinuous cases
            # This prevents step size from growing too large after discontinuities
            if "MAX_STEP_SIZE" not in time_int:
                # Set MAX_STEP_SIZE to 10× the new INIT_STEP_SIZE
                max_step_size = new_init_step * 10.0
                time_int.create_dataset("MAX_STEP_SIZE", data=max_step_size)
