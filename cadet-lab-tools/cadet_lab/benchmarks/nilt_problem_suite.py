"""Linear problem suite for NILT vs CADET benchmarking (Phase D Track 1).

Defines 6 linear problems suitable for NILT acceleration:
- P1: linear_transport_low_pe (Peclet=10, baseline)
- P2: linear_transport_high_pe (Peclet=1000, sharp front)
- P3: linear_langmuir_dilute (LINEAR binding)
- P7: pulse_injection_linear (temporal dynamics)
- P9: graded_dispersion (variable parameters)
- P10: stiff_kinetics_linear (fast binding)

Each problem provides:
1. CADET config generator (using minimal_grm)
2. Matching transfer function for NILT
3. Problem registration in global registry
"""

from pathlib import Path
from typing import Union, Callable
import numpy as np

from cadet_lab.config_gen.minimal_grm import create_minimal_grm_config
from cadet_lab.nilt.benchmarks import (
    advection_dispersion_transfer,
    langmuir_column_transfer,
    grm_langmuir_transfer,
)
from cadet_lab.benchmarks.problem_registry import (
    ProblemDefinition,
    ProblemCategory,
    Discretization,
    register_problem,
)


# =============================================================================
# P1: Linear Transport (Low Peclet)
# =============================================================================

def create_p1_linear_transport_low_pe(
    output_path: Union[str, Path],
    n_col: int = 8,
    n_par: int = 4,
    n_times: int = 201,
    end_time: float = 100.0,
    **kwargs,
) -> Path:
    """Generate P1: Linear transport with low Peclet number (Pe=10).

    Baseline advection-dispersion case with moderate Peclet number.

    Uses very fast film and pore diffusion to approximate instant equilibrium
    (no particle mass transfer resistance), matching the NILT advection-dispersion
    transfer function.
    """
    # Peclet = 10 (moderate advection/dispersion balance)
    velocity = 1e-3  # m/s
    col_length = 0.1  # m
    col_dispersion = velocity * col_length / 10.0  # Pe = 10

    return create_minimal_grm_config(
        output_path=output_path,
        velocity=velocity,
        col_length=col_length,
        col_dispersion=col_dispersion,
        binding_ka=0.0,  # No binding (linear transport only)
        binding_kd=1.0,
        # Fast diffusion for instant equilibrium (no particle resistance)
        film_diffusion=1.0,  # Very fast (1 m/s >> characteristic velocity)
        pore_diffusion=1e-4,  # Very fast (1e-4 m²/s >> default 1e-10)
        par_radius=1e-7,  # Very small particles (minimize retardation without stiffness)
        par_porosity=0.999,  # Very high porosity (minimize solid phase volume)
        n_times=n_times,
        end_time=end_time,
        n_col=n_col,
        par_nelem=n_par,
        **kwargs,
    )


def get_p1_transfer_function() -> Callable:
    """Get transfer function for P1."""
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = velocity * col_length / 10.0  # Pe = 10

    return advection_dispersion_transfer(
        velocity=velocity,
        dispersion=col_dispersion,
        length=col_length,
    )


# Register P1
register_problem(ProblemDefinition(
    id="P1_linear_transport_low_pe",
    name="Linear Transport (Low Peclet)",
    description="Baseline advection-dispersion with Pe=10 (moderate)",
    categories=[ProblemCategory.LINEAR, ProblemCategory.TRANSPORT],
    generator=create_p1_linear_transport_low_pe,
    default_params={
        "n_col": 8,
        "n_par": 4,
        "n_times": 201,
        "end_time": 100.0,
    },
    discretization=Discretization.FV,
    is_linear=True,
    supports_nilt=True,
    reference_peclet=10.0,
))


# =============================================================================
# P2: Linear Transport (High Peclet)
# =============================================================================

def create_p2_linear_transport_high_pe(
    output_path: Union[str, Path],
    n_col: int = 8,
    n_par: int = 4,
    n_times: int = 201,
    end_time: float = 200.0,
    **kwargs,
) -> Path:
    """Generate P2: Linear transport with high Peclet number (Pe=1000).

    Sharp front case with advection-dominated transport.

    Uses very fast film and pore diffusion to approximate instant equilibrium
    (no particle mass transfer resistance), matching the NILT advection-dispersion
    transfer function.
    """
    # Peclet = 1000 (highly advection-dominated)
    velocity = 1e-3  # m/s
    col_length = 0.1  # m
    col_dispersion = velocity * col_length / 1000.0  # Pe = 1000

    return create_minimal_grm_config(
        output_path=output_path,
        velocity=velocity,
        col_length=col_length,
        col_dispersion=col_dispersion,
        binding_ka=0.0,  # No binding
        binding_kd=1.0,
        # Fast diffusion for instant equilibrium (no particle resistance)
        film_diffusion=1.0,
        pore_diffusion=1e-4,
        par_radius=1e-7,  # Very small particles (minimize retardation without stiffness)
        par_porosity=0.999,  # Very high porosity (minimize solid phase volume)
        n_times=n_times,
        end_time=end_time,
        n_col=n_col,
        par_nelem=n_par,
        **kwargs,
    )


def get_p2_transfer_function() -> Callable:
    """Get transfer function for P2."""
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = velocity * col_length / 1000.0  # Pe = 1000

    return advection_dispersion_transfer(
        velocity=velocity,
        dispersion=col_dispersion,
        length=col_length,
    )


# Register P2
register_problem(ProblemDefinition(
    id="P2_linear_transport_high_pe",
    name="Linear Transport (High Peclet)",
    description="Sharp front with Pe=1000 (advection-dominated)",
    categories=[ProblemCategory.LINEAR, ProblemCategory.TRANSPORT],
    generator=create_p2_linear_transport_high_pe,
    default_params={
        "n_col": 8,
        "n_par": 4,
        "n_times": 201,
        "end_time": 200.0,
    },
    discretization=Discretization.FV,
    is_linear=True,
    supports_nilt=True,
    reference_peclet=1000.0,
))


# =============================================================================
# P3: Linear Langmuir (Dilute Conditions)
# =============================================================================

def create_p3_linear_langmuir_dilute(
    output_path: Union[str, Path],
    n_col: int = 8,
    n_par: int = 4,
    n_times: int = 201,
    end_time: float = 100.0,
    **kwargs,
) -> Path:
    """Generate P3: Linear Langmuir with dilute conditions.

    Langmuir binding in linear regime (low inlet concentration).

    Uses grm_langmuir_transfer() which accounts for full GRM physics:
    particle dynamics, film/pore diffusion, and kinetic binding.
    """
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = 1e-6

    # Linear binding (dilute conditions)
    binding_ka = 1.0
    binding_kd = 0.1

    return create_minimal_grm_config(
        output_path=output_path,
        velocity=velocity,
        col_length=col_length,
        col_dispersion=col_dispersion,
        # Linear binding (use ka/kd parameters)
        binding_ka=binding_ka,
        binding_kd=binding_kd,
        inlet_concentration=1e-6,  # Very dilute (ensures linearity)
        # Realistic particle parameters (GRM transfer function accounts for these)
        film_diffusion=1e-4,   # Realistic (not instant)
        pore_diffusion=1e-9,   # Realistic (not instant)
        par_radius=1e-5,       # Realistic particle size
        par_porosity=0.33,     # Standard particle porosity
        n_times=n_times,
        end_time=end_time,
        n_col=n_col,
        par_nelem=n_par,
        **kwargs,
    )


def get_p3_transfer_function() -> Callable:
    """Get transfer function for P3.

    Uses full GRM with kinetic binding and realistic particle dynamics.
    """
    # Transport parameters
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = 1e-6

    # Realistic particle parameters (match CADET config)
    col_porosity = 0.37  # Default CADET column porosity
    par_radius = 1e-5     # Realistic particle size
    par_porosity = 0.33   # Standard particle porosity
    film_diffusion = 1e-4 # Realistic film mass transfer
    pore_diffusion = 1e-9 # Realistic pore diffusion

    # Binding parameters
    binding_ka = 1.0
    binding_kd = 0.1
    qmax = 100.0  # Large qmax for linear regime

    return grm_langmuir_transfer(
        velocity=velocity,
        dispersion=col_dispersion,
        length=col_length,
        col_porosity=col_porosity,
        par_radius=par_radius,
        par_porosity=par_porosity,
        film_diffusion=film_diffusion,
        pore_diffusion=pore_diffusion,
        ka=binding_ka,
        kd=binding_kd,
        qmax=qmax,
    )


# Register P3
register_problem(ProblemDefinition(
    id="P3_linear_langmuir_dilute",
    name="Linear Langmuir (Dilute)",
    description="Langmuir binding in linear regime (dilute conditions)",
    categories=[ProblemCategory.LINEAR, ProblemCategory.BINDING],
    generator=create_p3_linear_langmuir_dilute,
    default_params={
        "n_col": 8,
        "n_par": 4,
        "n_times": 201,
        "end_time": 100.0,
    },
    discretization=Discretization.FV,
    is_linear=True,
    supports_nilt=True,
    reference_peclet=100.0,
    reference_ka=1.0,
))


# =============================================================================
# P7: Pulse Injection (Linear Transport)
# =============================================================================

def create_p7_pulse_injection_linear(
    output_path: Union[str, Path],
    n_col: int = 8,
    n_par: int = 4,
    n_times: int = 201,
    end_time: float = 100.0,
    pulse_duration: float = 10.0,
    **kwargs,
) -> Path:
    """Generate P7: Pulse injection with linear transport.

    Temporal dynamics test with finite pulse injection.

    Uses very fast film and pore diffusion to approximate instant equilibrium
    (no particle mass transfer resistance), matching the NILT advection-dispersion
    transfer function.
    """
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = 1e-6

    # TODO: Implement pulse injection via inlet sections
    # For now, use step injection (can extend with multi-section later)
    return create_minimal_grm_config(
        output_path=output_path,
        velocity=velocity,
        col_length=col_length,
        col_dispersion=col_dispersion,
        binding_ka=0.0,  # No binding
        binding_kd=1.0,
        # Fast diffusion for instant equilibrium (no particle resistance)
        film_diffusion=1.0,
        pore_diffusion=1e-4,
        par_radius=1e-7,  # Very small particles (minimize retardation without stiffness)
        par_porosity=0.999,  # Very high porosity (minimize solid phase volume)
        n_times=n_times,
        end_time=end_time,
        n_col=n_col,
        par_nelem=n_par,
        **kwargs,
    )


def get_p7_transfer_function() -> Callable:
    """Get transfer function for P7."""
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = 1e-6

    # For step injection, use advection-dispersion
    # Pulse response = step response * (pulse shape in Laplace domain)
    return advection_dispersion_transfer(
        velocity=velocity,
        dispersion=col_dispersion,
        length=col_length,
    )


# Register P7
register_problem(ProblemDefinition(
    id="P7_pulse_injection_linear",
    name="Pulse Injection (Linear)",
    description="Temporal dynamics with finite pulse injection",
    categories=[ProblemCategory.LINEAR, ProblemCategory.TRANSPORT],
    generator=create_p7_pulse_injection_linear,
    default_params={
        "n_col": 8,
        "n_par": 4,
        "n_times": 201,
        "end_time": 100.0,
        "pulse_duration": 10.0,
    },
    discretization=Discretization.FV,
    is_linear=True,
    supports_nilt=True,
    reference_peclet=100.0,
))


# =============================================================================
# P9: Graded Dispersion (Variable Parameters)
# =============================================================================

def create_p9_graded_dispersion(
    output_path: Union[str, Path],
    n_col: int = 8,
    n_par: int = 4,
    n_times: int = 201,
    end_time: float = 100.0,
    **kwargs,
) -> Path:
    """Generate P9: Graded dispersion coefficient.

    Variable dispersion coefficient along column axis.
    Note: CADET may not support spatially varying dispersion directly,
    so this is approximated with average value.

    Uses very fast film and pore diffusion to approximate instant equilibrium
    (no particle mass transfer resistance), matching the NILT advection-dispersion
    transfer function.
    """
    velocity = 1e-3
    col_length = 0.1
    # Average dispersion (graded from 5e-7 to 1.5e-6)
    col_dispersion = (5e-7 + 1.5e-6) / 2.0

    return create_minimal_grm_config(
        output_path=output_path,
        velocity=velocity,
        col_length=col_length,
        col_dispersion=col_dispersion,
        binding_ka=0.0,  # No binding
        binding_kd=1.0,
        # Fast diffusion for instant equilibrium (no particle resistance)
        film_diffusion=1.0,
        pore_diffusion=1e-4,
        par_radius=1e-7,  # Very small particles (minimize retardation without stiffness)
        par_porosity=0.999,  # Very high porosity (minimize solid phase volume)
        n_times=n_times,
        end_time=end_time,
        n_col=n_col,
        par_nelem=n_par,
        **kwargs,
    )


def get_p9_transfer_function() -> Callable:
    """Get transfer function for P9."""
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = (5e-7 + 1.5e-6) / 2.0  # Average

    return advection_dispersion_transfer(
        velocity=velocity,
        dispersion=col_dispersion,
        length=col_length,
    )


# Register P9
register_problem(ProblemDefinition(
    id="P9_graded_dispersion",
    name="Graded Dispersion",
    description="Variable dispersion coefficient (averaged for comparison)",
    categories=[ProblemCategory.LINEAR, ProblemCategory.TRANSPORT],
    generator=create_p9_graded_dispersion,
    default_params={
        "n_col": 8,
        "n_par": 4,
        "n_times": 201,
        "end_time": 100.0,
    },
    discretization=Discretization.FV,
    is_linear=True,
    supports_nilt=True,
    reference_peclet=100.0,
))


# =============================================================================
# P10: Stiff Kinetics (Fast Linear Binding)
# =============================================================================

def create_p10_stiff_kinetics_linear(
    output_path: Union[str, Path],
    n_col: int = 8,
    n_par: int = 4,
    n_times: int = 201,
    end_time: float = 100.0,
    **kwargs,
) -> Path:
    """Generate P10: Stiff kinetics with fast linear binding.

    Fast binding/unbinding rates create temporal stiffness.

    Uses grm_langmuir_transfer() which accounts for full GRM physics:
    particle dynamics, film/pore diffusion, and fast kinetic binding.
    """
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = 1e-6

    # Fast kinetics (stiff system)
    binding_ka = 100.0  # Fast adsorption
    binding_kd = 10.0   # Fast desorption

    return create_minimal_grm_config(
        output_path=output_path,
        velocity=velocity,
        col_length=col_length,
        col_dispersion=col_dispersion,
        # Linear binding (use ka/kd parameters)
        binding_ka=binding_ka,
        binding_kd=binding_kd,
        inlet_concentration=1e-6,  # Dilute
        # Realistic particle parameters (GRM transfer function accounts for these)
        film_diffusion=1e-4,   # Realistic (not instant)
        pore_diffusion=1e-9,   # Realistic (not instant)
        par_radius=1e-5,       # Realistic particle size
        par_porosity=0.33,     # Standard particle porosity
        n_times=n_times,
        end_time=end_time,
        n_col=n_col,
        par_nelem=n_par,
        **kwargs,
    )


def get_p10_transfer_function() -> Callable:
    """Get transfer function for P10.

    Uses full GRM with fast kinetic binding and realistic particle dynamics.
    """
    # Transport parameters
    velocity = 1e-3
    col_length = 0.1
    col_dispersion = 1e-6

    # Realistic particle parameters (match CADET config)
    col_porosity = 0.37  # Default CADET column porosity
    par_radius = 1e-5     # Realistic particle size
    par_porosity = 0.33   # Standard particle porosity
    film_diffusion = 1e-4 # Realistic film mass transfer
    pore_diffusion = 1e-9 # Realistic pore diffusion

    # Fast binding kinetics (stiff system)
    binding_ka = 100.0
    binding_kd = 10.0
    qmax = 100.0

    return grm_langmuir_transfer(
        velocity=velocity,
        dispersion=col_dispersion,
        length=col_length,
        col_porosity=col_porosity,
        par_radius=par_radius,
        par_porosity=par_porosity,
        film_diffusion=film_diffusion,
        pore_diffusion=pore_diffusion,
        ka=binding_ka,
        kd=binding_kd,
        qmax=qmax,
    )


# Register P10
register_problem(ProblemDefinition(
    id="P10_stiff_kinetics_linear",
    name="Stiff Kinetics (Linear)",
    description="Fast linear binding creates temporal stiffness",
    categories=[ProblemCategory.LINEAR, ProblemCategory.BINDING],
    generator=create_p10_stiff_kinetics_linear,
    default_params={
        "n_col": 8,
        "n_par": 4,
        "n_times": 201,
        "end_time": 100.0,
    },
    discretization=Discretization.FV,
    is_linear=True,
    supports_nilt=True,
    reference_peclet=100.0,
    reference_ka=100.0,
))


# =============================================================================
# Utility Functions
# =============================================================================

def get_all_linear_problems():
    """Get all registered linear problems.

    Returns:
        List of problem IDs.
    """
    return [
        "P1_linear_transport_low_pe",
        "P2_linear_transport_high_pe",
        "P3_linear_langmuir_dilute",
        "P7_pulse_injection_linear",
        "P9_graded_dispersion",
        "P10_stiff_kinetics_linear",
    ]


def get_transfer_function_for_problem(problem_id: str) -> Callable:
    """Get transfer function for a given problem ID.

    Args:
        problem_id: Problem identifier.

    Returns:
        Transfer function callable.

    Raises:
        ValueError: If problem ID not recognized.
    """
    transfer_funcs = {
        "P1_linear_transport_low_pe": get_p1_transfer_function,
        "P2_linear_transport_high_pe": get_p2_transfer_function,
        "P3_linear_langmuir_dilute": get_p3_transfer_function,
        "P7_pulse_injection_linear": get_p7_transfer_function,
        "P9_graded_dispersion": get_p9_transfer_function,
        "P10_stiff_kinetics_linear": get_p10_transfer_function,
    }

    if problem_id not in transfer_funcs:
        raise ValueError(f"Unknown problem ID: {problem_id}")

    return transfer_funcs[problem_id]()
