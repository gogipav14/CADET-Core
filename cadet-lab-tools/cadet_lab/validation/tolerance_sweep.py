"""Tolerance sweep for work-precision analysis.

This module provides tools to sweep tolerance parameters and analyze
the accuracy-cost trade-off in CADET simulations.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Union, Optional, Callable, List
from datetime import datetime
import json
import h5py

from cadet_lab.telemetry.full_state_metrics import compare_full_state
from cadet_lab.telemetry.read_hdf5 import read_solution


@dataclass
class TolerancePoint:
    """Single point in tolerance sweep.

    Attributes:
        abstol: Absolute tolerance used.
        reltol: Relative tolerance used.
        num_steps: Total time steps taken.
        num_err_test_fails: Number of error test failures.
        num_conv_fails: Number of convergence failures.
        wall_time: Wall clock time in seconds.
        linf_error: L-infinity error vs reference.
        scaled_rms_error: Scaled RMS error vs reference.
        success: Whether simulation succeeded.
    """

    abstol: float
    reltol: float
    num_steps: Optional[int] = None
    num_err_test_fails: Optional[int] = None
    num_conv_fails: Optional[int] = None
    wall_time: Optional[float] = None
    linf_error: Optional[float] = None
    scaled_rms_error: Optional[float] = None
    success: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "abstol": self.abstol,
            "reltol": self.reltol,
            "num_steps": self.num_steps,
            "num_err_test_fails": self.num_err_test_fails,
            "num_conv_fails": self.num_conv_fails,
            "wall_time": self.wall_time,
            "linf_error": self.linf_error,
            "scaled_rms_error": self.scaled_rms_error,
            "success": self.success,
        }


@dataclass
class WorkPrecisionResult:
    """Result of work-precision tolerance sweep.

    Attributes:
        case_name: Name of the test case.
        reference_tolerances: Tolerances used for reference (dict with abstol, reltol).
        reference_resolution: Spatial resolution of reference (dict with nelem_col, nelem_par).
        sweep_points: List of TolerancePoint dictionaries.
        timestamp: ISO 8601 timestamp when sweep was performed.
    """

    case_name: str
    reference_tolerances: dict
    reference_resolution: dict
    sweep_points: List[dict] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def save(self, output_path: Union[str, Path]) -> None:
        """Save to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "case_name": self.case_name,
            "reference": {
                "tolerances": self.reference_tolerances,
                "resolution": self.reference_resolution,
            },
            "sweep_points": self.sweep_points,
            "timestamp": self.timestamp,
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(input_path: Union[str, Path]) -> "WorkPrecisionResult":
        """Load from JSON file."""
        with open(input_path, "r") as f:
            data = json.load(f)

        return WorkPrecisionResult(
            case_name=data["case_name"],
            reference_tolerances=data["reference"]["tolerances"],
            reference_resolution=data["reference"]["resolution"],
            sweep_points=data["sweep_points"],
            timestamp=data["timestamp"],
        )


def run_tolerance_sweep(
    case_generator: Callable,
    case_kwargs: dict,
    reference_output: Union[str, Path],
    cadet_cli_path: Union[str, Path],
    output_dir: Union[str, Path],
    abstol_grid: Optional[List[float]] = None,
    reltol_grid: Optional[List[float]] = None,
    reference_config: Optional[Union[str, Path]] = None,
) -> WorkPrecisionResult:
    """Run tolerance sweep to generate work-precision data.

    Sweeps a cartesian product of abstol × reltol values, comparing each
    against the reference solution using full-state metrics.

    Args:
        case_generator: Function that generates config (e.g., case_first_step_fail).
        case_kwargs: Keyword arguments for case_generator.
        reference_output: Path to reference solution HDF5 file.
        cadet_cli_path: Path to cadet-cli executable.
        output_dir: Directory where sweep outputs will be stored.
        abstol_grid: List of abstol values to sweep (default: [1e-9, 3e-9, 1e-8, 3e-8]).
        reltol_grid: List of reltol values to sweep (default: [1e-6, 3e-6, 1e-5, 3e-5]).
        reference_config: Path to reference config file (for extracting tolerances/resolution).
                          If None, assumes reference_output contains input section.

    Returns:
        WorkPrecisionResult with all sweep points.
    """
    from cadet_lab.harness.run_case import run_case

    # Default tolerance grids (4×4 = 16 points)
    if abstol_grid is None:
        abstol_grid = [1e-9, 3e-9, 1e-8, 3e-8]
    if reltol_grid is None:
        reltol_grid = [1e-6, 3e-6, 1e-5, 3e-5]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_output = Path(reference_output)

    # Use reference_config if provided, otherwise fallback to reference_output
    config_file = Path(reference_config) if reference_config else reference_output

    # Read reference solution with full-state data
    reference_data = read_solution(reference_output, read_full_state=True)

    # Extract reference tolerances and resolution from config file
    reference_tolerances = _extract_tolerances(config_file)
    reference_resolution = _extract_resolution(config_file)

    # Get case name from kwargs
    case_name = case_kwargs.get("_case_name", "unknown")

    sweep_points = []

    # Cartesian product sweep
    for abstol in abstol_grid:
        for reltol in reltol_grid:
            # Generate config with these tolerances (filter metadata keys)
            test_config = output_dir / f"sweep_atol{abstol:.0e}_rtol{reltol:.0e}.h5"
            clean_kwargs = {k: v for k, v in case_kwargs.items() if not k.startswith("_")}
            case_generator(
                output_path=test_config,
                abstol=abstol,
                reltol=reltol,
                enable_full_state_output=True,
                **clean_kwargs,
            )

            # Run simulation
            result = run_case(
                input_file=test_config,
                cadet_cli_path=cadet_cli_path,
                output_dir=output_dir,
            )

            test_output = result.output_file

            # Create TolerancePoint
            point = TolerancePoint(
                abstol=abstol,
                reltol=reltol,
                success=result.success,
                wall_time=result.wall_time,
            )

            if result.success:
                # Read solver stats
                if result.solver_stats:
                    point.num_steps = result.solver_stats.get("NUM_STEPS")
                    point.num_err_test_fails = result.solver_stats.get("NUM_ERR_TEST_FAILS")
                    point.num_conv_fails = result.solver_stats.get("NUM_NONLIN_CONV_FAILS")

                # Compare against reference
                try:
                    test_data = read_solution(test_output, read_full_state=True)
                    metrics = compare_full_state(
                        test=test_data,
                        reference=reference_data,
                        abstol=abstol,
                        reltol=reltol,
                    )
                    point.linf_error = metrics.linf_global
                    point.scaled_rms_error = metrics.scaled_rms_global
                except Exception as e:
                    print(f"Warning: Failed to compare full-state for atol={abstol}, rtol={reltol}: {e}")

            sweep_points.append(point.to_dict())

    return WorkPrecisionResult(
        case_name=case_name,
        reference_tolerances=reference_tolerances,
        reference_resolution=reference_resolution,
        sweep_points=sweep_points,
    )


def _extract_tolerances(config_path: Path) -> dict:
    """Extract ABSTOL and RELTOL from config file."""
    with h5py.File(config_path, "r") as f:
        time_int = f["input/solver/time_integrator"]
        return {
            "abstol": float(time_int["ABSTOL"][()]),
            "reltol": float(time_int["RELTOL"][()]),
        }


def _extract_resolution(config_path: Path) -> dict:
    """Extract spatial resolution (NELEM, PAR_NELEM) from config file."""
    with h5py.File(config_path, "r") as f:
        model = f["input/model"]

        # Find first GRM unit
        for unit_key in model.keys():
            if not unit_key.startswith("unit_"):
                continue

            unit = model[unit_key]

            # Check unit type
            if "UNIT_TYPE" not in unit:
                continue

            unit_type_data = unit["UNIT_TYPE"][()]
            if isinstance(unit_type_data, bytes):
                unit_type = unit_type_data.decode()
            else:
                unit_type = str(unit_type_data)

            if unit_type != "GENERAL_RATE_MODEL":
                continue

            # Extract column NELEM
            nelem_col = None
            if "discretization" in unit and "NELEM" in unit["discretization"]:
                nelem_col = int(unit["discretization"]["NELEM"][()])

            # Extract particle PAR_NELEM (from first particle type)
            nelem_par = None
            for partype_key in unit.keys():
                if partype_key.startswith("particle_type_"):
                    partype = unit[partype_key]
                    if "discretization" in partype and "PAR_NELEM" in partype["discretization"]:
                        nelem_par = int(partype["discretization"]["PAR_NELEM"][()])
                        break

            return {
                "nelem_col": nelem_col,
                "nelem_par": nelem_par,
            }

    return {"nelem_col": None, "nelem_par": None}
