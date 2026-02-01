"""Spatial convergence verification for CADET simulations.

This module provides tools to verify that spatial discretization is adequate
by comparing baseline and refined solutions.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Union, Callable, Optional
from datetime import datetime
import json
import numpy as np
from scipy.interpolate import interp1d

from cadet_lab.telemetry.full_state_metrics import compare_full_state
from cadet_lab.telemetry.read_hdf5 import read_solution, SolutionData
from cadet_lab.validation.reference_protocol import create_reference_config
import h5py as h5py_module


@dataclass
class SpatialConvergenceResult:
    """Result of spatial convergence check.

    Attributes:
        case_name: Name of the test case.
        baseline_resolution: Baseline spatial resolution (dict with nelem_col, nelem_par).
        refined_resolution: Refined spatial resolution (dict with nelem_col, nelem_par).
        linf_delta: L-infinity difference between refined and baseline.
        scaled_rms_delta: Scaled RMS difference between refined and baseline.
        convergence_achieved: Whether convergence criterion met.
        threshold: Threshold used for convergence check.
        timestamp: ISO 8601 timestamp.
        coordinates_present: Whether coordinates were present in HDF5 output.
        interpolation_method: "coordinate-based" or "uniform-fallback".
        confidence_level: "high", "medium", or "low" based on coordinate availability.
        refinement_levels: Number of refinement iterations performed.
        warnings: List of warning messages about convergence quality.
    """

    case_name: str
    baseline_resolution: dict
    refined_resolution: dict
    linf_delta: float
    scaled_rms_delta: float
    convergence_achieved: bool
    threshold: float
    timestamp: str
    coordinates_present: bool = False
    interpolation_method: str = "uniform-fallback"
    confidence_level: str = "medium"
    refinement_levels: int = 1
    warnings: list = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def save(self, output_path: Union[str, Path]) -> None:
        """Save to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "case_name": self.case_name,
            "baseline_resolution": self.baseline_resolution,
            "refined_resolution": self.refined_resolution,
            "linf_delta": self.linf_delta,
            "scaled_rms_delta": self.scaled_rms_delta,
            "convergence_achieved": self.convergence_achieved,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "coordinates_present": self.coordinates_present,
            "interpolation_method": self.interpolation_method,
            "confidence_level": self.confidence_level,
            "refinement_levels": self.refinement_levels,
            "warnings": self.warnings,
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)


def _compute_coordinate_confidence(
    baseline_data: SolutionData,
    refined_data: SolutionData,
    baseline_config: Path,
    case_name: str,
) -> tuple:
    """Compute coordinate confidence level and interpolation method.

    Args:
        baseline_data: Baseline solution data.
        refined_data: Refined solution data.
        baseline_config: Path to baseline config.
        case_name: Name of test case.

    Returns:
        Tuple of (coordinates_present, interpolation_method, confidence_level, warnings).
    """
    warnings = []

    # Check if coordinates are present in output
    baseline_has_coords = bool(
        baseline_data.coordinates.get("axial")
        or baseline_data.coordinates.get("particle")
    )
    refined_has_coords = bool(
        refined_data.coordinates.get("axial")
        or refined_data.coordinates.get("particle")
    )

    coordinates_present = baseline_has_coords and refined_has_coords

    if coordinates_present:
        interpolation_method = "coordinate-based"
        confidence_level = "high"
    else:
        interpolation_method = "uniform-fallback"

        # Determine if baseline is uniform discretization
        is_uniform = _check_uniform_discretization(baseline_config)

        # Check if case has sharp fronts (spatial challenge)
        is_sharp_front = "sharp_front" in case_name.lower()

        if is_uniform and not is_sharp_front:
            confidence_level = "medium"
            warnings.append(
                "Coordinates not present in HDF5 output (CADET v6.x limitation). "
                "Using uniform grid fallback. Confidence is medium for uniform discretization."
            )
        else:
            confidence_level = "low"
            warnings.append(
                "Coordinates not present in HDF5 output. "
                "Using uniform grid fallback. Spatial convergence may be inaccurate "
                "for non-uniform discretization or sharp fronts."
            )

            if confidence_level == "low":
                warnings.append(
                    f"Recommendation: Increase baseline spatial resolution (NELEM × 2) "
                    f"to mitigate uncertainty from coordinate absence."
                )

    return coordinates_present, interpolation_method, confidence_level, warnings


def _check_uniform_discretization(config_path: Path) -> bool:
    """Check if config uses uniform spatial discretization.

    Args:
        config_path: Path to HDF5 config file.

    Returns:
        True if discretization is uniform (DG, FV with NELEM).
    """
    try:
        with h5py_module.File(config_path, "r") as f:
            # Check first column unit
            if "input/model/unit_001/discretization" in f:
                disc = f["input/model/unit_001/discretization"]
                # If NELEM is present, discretization is uniform (DG or FV)
                return "NELEM" in disc
    except Exception:
        pass

    # Default to assuming non-uniform (conservative)
    return False


def run_spatial_convergence_check(
    case_generator: Callable,
    case_kwargs: dict,
    cadet_cli_path: Union[str, Path],
    output_dir: Union[str, Path],
    spatial_refinement_factor: int = 2,
    threshold: float = 1e-3,
    refinement_levels: int = 1,
) -> SpatialConvergenceResult:
    """Run spatial convergence check by comparing baseline and refined solutions.

    Generates baseline and spatially refined configs with same tolerances,
    runs both, interpolates refined to baseline grid, and compares.

    Args:
        case_generator: Function that generates config (e.g., case_sharp_front).
        case_kwargs: Keyword arguments for case_generator.
        cadet_cli_path: Path to cadet-cli executable.
        output_dir: Directory where outputs will be stored.
        spatial_refinement_factor: Factor to refine spatial grid (default: 2).
        threshold: Scaled RMS threshold for convergence (default: 1e-3).
        refinement_levels: Number of refinement iterations performed (default: 1).

    Returns:
        SpatialConvergenceResult with convergence assessment and confidence tracking.
    """
    from cadet_lab.harness.run_case import run_case
    from cadet_lab.validation.tolerance_sweep import _extract_resolution

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get case name
    case_name = case_kwargs.get("_case_name", "unknown")

    # Generate baseline config with full-state output and coordinates enabled
    baseline_config = output_dir / "baseline.h5"
    clean_kwargs = {k: v for k, v in case_kwargs.items() if not k.startswith("_")}
    case_generator(
        output_path=baseline_config,
        enable_full_state_output=True,
        **clean_kwargs,
    )

    # Run baseline
    baseline_result = run_case(
        input_file=baseline_config,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
    )

    baseline_output = baseline_result.output_file

    if not baseline_result.success:
        raise RuntimeError(
            f"Baseline simulation failed: {baseline_result.failure_reason}"
        )

    # Extract baseline resolution
    baseline_resolution = _extract_resolution(baseline_config)

    # Create refined config (space mode, same tolerances)
    refined_config = output_dir / "refined.h5"
    create_reference_config(
        baseline_config=baseline_config,
        output_path=refined_config,
        mode="space",
        spatial_refinement_factor=spatial_refinement_factor,
    )

    # Run refined
    refined_result = run_case(
        input_file=refined_config,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
    )

    refined_output = refined_result.output_file

    if not refined_result.success:
        raise RuntimeError(
            f"Refined simulation failed: {refined_result.failure_reason}"
        )

    # Extract refined resolution
    refined_resolution = _extract_resolution(refined_config)

    # Read both solutions with full-state and coordinates
    baseline_data = read_solution(baseline_output, read_full_state=True)
    refined_data = read_solution(refined_output, read_full_state=True)

    # Interpolate refined solution to baseline grid
    interpolated_refined = _interpolate_to_baseline_grid(
        refined_data=refined_data,
        baseline_data=baseline_data,
    )

    # Compare interpolated refined vs baseline
    # Use baseline tolerances for scaled RMS computation
    abstol = case_kwargs.get("abstol", 1e-6)
    reltol = case_kwargs.get("reltol", 1e-6)

    metrics = compare_full_state(
        test=interpolated_refined,
        reference=baseline_data,
        abstol=abstol,
        reltol=reltol,
    )

    convergence_achieved = metrics.scaled_rms_global < threshold

    # Compute coordinate confidence
    (
        coordinates_present,
        interpolation_method,
        confidence_level,
        warnings,
    ) = _compute_coordinate_confidence(
        baseline_data=baseline_data,
        refined_data=refined_data,
        baseline_config=baseline_config,
        case_name=case_name,
    )

    return SpatialConvergenceResult(
        case_name=case_name,
        baseline_resolution=baseline_resolution,
        refined_resolution=refined_resolution,
        linf_delta=metrics.linf_global,
        scaled_rms_delta=metrics.scaled_rms_global,
        convergence_achieved=convergence_achieved,
        threshold=threshold,
        timestamp=datetime.now().isoformat(),
        coordinates_present=coordinates_present,
        interpolation_method=interpolation_method,
        confidence_level=confidence_level,
        refinement_levels=refinement_levels,
        warnings=warnings,
    )


def _interpolate_to_baseline_grid(
    refined_data: SolutionData,
    baseline_data: SolutionData,
    baseline_config: Optional[Path] = None,
    refined_config: Optional[Path] = None,
) -> SolutionData:
    """Interpolate refined solution data to baseline grid using coordinates.

    Uses coordinate-based interpolation for both axial and particle dimensions.
    If coordinates are not in the output, computes them from config parameters.

    Args:
        refined_data: Refined solution with full-state data.
        baseline_data: Baseline solution with full-state data.
        baseline_config: Optional path to baseline config (for computing coordinates).
        refined_config: Optional path to refined config (for computing coordinates).

    Returns:
        New SolutionData with refined data interpolated to baseline grid.
    """
    interpolated = SolutionData(
        solution_times=baseline_data.solution_times.copy(),
        outlet_profiles={},
    )

    # Interpolate bulk profiles
    for unit_id in baseline_data.bulk_profiles.keys():
        if unit_id not in refined_data.bulk_profiles:
            continue

        baseline_bulk = baseline_data.bulk_profiles[unit_id]
        refined_bulk = refined_data.bulk_profiles[unit_id]

        # Get axial coordinates (from output or compute from config)
        baseline_coords = baseline_data.coordinates.get("axial", {}).get(unit_id)
        refined_coords = refined_data.coordinates.get("axial", {}).get(unit_id)

        # If coordinates not in output, compute from config
        if baseline_coords is None and baseline_config:
            baseline_coords = _compute_axial_coordinates(baseline_config, unit_id)
        if refined_coords is None and refined_config:
            refined_coords = _compute_axial_coordinates(refined_config, unit_id)

        if baseline_coords is None or refined_coords is None:
            # Fall back to uniform index-based interpolation
            baseline_coords = np.linspace(0, 1, baseline_bulk.shape[1])
            refined_coords = np.linspace(0, 1, refined_bulk.shape[1])

        # Interpolate along axial dimension
        interpolated.bulk_profiles[unit_id] = _interpolate_axial(
            data=refined_bulk,
            refined_coords=refined_coords,
            baseline_coords=baseline_coords,
        )

    # Interpolate particle profiles
    for key in baseline_data.particle_profiles.keys():
        if key not in refined_data.particle_profiles:
            continue

        unit_id, partype = key
        baseline_particle = baseline_data.particle_profiles[key]
        refined_particle = refined_data.particle_profiles[key]

        # Get both axial and particle coordinates
        baseline_axial = baseline_data.coordinates.get("axial", {}).get(unit_id)
        refined_axial = refined_data.coordinates.get("axial", {}).get(unit_id)
        baseline_radial = baseline_data.coordinates.get("particle", {}).get(key)
        refined_radial = refined_data.coordinates.get("particle", {}).get(key)

        # Fall back to uniform grids if coordinates not available
        if baseline_axial is None:
            baseline_axial = np.linspace(0, 1, baseline_particle.shape[1])
        if refined_axial is None:
            refined_axial = np.linspace(0, 1, refined_particle.shape[1])
        if baseline_radial is None:
            baseline_radial = np.linspace(0, 1, baseline_particle.shape[2])
        if refined_radial is None:
            refined_radial = np.linspace(0, 1, refined_particle.shape[2])

        # Interpolate along both dimensions
        interpolated.particle_profiles[key] = _interpolate_2d(
            data=refined_particle,
            refined_axial=refined_axial,
            baseline_axial=baseline_axial,
            refined_radial=refined_radial,
            baseline_radial=baseline_radial,
        )

    # Interpolate solid profiles (same coordinates as particle)
    for key in baseline_data.solid_profiles.keys():
        if key not in refined_data.solid_profiles:
            continue

        unit_id, partype = key
        baseline_solid = baseline_data.solid_profiles[key]
        refined_solid = refined_data.solid_profiles[key]

        # Get both axial and particle coordinates
        baseline_axial = baseline_data.coordinates.get("axial", {}).get(unit_id)
        refined_axial = refined_data.coordinates.get("axial", {}).get(unit_id)
        baseline_radial = baseline_data.coordinates.get("particle", {}).get(key)
        refined_radial = refined_data.coordinates.get("particle", {}).get(key)

        # Fall back to uniform grids if coordinates not available
        if baseline_axial is None:
            baseline_axial = np.linspace(0, 1, baseline_solid.shape[1])
        if refined_axial is None:
            refined_axial = np.linspace(0, 1, refined_solid.shape[1])
        if baseline_radial is None:
            baseline_radial = np.linspace(0, 1, baseline_solid.shape[2])
        if refined_radial is None:
            refined_radial = np.linspace(0, 1, refined_solid.shape[2])

        # Interpolate along both dimensions
        interpolated.solid_profiles[key] = _interpolate_2d(
            data=refined_solid,
            refined_axial=refined_axial,
            baseline_axial=baseline_axial,
            refined_radial=refined_radial,
            baseline_radial=baseline_radial,
        )

    return interpolated


def _interpolate_axial(
    data: np.ndarray,
    refined_coords: np.ndarray,
    baseline_coords: np.ndarray,
) -> np.ndarray:
    """Interpolate along axial dimension.

    Args:
        data: Array with shape (n_times, n_axial_refined, ...).
        refined_coords: Refined axial coordinates (1D array).
        baseline_coords: Baseline axial coordinates (1D array).

    Returns:
        Interpolated array with shape (n_times, n_axial_baseline, ...).
    """
    n_times = data.shape[0]
    n_baseline = len(baseline_coords)

    # Handle trailing dimensions (components, etc.)
    trailing_shape = data.shape[2:] if data.ndim > 2 else ()

    output_shape = (n_times, n_baseline) + trailing_shape
    output = np.zeros(output_shape)

    # Interpolate each time point
    for t in range(n_times):
        if data.ndim == 2:
            # Shape: (n_axial,)
            f = interp1d(refined_coords, data[t, :], kind="linear", fill_value="extrapolate")
            output[t, :] = f(baseline_coords)
        else:
            # Shape: (n_axial, ...)
            # Interpolate along axis 0 for each trailing index
            for idx in np.ndindex(trailing_shape):
                f = interp1d(
                    refined_coords,
                    data[t, :][(...,) + idx],
                    kind="linear",
                    fill_value="extrapolate",
                )
                output[t, :][(...,) + idx] = f(baseline_coords)

    return output


def _interpolate_2d(
    data: np.ndarray,
    refined_axial: np.ndarray,
    baseline_axial: np.ndarray,
    refined_radial: np.ndarray,
    baseline_radial: np.ndarray,
) -> np.ndarray:
    """Interpolate along both axial and radial dimensions.

    Args:
        data: Array with shape (n_times, n_axial_refined, n_radial_refined, ...).
        refined_axial: Refined axial coordinates.
        baseline_axial: Baseline axial coordinates.
        refined_radial: Refined radial coordinates.
        baseline_radial: Baseline radial coordinates.

    Returns:
        Interpolated array with shape (n_times, n_axial_baseline, n_radial_baseline, ...).
    """
    n_times = data.shape[0]
    n_baseline_axial = len(baseline_axial)
    n_baseline_radial = len(baseline_radial)

    # Handle trailing dimensions
    trailing_shape = data.shape[3:] if data.ndim > 3 else ()

    output_shape = (n_times, n_baseline_axial, n_baseline_radial) + trailing_shape
    output = np.zeros(output_shape)

    # Interpolate each time point
    for t in range(n_times):
        # First interpolate along axial dimension
        temp = np.zeros((n_baseline_axial, data.shape[2]) + trailing_shape)

        if data.ndim == 3:
            # No trailing dimensions
            for j in range(data.shape[2]):
                f_axial = interp1d(
                    refined_axial,
                    data[t, :, j],
                    kind="linear",
                    fill_value="extrapolate",
                )
                temp[:, j] = f_axial(baseline_axial)
        else:
            # With trailing dimensions
            for j in range(data.shape[2]):
                for idx in np.ndindex(trailing_shape):
                    f_axial = interp1d(
                        refined_axial,
                        data[t, :, j][(...,) + idx],
                        kind="linear",
                        fill_value="extrapolate",
                    )
                    temp[:, j][(...,) + idx] = f_axial(baseline_axial)

        # Then interpolate along radial dimension
        if data.ndim == 3:
            for i in range(n_baseline_axial):
                f_radial = interp1d(
                    refined_radial,
                    temp[i, :],
                    kind="linear",
                    fill_value="extrapolate",
                )
                output[t, i, :] = f_radial(baseline_radial)
        else:
            for i in range(n_baseline_axial):
                for idx in np.ndindex(trailing_shape):
                    f_radial = interp1d(
                        refined_radial,
                        temp[i, :][(...,) + idx],
                        kind="linear",
                        fill_value="extrapolate",
                    )
                    output[t, i, :][(...,) + idx] = f_radial(baseline_radial)

    return output
