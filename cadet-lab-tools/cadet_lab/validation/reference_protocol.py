"""Reference solution generation protocol for validation.

This module provides functions to generate high-accuracy reference solutions
by either tightening time tolerances or refining spatial discretization.
"""

from pathlib import Path
from typing import Union, Optional, Callable, Any
import shutil
import hashlib
import json
import h5py


def create_reference_config(
    baseline_config: Union[str, Path],
    output_path: Union[str, Path],
    mode: str = "time",
    tolerance_factor: float = 10.0,
    spatial_refinement_factor: int = 2,
) -> Path:
    """Create a reference configuration from baseline config.

    Supports two modes:
    - "time": Tighten tolerances only (ABSTOL /= factor, RELTOL /= factor)
    - "space": Refine spatial resolution only (NELEM *= factor, PAR_NELEM *= factor)

    Both modes enable full-state output flags.

    Args:
        baseline_config: Path to baseline HDF5 configuration file.
        output_path: Path where reference config will be written.
        mode: Either "time" or "space".
        tolerance_factor: Factor to tighten tolerances in time mode (default: 10).
        spatial_refinement_factor: Factor to refine spatial grid in space mode (default: 2).

    Returns:
        Path to created reference configuration file.

    Raises:
        ValueError: If mode is not "time" or "space".
    """
    baseline_config = Path(baseline_config)
    output_path = Path(output_path)

    if mode not in ["time", "space"]:
        raise ValueError(f"Mode must be 'time' or 'space', got '{mode}'")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy baseline to output
    shutil.copy(baseline_config, output_path)

    # Modify configuration based on mode
    with h5py.File(output_path, "r+") as f:
        if mode == "time":
            # Tighten time tolerances only
            _tighten_tolerances(f, tolerance_factor)
        elif mode == "space":
            # Refine spatial discretization only
            _refine_spatial_resolution(f, spatial_refinement_factor)

        # Enable full-state output in both modes
        _enable_full_state_output(f)

    return output_path


def _tighten_tolerances(f: h5py.File, factor: float) -> None:
    """Tighten ABSTOL and RELTOL by dividing by factor."""
    time_int = f["input/solver/time_integrator"]

    if "ABSTOL" in time_int:
        old_abstol = float(time_int["ABSTOL"][()])
        new_abstol = old_abstol / factor
        del time_int["ABSTOL"]
        time_int.create_dataset("ABSTOL", data=new_abstol)

    if "RELTOL" in time_int:
        old_reltol = float(time_int["RELTOL"][()])
        new_reltol = old_reltol / factor
        del time_int["RELTOL"]
        time_int.create_dataset("RELTOL", data=new_reltol)


def _refine_spatial_resolution(f: h5py.File, factor: int) -> None:
    """Refine spatial discretization by multiplying NELEM and PAR_NELEM by factor."""
    model = f["input/model"]

    # Iterate over all units
    for unit_key in model.keys():
        if not unit_key.startswith("unit_"):
            continue

        unit = model[unit_key]

        # Refine column discretization (if present)
        if "discretization" in unit:
            disc = unit["discretization"]
            if "NELEM" in disc:
                old_nelem = int(disc["NELEM"][()])
                new_nelem = old_nelem * factor
                del disc["NELEM"]
                disc.create_dataset("NELEM", data=new_nelem)

        # Refine particle discretization (CADET v6: inside particle_type_XXX)
        for partype_key in unit.keys():
            if partype_key.startswith("particle_type_"):
                partype = unit[partype_key]
                if "discretization" in partype:
                    par_disc = partype["discretization"]
                    if "PAR_NELEM" in par_disc:
                        old_par_nelem = int(par_disc["PAR_NELEM"][()])
                        new_par_nelem = old_par_nelem * factor
                        del par_disc["PAR_NELEM"]
                        par_disc.create_dataset("PAR_NELEM", data=new_par_nelem)


def _enable_full_state_output(f: h5py.File) -> None:
    """Enable full-state output flags (BULK, PARTICLE, SOLID, COORDINATES)."""
    ret = f["input/return"]

    # Iterate over all unit return groups
    for unit_key in ret.keys():
        if not unit_key.startswith("unit_"):
            continue

        unit_ret = ret[unit_key]

        # Set full-state flags
        for flag_name in [
            "WRITE_SOLUTION_BULK",
            "WRITE_SOLUTION_PARTICLE",
            "WRITE_SOLUTION_SOLID",
            "WRITE_COORDINATES",
        ]:
            if flag_name in unit_ret:
                del unit_ret[flag_name]
            unit_ret.create_dataset(flag_name, data=1)


def run_reference(
    case_generator: Callable,
    case_kwargs: dict,
    cadet_cli_path: Union[str, Path],
    output_dir: Union[str, Path],
    mode: str = "time",
    tolerance_factor: float = 10.0,
    spatial_refinement_factor: int = 2,
    cache_dir: Optional[Union[str, Path]] = None,
) -> tuple[Path, Path]:
    """Generate and run a reference solution.

    Creates reference config, runs with cadet-cli, and optionally caches result.

    Args:
        case_generator: Function that generates baseline config (e.g., case_first_step_fail).
        case_kwargs: Keyword arguments to pass to case_generator.
        cadet_cli_path: Path to cadet-cli executable.
        output_dir: Directory where reference outputs will be stored.
        mode: Either "time" or "space" (passed to create_reference_config).
        tolerance_factor: Tolerance tightening factor for time mode.
        spatial_refinement_factor: Spatial refinement factor for space mode.
        cache_dir: Optional directory for caching reference results.

    Returns:
        Tuple of (reference_output_path, reference_config_path).

    Raises:
        RuntimeError: If reference simulation fails.
    """
    from cadet_lab.harness.run_case import run_case

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check cache if enabled
    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_key = _compute_cache_key(case_kwargs, mode, tolerance_factor, spatial_refinement_factor)
        cached_output = cache_dir / f"reference_{cache_key}.h5"
        cached_config = cache_dir / f"reference_{cache_key}_config.h5"
        if cached_output.exists() and cached_config.exists():
            return cached_output, cached_config

    # Generate baseline config (filter out metadata keys starting with _)
    baseline_path = output_dir / "baseline.h5"
    clean_kwargs = {k: v for k, v in case_kwargs.items() if not k.startswith("_")}
    case_generator(output_path=baseline_path, **clean_kwargs)

    # Create reference config
    reference_config = output_dir / f"reference_{mode}.h5"
    create_reference_config(
        baseline_config=baseline_path,
        output_path=reference_config,
        mode=mode,
        tolerance_factor=tolerance_factor,
        spatial_refinement_factor=spatial_refinement_factor,
    )

    # Run reference simulation
    result = run_case(
        input_file=reference_config,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
    )

    # Get output file path (run_case creates it automatically)
    reference_output = result.output_file

    if not result.success:
        raise RuntimeError(
            f"Reference simulation failed with return code {result.return_code}. "
            f"Failure reason: {result.failure_reason}. "
            f"Reference solutions must succeed to establish ground truth."
        )

    # Cache result if enabled
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(reference_output, cached_output)
        shutil.copy(reference_config, cached_config)

    return reference_output, reference_config


def _compute_cache_key(case_kwargs: dict, mode: str, tol_factor: float, spatial_factor: int) -> str:
    """Compute a cache key for reference results."""
    # Create deterministic string from kwargs
    key_data = {
        "case_kwargs": sorted(case_kwargs.items()),
        "mode": mode,
        "tolerance_factor": tol_factor,
        "spatial_refinement_factor": spatial_factor,
    }
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()[:16]
