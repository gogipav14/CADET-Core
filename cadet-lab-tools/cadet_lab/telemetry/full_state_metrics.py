"""Full-state accuracy metrics for CADET simulations.

This module provides functions to compare full-state simulation results
(bulk, particle, and solid phase concentrations) against reference solutions
using scaled RMS and L-infinity norms.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import numpy as np

from cadet_lab.telemetry.read_hdf5 import SolutionData


@dataclass
class FullStateMetrics:
    """Full-state accuracy metrics comparing test to reference solution.

    Attributes:
        linf_bulk: L-infinity error in bulk phase.
        linf_particle: L-infinity error in particle phase.
        linf_solid: L-infinity error in solid phase.
        linf_global: Maximum L-infinity across all phases.
        scaled_rms_bulk: Scaled RMS error in bulk phase.
        scaled_rms_particle: Scaled RMS error in particle phase.
        scaled_rms_solid: Scaled RMS error in solid phase.
        scaled_rms_global: DOF-weighted mean scaled RMS across all phases.
        n_bulk_dofs: Number of bulk phase DOFs.
        n_particle_dofs: Number of particle phase DOFs.
        n_solid_dofs: Number of solid phase DOFs.
    """

    linf_bulk: float
    linf_particle: float
    linf_solid: float
    linf_global: float
    scaled_rms_bulk: float
    scaled_rms_particle: float
    scaled_rms_solid: float
    scaled_rms_global: float
    n_bulk_dofs: int
    n_particle_dofs: int
    n_solid_dofs: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "linf_bulk": self.linf_bulk,
            "linf_particle": self.linf_particle,
            "linf_solid": self.linf_solid,
            "linf_global": self.linf_global,
            "scaled_rms_bulk": self.scaled_rms_bulk,
            "scaled_rms_particle": self.scaled_rms_particle,
            "scaled_rms_solid": self.scaled_rms_solid,
            "scaled_rms_global": self.scaled_rms_global,
            "n_bulk_dofs": self.n_bulk_dofs,
            "n_particle_dofs": self.n_particle_dofs,
            "n_solid_dofs": self.n_solid_dofs,
        }


def compute_scaled_rms(
    y: np.ndarray,
    y_ref: np.ndarray,
    abstol: float,
    reltol: float,
) -> float:
    """Compute scaled RMS error between test and reference arrays.

    Formula: sqrt(mean((y - y_ref)^2 / (atol + rtol * max(|y|, |y_ref|))^2))

    This is the error metric used by SUNDIALS integrators internally.

    Args:
        y: Test solution array.
        y_ref: Reference solution array.
        abstol: Absolute tolerance for scaling.
        reltol: Relative tolerance for scaling.

    Returns:
        Scaled RMS error (dimensionless).
    """
    if y.shape != y_ref.shape:
        raise ValueError(
            f"Shape mismatch: y.shape={y.shape}, y_ref.shape={y_ref.shape}"
        )

    if y.size == 0:
        return 0.0

    # Flatten arrays for vectorized operations
    y_flat = y.flatten()
    y_ref_flat = y_ref.flatten()

    # Compute error
    error = y_flat - y_ref_flat

    # Compute scaling factor (atol + rtol * max(|y|, |y_ref|))
    scale = abstol + reltol * np.maximum(np.abs(y_flat), np.abs(y_ref_flat))

    # Avoid division by zero
    scale = np.maximum(scale, 1e-30)

    # Scaled error
    scaled_error = error / scale

    # RMS
    rms = np.sqrt(np.mean(scaled_error**2))

    return float(rms)


def compute_linf(y: np.ndarray, y_ref: np.ndarray) -> float:
    """Compute L-infinity (maximum absolute) error.

    Formula: max|y - y_ref|

    Args:
        y: Test solution array.
        y_ref: Reference solution array.

    Returns:
        Maximum absolute error.
    """
    if y.shape != y_ref.shape:
        raise ValueError(
            f"Shape mismatch: y.shape={y.shape}, y_ref.shape={y_ref.shape}"
        )

    if y.size == 0:
        return 0.0

    error = np.abs(y - y_ref)
    return float(np.max(error))


def compare_full_state(
    test: SolutionData,
    reference: SolutionData,
    abstol: float,
    reltol: float,
    unit_id: str = "unit_001",
) -> FullStateMetrics:
    """Compare full-state data between test and reference solutions.

    Computes scaled RMS and L-infinity errors across bulk, particle,
    and solid phases. Aggregates phase-wise metrics into global metrics.

    Args:
        test: Test solution data.
        reference: Reference solution data.
        abstol: Absolute tolerance for scaled RMS computation.
        reltol: Relative tolerance for scaled RMS computation.
        unit_id: Unit ID to compare (default: "unit_001").

    Returns:
        FullStateMetrics with aggregated errors across all phases.

    Raises:
        ValueError: If required data not present or shapes don't match.
    """
    # Initialize metrics
    linf_bulk = 0.0
    linf_particle = 0.0
    linf_solid = 0.0
    scaled_rms_bulk = 0.0
    scaled_rms_particle = 0.0
    scaled_rms_solid = 0.0
    n_bulk_dofs = 0
    n_particle_dofs = 0
    n_solid_dofs = 0

    # Compare bulk phase
    if unit_id in test.bulk_profiles and unit_id in reference.bulk_profiles:
        y_bulk = test.bulk_profiles[unit_id]
        y_ref_bulk = reference.bulk_profiles[unit_id]
        linf_bulk = compute_linf(y_bulk, y_ref_bulk)
        scaled_rms_bulk = compute_scaled_rms(y_bulk, y_ref_bulk, abstol, reltol)
        n_bulk_dofs = y_bulk.size

    # Compare particle phase
    particle_keys_test = {k for k in test.particle_profiles.keys() if k[0] == unit_id}
    particle_keys_ref = {k for k in reference.particle_profiles.keys() if k[0] == unit_id}

    if particle_keys_test and particle_keys_ref:
        if particle_keys_test != particle_keys_ref:
            raise ValueError(
                f"Particle type mismatch: test has {particle_keys_test}, "
                f"reference has {particle_keys_ref}"
            )

        # Aggregate across particle types
        particle_linf_list = []
        particle_rms_list = []
        particle_dof_list = []

        for key in particle_keys_test:
            y_particle = test.particle_profiles[key]
            y_ref_particle = reference.particle_profiles[key]
            particle_linf_list.append(compute_linf(y_particle, y_ref_particle))
            particle_rms_list.append(
                compute_scaled_rms(y_particle, y_ref_particle, abstol, reltol)
            )
            particle_dof_list.append(y_particle.size)

        # Use max for Linf, DOF-weighted mean for RMS
        linf_particle = max(particle_linf_list) if particle_linf_list else 0.0
        n_particle_dofs = sum(particle_dof_list)
        if n_particle_dofs > 0:
            scaled_rms_particle = sum(
                rms * dof for rms, dof in zip(particle_rms_list, particle_dof_list)
            ) / n_particle_dofs

    # Compare solid phase
    solid_keys_test = {k for k in test.solid_profiles.keys() if k[0] == unit_id}
    solid_keys_ref = {k for k in reference.solid_profiles.keys() if k[0] == unit_id}

    if solid_keys_test and solid_keys_ref:
        if solid_keys_test != solid_keys_ref:
            raise ValueError(
                f"Solid type mismatch: test has {solid_keys_test}, "
                f"reference has {solid_keys_ref}"
            )

        # Aggregate across solid types
        solid_linf_list = []
        solid_rms_list = []
        solid_dof_list = []

        for key in solid_keys_test:
            y_solid = test.solid_profiles[key]
            y_ref_solid = reference.solid_profiles[key]
            solid_linf_list.append(compute_linf(y_solid, y_ref_solid))
            solid_rms_list.append(
                compute_scaled_rms(y_solid, y_ref_solid, abstol, reltol)
            )
            solid_dof_list.append(y_solid.size)

        # Use max for Linf, DOF-weighted mean for RMS
        linf_solid = max(solid_linf_list) if solid_linf_list else 0.0
        n_solid_dofs = sum(solid_dof_list)
        if n_solid_dofs > 0:
            scaled_rms_solid = sum(
                rms * dof for rms, dof in zip(solid_rms_list, solid_dof_list)
            ) / n_solid_dofs

    # Compute global metrics
    linf_global = max(linf_bulk, linf_particle, linf_solid)

    total_dofs = n_bulk_dofs + n_particle_dofs + n_solid_dofs
    if total_dofs > 0:
        scaled_rms_global = (
            scaled_rms_bulk * n_bulk_dofs +
            scaled_rms_particle * n_particle_dofs +
            scaled_rms_solid * n_solid_dofs
        ) / total_dofs
    else:
        scaled_rms_global = 0.0

    return FullStateMetrics(
        linf_bulk=linf_bulk,
        linf_particle=linf_particle,
        linf_solid=linf_solid,
        linf_global=linf_global,
        scaled_rms_bulk=scaled_rms_bulk,
        scaled_rms_particle=scaled_rms_particle,
        scaled_rms_solid=scaled_rms_solid,
        scaled_rms_global=scaled_rms_global,
        n_bulk_dofs=n_bulk_dofs,
        n_particle_dofs=n_particle_dofs,
        n_solid_dofs=n_solid_dofs,
    )
