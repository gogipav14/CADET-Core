"""Stress test case generators for CADET simulations.

This module provides functions to generate CADET configurations that are
intentionally challenging for the solver, useful for testing robustness.
"""

from pathlib import Path
from typing import Union
import numpy as np

from cadet_lab.config_gen.minimal_grm import create_minimal_grm_config, _write_string
import h5py


def case_first_step_fail(
    output_path: Union[str, Path],
    init_step_size: float = 1.0,  # Intentionally large
    **kwargs,
) -> Path:
    """Generate a case with intentionally large init_step_size.

    This configuration is designed to cause first-step failures by setting
    an unreasonably large initial step size. The solver should reject the
    first step(s) and recover by reducing step size.

    Args:
        output_path: Path where HDF5 file will be written.
        init_step_size: Initial step size (default 1.0, very large for stiff systems).
        **kwargs: Additional arguments passed to create_minimal_grm_config.

    Returns:
        Path to created HDF5 file.
    """
    # Use default values that make the problem reasonably stiff
    kwargs.setdefault("n_times", 21)
    kwargs.setdefault("end_time", 10.0)
    kwargs.setdefault("abstol", 1e-8)
    kwargs.setdefault("reltol", 1e-6)
    kwargs.setdefault("col_dispersion", 1e-8)  # Low dispersion -> stiffer
    kwargs.setdefault("velocity", 5e-4)
    kwargs.setdefault("binding_ka", 10.0)  # Faster binding -> stiffer
    kwargs.setdefault("binding_kd", 0.1)

    return create_minimal_grm_config(
        output_path=output_path,
        init_step_size=init_step_size,
        **kwargs,
    )


def case_sharp_front(
    output_path: Union[str, Path],
    peclet: float = 1000.0,
    n_col: int = 8,  # Coarse discretization
    **kwargs,
) -> Path:
    """Generate a case with a sharp concentration front.

    This configuration creates a high Peclet number (advection-dominated)
    system with coarse spatial discretization, leading to steep gradients
    that are challenging for the time integrator.

    Pe = v*L/D where:
        v = velocity
        L = column length
        D = dispersion coefficient

    Args:
        output_path: Path where HDF5 file will be written.
        peclet: Target Peclet number (default 1000, very advection-dominated).
        n_col: Number of column discretization cells (default 8, coarse).
        **kwargs: Additional arguments passed to create_minimal_grm_config.

    Returns:
        Path to created HDF5 file.
    """
    # Set parameters to achieve target Peclet number
    col_length = kwargs.get("col_length", 0.1)
    velocity = kwargs.get("velocity", 1e-3)
    col_dispersion = velocity * col_length / peclet

    kwargs.setdefault("n_times", 51)
    kwargs.setdefault("end_time", 200.0)  # Long enough to see breakthrough
    kwargs.setdefault("abstol", 1e-6)
    kwargs.setdefault("reltol", 1e-4)
    kwargs.setdefault("init_step_size", 1e-4)

    # Create base config
    output_path = create_minimal_grm_config(
        output_path=output_path,
        col_dispersion=col_dispersion,
        velocity=velocity,
        col_length=col_length,
        **kwargs,
    )

    # Modify discretization to be coarse
    with h5py.File(output_path, "r+") as f:
        disc = f["input/model/unit_001/discretization"]
        if "NELEM" in disc:
            del disc["NELEM"]
        disc.create_dataset("NELEM", data=n_col)

    return output_path


def case_discontinuous_section(
    output_path: Union[str, Path],
    pulse_duration: float = 1.0,
    concentration_ratio: float = 100.0,
    **kwargs,
) -> Path:
    """Generate a case with discontinuous inlet at section transition.

    This configuration has two sections:
    1. First section: High inlet concentration
    2. Second section: Near-zero inlet concentration

    The discontinuous transition tests the solver's ability to handle
    sudden changes in boundary conditions.

    Args:
        output_path: Path where HDF5 file will be written.
        pulse_duration: Duration of the first (high concentration) section.
        concentration_ratio: Ratio of high to low concentration.
        **kwargs: Additional arguments passed to create_minimal_grm_config.

    Returns:
        Path to created HDF5 file.
    """
    output_path = Path(output_path)
    end_time = kwargs.get("end_time", 10.0)
    n_times = kwargs.get("n_times", 51)
    n_comp = kwargs.get("n_comp", 1)

    # Generate solution times spanning both sections
    solution_times = np.linspace(0, end_time, n_times)

    kwargs.setdefault("abstol", 1e-8)
    kwargs.setdefault("reltol", 1e-6)
    kwargs.setdefault("init_step_size", 1e-6)

    high_conc = kwargs.pop("inlet_concentration", 1.0)
    low_conc = high_conc / concentration_ratio

    # Create base config with high concentration
    output_path = create_minimal_grm_config(
        output_path=output_path,
        n_times=n_times,
        end_time=end_time,
        inlet_concentration=high_conc,
        **kwargs,
    )

    # Modify to add second section with discontinuity
    with h5py.File(output_path, "r+") as f:
        # Update sections
        sections = f["input/solver/sections"]
        del sections["NSEC"]
        sections.create_dataset("NSEC", data=2)
        del sections["SECTION_TIMES"]
        sections.create_dataset("SECTION_TIMES", data=[0.0, pulse_duration, end_time])
        del sections["SECTION_CONTINUITY"]
        sections.create_dataset("SECTION_CONTINUITY", data=[0])  # Discontinuous!

        # Add second inlet section with low concentration
        unit_000 = f["input/model/unit_000"]
        sec_001 = unit_000.create_group("sec_001")
        sec_001.create_dataset("CONST_COEFF", data=[low_conc] * n_comp)
        sec_001.create_dataset("LIN_COEFF", data=[0.0] * n_comp)
        sec_001.create_dataset("QUAD_COEFF", data=[0.0] * n_comp)
        sec_001.create_dataset("CUBE_COEFF", data=[0.0] * n_comp)

    return output_path


def get_all_stress_cases() -> list:
    """Return list of all available stress case generators.

    Returns:
        List of tuples (name, generator_func, default_kwargs).
    """
    return [
        ("first_step_fail", case_first_step_fail, {"init_step_size": 1.0}),
        ("sharp_front", case_sharp_front, {"peclet": 1000.0, "n_col": 8}),
        ("discontinuous_section", case_discontinuous_section, {"pulse_duration": 1.0}),
    ]
