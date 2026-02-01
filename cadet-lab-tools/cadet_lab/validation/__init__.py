"""Validation tools for CADET simulations."""

from cadet_lab.validation.reference_protocol import (
    create_reference_config,
    run_reference,
)
from cadet_lab.validation.tolerance_sweep import (
    run_tolerance_sweep,
    TolerancePoint,
    WorkPrecisionResult,
)
from cadet_lab.validation.step_advisor import (
    detect_excessive_err_fails,
    run_with_step_advisor,
)
from cadet_lab.validation.spatial_convergence import (
    run_spatial_convergence_check,
    SpatialConvergenceResult,
)

__all__ = [
    "create_reference_config",
    "run_reference",
    "run_tolerance_sweep",
    "TolerancePoint",
    "WorkPrecisionResult",
    "detect_excessive_err_fails",
    "run_with_step_advisor",
    "run_spatial_convergence_check",
    "SpatialConvergenceResult",
]
