"""Read solution data from CADET HDF5 output files.

This module provides functions to extract solution times, outlet profiles,
and solver statistics from CADET simulation output files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Union
import numpy as np
import h5py


@dataclass
class SolutionData:
    """Container for CADET solution data extracted from HDF5 output.

    Attributes:
        solution_times: Array of time points where solution was recorded.
        outlet_profiles: Dictionary mapping unit IDs to outlet concentration arrays.
        inlet_profiles: Dictionary mapping unit IDs to inlet concentration arrays.
        solver_stats: Dictionary of solver statistics if available (from versioned
            /output/solver_statistics/ group), or None.
        file_path: Path to the source HDF5 file.
    """

    solution_times: np.ndarray
    outlet_profiles: Dict[str, np.ndarray]
    inlet_profiles: Dict[str, np.ndarray] = field(default_factory=dict)
    solver_stats: Optional[Dict[str, any]] = None
    file_path: Optional[Path] = None


def read_solution(
    file_path: Union[str, Path],
    read_inlet: bool = False,
    read_bulk: bool = False,
) -> SolutionData:
    """Read solution data from a CADET HDF5 output file.

    Args:
        file_path: Path to the HDF5 output file.
        read_inlet: If True, also read inlet profiles.
        read_bulk: If True, also read bulk phase data (not implemented yet).

    Returns:
        SolutionData containing solution times, profiles, and statistics.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a valid CADET output file.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"HDF5 file not found: {file_path}")

    try:
        with h5py.File(file_path, "r") as f:
            # Read solution times
            solution_times = _read_solution_times(f)

            # Read outlet profiles
            outlet_profiles = _read_outlet_profiles(f)

            # Read inlet profiles if requested
            inlet_profiles = {}
            if read_inlet:
                inlet_profiles = _read_inlet_profiles(f)

            # Read solver statistics if available
            solver_stats = _read_solver_stats(f)

            return SolutionData(
                solution_times=solution_times,
                outlet_profiles=outlet_profiles,
                inlet_profiles=inlet_profiles,
                solver_stats=solver_stats,
                file_path=file_path,
            )

    except OSError as e:
        raise ValueError(f"Failed to read HDF5 file {file_path}: {e}") from e


def _read_solution_times(f: h5py.File) -> np.ndarray:
    """Read solution times from HDF5 file.

    Searches for SOLUTION_TIMES in standard locations.
    """
    # Standard location
    paths_to_try = [
        "output/solution/SOLUTION_TIMES",
        "output/SOLUTION_TIMES",
    ]

    for path in paths_to_try:
        if path in f:
            return np.array(f[path])

    raise ValueError("SOLUTION_TIMES not found in HDF5 file")


def _read_outlet_profiles(f: h5py.File) -> Dict[str, np.ndarray]:
    """Read outlet concentration profiles from all units.

    Returns dictionary mapping unit IDs (e.g., 'unit_002') to arrays.
    """
    profiles = {}

    # Check if solution group exists
    if "output/solution" not in f:
        return profiles

    solution = f["output/solution"]

    # Iterate over unit groups
    for key in solution.keys():
        if key.startswith("unit_"):
            unit_group = solution[key]

            # Try different outlet dataset names
            outlet_names = [
                "SOLUTION_OUTLET",
                "SOLUTION_OUTLET_COMP_000",
            ]

            for name in outlet_names:
                if name in unit_group:
                    profiles[key] = np.array(unit_group[name])
                    break

            # Also check for multi-component outlets
            if key not in profiles:
                # Look for pattern SOLUTION_OUTLET_COMP_*
                comp_arrays = []
                comp_idx = 0
                while f"SOLUTION_OUTLET_COMP_{comp_idx:03d}" in unit_group:
                    comp_arrays.append(np.array(unit_group[f"SOLUTION_OUTLET_COMP_{comp_idx:03d}"]))
                    comp_idx += 1

                if comp_arrays:
                    # Stack components along last axis
                    profiles[key] = np.stack(comp_arrays, axis=-1)

    return profiles


def _read_inlet_profiles(f: h5py.File) -> Dict[str, np.ndarray]:
    """Read inlet concentration profiles from all units."""
    profiles = {}

    if "output/solution" not in f:
        return profiles

    solution = f["output/solution"]

    for key in solution.keys():
        if key.startswith("unit_"):
            unit_group = solution[key]

            inlet_names = [
                "SOLUTION_INLET",
                "SOLUTION_INLET_COMP_000",
            ]

            for name in inlet_names:
                if name in unit_group:
                    profiles[key] = np.array(unit_group[name])
                    break

    return profiles


def _read_solver_stats(f: h5py.File) -> Optional[Dict[str, any]]:
    """Read solver statistics if available.

    Looks for versioned /output/solver_statistics/ group.
    Falls back to checking common statistic locations.

    The solver_statistics group (when present) contains:
        - VERSION: Schema version (int)
        - NUM_STEPS: Total time steps taken
        - NUM_RHS_EVALS: Total residual evaluations
        - NUM_LINSOL_SETUPS: Total linear solver setups
        - NUM_ERR_TEST_FAILS: Total error test failures
        - NUM_NONLIN_CONV_FAILS: Total nonlinear convergence failures
        - NUM_NONLIN_ITERS: Total nonlinear solver iterations
    """
    stats = {}

    # Check for versioned solver_statistics group (Phase A2 enhancement)
    if "output/solver_statistics" in f:
        stats_group = f["output/solver_statistics"]

        # Check version for compatibility - can be dataset or attribute
        if "VERSION" in stats_group:
            version = int(stats_group["VERSION"][()])
        else:
            version = stats_group.attrs.get("VERSION", 1)
        stats["_version"] = version

        # Read available statistics - handle both scalar and array formats
        stat_names = [
            "NUM_STEPS",
            "NUM_RHS_EVALS",
            "NUM_LINSOL_SETUPS",
            "NUM_ERR_TEST_FAILS",
            "NUM_NONLIN_CONV_FAILS",  # New name from C++ implementation
            "NUM_NONLIN_ITERS",       # New field
            "NUM_CONV_FAILS",         # Legacy name (fallback)
        ]

        for name in stat_names:
            if name in stats_group:
                data = stats_group[name][()]
                # Handle both scalar and array formats
                if hasattr(data, 'ndim') and data.ndim > 0:
                    stats[name] = int(np.sum(data))
                else:
                    stats[name] = int(data)

        # Normalize legacy name to new name
        if "NUM_CONV_FAILS" in stats and "NUM_NONLIN_CONV_FAILS" not in stats:
            stats["NUM_NONLIN_CONV_FAILS"] = stats.pop("NUM_CONV_FAILS")

    # Also check meta group for timing info
    if "output/meta" in f:
        meta = f["output/meta"]
        if "TIME_SIM" in meta:
            stats["TIME_SIM"] = float(meta["TIME_SIM"][()])

    # Check /meta at root level too (some CADET versions)
    if "meta" in f and "output/meta" not in f:
        meta = f["meta"]
        if "TIME_SIM" in meta:
            stats["TIME_SIM"] = float(meta["TIME_SIM"][()])

    return stats if stats else None


def get_outlet_unit_id(f: h5py.File) -> Optional[str]:
    """Find the outlet unit ID in an HDF5 file.

    Returns the unit_XXX identifier for the OUTLET unit, or None if not found.
    """
    if "input/model" not in f:
        return None

    model = f["input/model"]

    for key in model.keys():
        if key.startswith("unit_"):
            unit = model[key]
            if "UNIT_TYPE" in unit:
                unit_type = unit["UNIT_TYPE"][()]
                if isinstance(unit_type, bytes):
                    unit_type = unit_type.decode()
                if unit_type == "OUTLET":
                    return key

    return None
