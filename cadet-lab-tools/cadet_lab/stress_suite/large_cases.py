"""Large-scale stress test cases for Phase D solver instrumentation.

This module provides enlarged benchmark configurations designed to stress
the linear solver (GMRES) and expose preconditioning optimization opportunities.

Phase D Goal: Generate problems that take seconds (not milliseconds) to reveal
where linear solver iterations dominate cost.
"""

from pathlib import Path
from typing import Union
import numpy as np

from cadet_lab.config_gen.minimal_grm import create_minimal_grm_config


def case_large_sharp_front_spatial(
    output_path: Union[str, Path],
    cadet_path: Union[str, Path] = None,  # Not used, for compatibility with runner
    **kwargs,
) -> Path:
    """Enlarged sharp front case with 64× spatial resolution increase.

    **Spatial Resolution Scaling (Primary):**
    - NELEM: 8 → 64 (8× column elements)
    - PAR_NELEM: 1 → 8 (8× particle elements)
    - State dimension: ~64 → ~2,304 (36× increase)
    - Jacobian entries: ~4,096 → ~5,308,416 (1,296× increase!)

    **Expected Problem Size:**
    - Wall time: 10-60 seconds (200-1000× baseline)
    - NUM_STEPS: 400-600 (similar to baseline, spatial doesn't affect time stepping much)
    - NUM_LIN_ITERS: 20,000-100,000 (this is the key metric!)
    - Linear iters per step: 50-150 (indicates strong preconditioning payoff potential)

    **Physics Parameters (Maintain Sharp Front Character):**
    - Peclet: 5000 (1000 → 5000, sharper front)
    - Lower dispersion, sharper gradients

    **Tolerances:**
    - Use Phase C recommended settings for sharp_front case
    - abstol: 3e-9, reltol: 1e-5 (from phase_c_recommended_settings.json)

    **Goal:** Expose linear solver bottleneck to justify Phase D-3 preconditioning work.

    Args:
        output_path: Path where HDF5 file will be written.
        cadet_path: Path to cadet-cli (not used, for compatibility).
        **kwargs: Additional arguments override defaults.

    Returns:
        Path to created HDF5 file.
    """
    # Spatial resolution (primary scaling)
    kwargs.setdefault("n_col", 64)           # 8 → 64 (8× column elements)
    kwargs.setdefault("par_nelem", 8)        # 1 → 8 (8× particle elements)

    # Physics parameters (maintain sharp front character)
    kwargs.setdefault("peclet", 5000.0)      # 1000 → 5000 (sharper front)
    kwargs.setdefault("col_length", 0.1)
    kwargs.setdefault("velocity", 1e-3)

    # Derived: col_dispersion will be calculated from peclet in create_minimal_grm_config
    # col_dispersion = velocity * col_length / peclet = 1e-3 * 0.1 / 5000 = 2e-8

    kwargs.setdefault("film_diffusion", 1e-4)
    kwargs.setdefault("pore_diffusion", 1e-6)

    # Time parameters (baseline)
    kwargs.setdefault("end_time", 200.0)     # Same as original sharp_front
    kwargs.setdefault("n_times", 101)        # 51 → 101 for smoother output

    # Tolerances (use Phase C recommended settings for sharp_front)
    # From artifacts/phase_c_recommended_settings.json or plan defaults
    kwargs.setdefault("abstol", 3e-9)        # Phase C recommended
    kwargs.setdefault("reltol", 1e-5)        # Phase C recommended
    kwargs.setdefault("init_step_size", 1e-8)

    # Keep simple for clarity
    kwargs.setdefault("n_comp", 1)           # Single component
    kwargs.setdefault("enable_full_state_output", True)  # Need full state for analysis

    # CRITICAL: Enable GMRES by setting MAX_KRYLOV > 0
    # MAX_KRYLOV=0 uses direct solver (no iterations)
    # MAX_KRYLOV=50 means GMRES with Krylov subspace dimension 50
    kwargs.setdefault("max_krylov", 50)

    return create_minimal_grm_config(
        output_path=output_path,
        **kwargs,
    )


def case_medium_sharp_front_spatial(
    output_path: Union[str, Path],
    cadet_path: Union[str, Path] = None,
    **kwargs,
) -> Path:
    """Medium-resolution sharp front for scaling study.

    **Spatial Resolution:**
    - NELEM: 8 → 32 (4× column elements)
    - PAR_NELEM: 1 → 4 (4× particle elements)
    - State dimension: ~64 → ~576 (9× increase)

    **Expected:**
    - Wall time: 2-8 seconds
    - Intermediate scaling check between baseline (NELEM=8) and large (NELEM=64)

    Args:
        output_path: Path where HDF5 file will be written.
        cadet_path: Path to cadet-cli (not used, for compatibility).
        **kwargs: Additional arguments override defaults.

    Returns:
        Path to created HDF5 file.
    """
    kwargs.setdefault("n_col", 32)
    kwargs.setdefault("par_nelem", 4)
    kwargs.setdefault("peclet", 5000.0)
    kwargs.setdefault("end_time", 200.0)
    kwargs.setdefault("n_times", 101)
    kwargs.setdefault("abstol", 3e-9)
    kwargs.setdefault("reltol", 1e-5)
    kwargs.setdefault("init_step_size", 1e-8)
    kwargs.setdefault("n_comp", 1)
    kwargs.setdefault("enable_full_state_output", True)
    kwargs.setdefault("max_krylov", 50)  # Enable GMRES

    return create_minimal_grm_config(
        output_path=output_path,
        **kwargs,
    )


def case_large_multicomp_stiff_binding(
    output_path: Union[str, Path],
    cadet_path: Union[str, Path] = None,
    **kwargs,
) -> Path:
    """Multi-component case with stiff binding (chemistry-dominated).

    **Scaling:**
    - NELEM: 32 (moderate spatial)
    - PAR_NELEM: 4
    - n_comp: 4 (multi-component!)
    - Stiff binding: ka=1e6, kd=1e4

    **Expected:**
    - Wall time: 10-30 seconds
    - High NUM_NONLIN_ITERS (nonlinear convergence challenge)

    Args:
        output_path: Path where HDF5 file will be written.
        cadet_path: Path to cadet-cli (not used, for compatibility).
        **kwargs: Additional arguments override defaults.

    Returns:
        Path to created HDF5 file.
    """
    kwargs.setdefault("n_col", 32)
    kwargs.setdefault("par_nelem", 4)
    kwargs.setdefault("n_comp", 4)
    kwargs.setdefault("binding_ka", 1e6)
    kwargs.setdefault("binding_kd", 1e4)
    kwargs.setdefault("end_time", 200.0)
    kwargs.setdefault("n_times", 101)
    kwargs.setdefault("abstol", 1e-8)
    kwargs.setdefault("reltol", 1e-6)
    kwargs.setdefault("init_step_size", 1e-6)
    kwargs.setdefault("enable_full_state_output", True)
    kwargs.setdefault("max_krylov", 50)  # Enable GMRES

    return create_minimal_grm_config(
        output_path=output_path,
        **kwargs,
    )


def case_large_long_horizon(
    output_path: Union[str, Path],
    cadet_path: Union[str, Path] = None,
    **kwargs,
) -> Path:
    """Long time horizon case (time-dominated).

    **Scaling:**
    - NELEM: 32
    - n_comp: 2
    - end_time: 5000 (200 → 5000, 25× longer)
    - n_times: 501 (many outputs)

    **Expected:**
    - Wall time: 20-60 seconds
    - High NUM_STEPS (cumulative cost)

    Args:
        output_path: Path where HDF5 file will be written.
        cadet_path: Path to cadet-cli (not used, for compatibility).
        **kwargs: Additional arguments override defaults.

    Returns:
        Path to created HDF5 file.
    """
    kwargs.setdefault("n_col", 32)
    kwargs.setdefault("par_nelem", 4)
    kwargs.setdefault("n_comp", 2)
    kwargs.setdefault("end_time", 5000.0)
    kwargs.setdefault("n_times", 501)
    kwargs.setdefault("abstol", 1e-8)
    kwargs.setdefault("reltol", 1e-6)
    kwargs.setdefault("init_step_size", 1e-6)
    kwargs.setdefault("enable_full_state_output", True)
    kwargs.setdefault("max_krylov", 50)  # Enable GMRES

    return create_minimal_grm_config(
        output_path=output_path,
        **kwargs,
    )


def case_large_sharp_front_spatial_dg(
    output_path: Union[str, Path],
    cadet_path: Union[str, Path] = None,
    **kwargs,
) -> Path:
    """Same as case_large_sharp_front_spatial but using DG discretization.

    Uses ColumnModel1D with Eigen direct solver (no GMRES iterations).

    Args:
        output_path: Path where HDF5 file will be written.
        cadet_path: Path to cadet-cli (not used, for compatibility).
        **kwargs: Additional arguments override defaults.

    Returns:
        Path to created HDF5 file.
    """
    kwargs.setdefault("n_col", 64)
    kwargs.setdefault("par_nelem", 8)
    kwargs.setdefault("peclet", 5000.0)
    kwargs.setdefault("end_time", 200.0)
    kwargs.setdefault("n_times", 101)
    kwargs.setdefault("abstol", 3e-9)
    kwargs.setdefault("reltol", 1e-5)
    kwargs.setdefault("init_step_size", 1e-8)
    kwargs.setdefault("n_comp", 1)
    kwargs.setdefault("enable_full_state_output", True)
    kwargs.setdefault("spatial_method", "DG")  # Use DG instead of FV
    kwargs.setdefault("max_krylov", 0)  # DG doesn't use GMRES

    return create_minimal_grm_config(
        output_path=output_path,
        **kwargs,
    )


def case_xlarge_sharp_front_spatial_fv(
    output_path: Union[str, Path],
    cadet_path: Union[str, Path] = None,
    **kwargs,
) -> Path:
    """Extra-large FV case: 128 column elements, 16 particle cells.

    State dimension: ~10,240 DOFs (4× larger than large case)

    Args:
        output_path: Path where HDF5 file will be written.
        cadet_path: Path to cadet-cli (not used, for compatibility).
        **kwargs: Additional arguments override defaults.

    Returns:
        Path to created HDF5 file.
    """
    kwargs.setdefault("n_col", 128)  # 64 → 128 (2× increase)
    kwargs.setdefault("par_nelem", 16)  # 8 → 16 (2× increase)
    kwargs.setdefault("peclet", 5000.0)
    kwargs.setdefault("end_time", 200.0)
    kwargs.setdefault("n_times", 101)
    kwargs.setdefault("abstol", 3e-9)
    kwargs.setdefault("reltol", 1e-5)
    kwargs.setdefault("init_step_size", 1e-8)
    kwargs.setdefault("n_comp", 1)
    kwargs.setdefault("enable_full_state_output", True)
    kwargs.setdefault("spatial_method", "FV")  # Finite Volume
    kwargs.setdefault("max_krylov", 50)  # Enable GMRES

    return create_minimal_grm_config(
        output_path=output_path,
        **kwargs,
    )


def case_xlarge_sharp_front_spatial_dg(
    output_path: Union[str, Path],
    cadet_path: Union[str, Path] = None,
    **kwargs,
) -> Path:
    """Extra-large DG case: 128 column elements, 16 particle cells.

    State dimension: ~10,240 DOFs (4× larger than large case)

    Args:
        output_path: Path where HDF5 file will be written.
        cadet_path: Path to cadet-cli (not used, for compatibility).
        **kwargs: Additional arguments override defaults.

    Returns:
        Path to created HDF5 file.
    """
    kwargs.setdefault("n_col", 128)
    kwargs.setdefault("par_nelem", 16)
    kwargs.setdefault("peclet", 5000.0)
    kwargs.setdefault("end_time", 200.0)
    kwargs.setdefault("n_times", 101)
    kwargs.setdefault("abstol", 3e-9)
    kwargs.setdefault("reltol", 1e-5)
    kwargs.setdefault("init_step_size", 1e-8)
    kwargs.setdefault("n_comp", 1)
    kwargs.setdefault("enable_full_state_output", True)
    kwargs.setdefault("spatial_method", "DG")  # Discontinuous Galerkin
    kwargs.setdefault("max_krylov", 0)  # DG doesn't use GMRES

    return create_minimal_grm_config(
        output_path=output_path,
        **kwargs,
    )


def get_large_benchmark_suite():
    """Return list of large benchmark cases for Phase D.

    Returns:
        List of tuples (name, generator_func, default_kwargs).
    """
    return [
        # Original cases
        ("large_sharp_front_spatial", case_large_sharp_front_spatial,
         {"n_col": 64, "par_nelem": 8, "peclet": 5000.0}),
        ("medium_sharp_front_spatial", case_medium_sharp_front_spatial,
         {"n_col": 32, "par_nelem": 4, "peclet": 5000.0}),
        ("large_multicomp_stiff_binding", case_large_multicomp_stiff_binding,
         {"n_col": 32, "par_nelem": 4, "n_comp": 4}),
        ("large_long_horizon", case_large_long_horizon,
         {"n_col": 32, "par_nelem": 4, "end_time": 5000.0}),

        # Comparison cases: DG vs FV at same scale
        ("large_sharp_front_spatial_dg", case_large_sharp_front_spatial_dg,
         {"n_col": 64, "par_nelem": 8, "spatial_method": "DG"}),

        # Scaled-up cases: 128 elements
        ("xlarge_sharp_front_spatial_fv", case_xlarge_sharp_front_spatial_fv,
         {"n_col": 128, "par_nelem": 16, "spatial_method": "FV"}),
        ("xlarge_sharp_front_spatial_dg", case_xlarge_sharp_front_spatial_dg,
         {"n_col": 128, "par_nelem": 16, "spatial_method": "DG"}),
    ]
