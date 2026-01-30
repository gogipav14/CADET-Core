"""CADET-specific benchmark transfer functions for NILT verification.

Provides analytical Laplace-domain transfer functions relevant to
chromatography, packed-bed reactors, and dispersion processes.
"""

from typing import Callable, List, Tuple, Optional
import numpy as np
import cmath

from .vendor import Problem


def advection_dispersion_transfer(
    velocity: float = 1e-3,
    dispersion: float = 1e-6,
    length: float = 0.1,
) -> Callable[[complex], complex]:
    """Advection-dispersion equation transfer function.

    For a column with Danckwerts boundary conditions,
    the outlet concentration transfer function is:

    F(s) = exp(Pe/2 * (1 - sqrt(1 + 4*s*tau/Pe)))

    where:
        Pe = v*L/D (Peclet number)
        tau = L/v (residence time)

    This is equivalent to the packed_bed problem from nilt-cfl
    with appropriate parameter mapping.

    Args:
        velocity: Interstitial velocity [m/s].
        dispersion: Axial dispersion coefficient [m²/s].
        length: Column length [m].

    Returns:
        Callable F(s) for the transfer function.
    """
    Pe = velocity * length / dispersion  # Peclet number
    tau = length / velocity  # Residence time

    def F(s: complex) -> complex:
        # Dimensionless time constant
        inner = 1 + 4 * s * tau / Pe
        return cmath.exp(Pe / 2 * (1 - cmath.sqrt(inner)))

    return F


def langmuir_column_transfer(
    velocity: float = 1e-3,
    dispersion: float = 1e-6,
    length: float = 0.1,
    ka: float = 1.0,
    kd: float = 0.1,
    qmax: float = 10.0,
    porosity: float = 0.4,
) -> Callable[[complex], complex]:
    """Linearized Langmuir column transfer function.

    For linear (dilute) conditions, the Langmuir model can be linearized
    to give an effective retardation factor. The transfer function
    combines advection-dispersion with sorption dynamics.

    Args:
        velocity: Interstitial velocity [m/s].
        dispersion: Axial dispersion coefficient [m²/s].
        length: Column length [m].
        ka: Adsorption rate constant [1/(mol·s)].
        kd: Desorption rate constant [1/s].
        qmax: Maximum binding capacity [mol/m³].
        porosity: Column porosity [-].

    Returns:
        Callable F(s) for the transfer function.
    """
    # Phase ratio
    phase_ratio = (1.0 - porosity) / porosity

    # Linear partition coefficient (Henry constant)
    K_eq = ka * qmax / kd

    # Retardation factor
    R = 1.0 + phase_ratio * K_eq

    # Effective Peclet number (accounting for retardation)
    Pe_eff = velocity * length / (dispersion * R)

    # Effective residence time
    tau_eff = R * length / velocity

    # Sorption time scale
    tau_sorp = 1.0 / kd

    def F(s: complex) -> complex:
        # Transport part (advection-dispersion with retardation)
        inner = 1 + 4 * s * tau_eff / Pe_eff
        transport = cmath.exp(Pe_eff / 2 * (1 - cmath.sqrt(inner)))

        # Kinetic correction (low-pass filter for finite sorption rate)
        kinetic = 1.0 / (1.0 + s * tau_sorp / R)

        return transport * kinetic

    return F


def grm_moment_transfer(
    velocity: float = 1e-3,
    dispersion: float = 1e-6,
    length: float = 0.1,
    particle_radius: float = 5e-5,
    film_diffusion: float = 1e-5,
    pore_diffusion: float = 1e-10,
    porosity_column: float = 0.4,
    porosity_particle: float = 0.5,
) -> Callable[[complex], complex]:
    """General Rate Model (GRM) transfer function (moment-based approximation).

    This approximates the GRM outlet response using a moment-matching
    approach. The GRM accounts for:
    - Axial dispersion in interstitial volume
    - Film mass transfer at particle surface
    - Pore diffusion within particles

    Args:
        velocity: Interstitial velocity [m/s].
        dispersion: Axial dispersion coefficient [m²/s].
        length: Column length [m].
        particle_radius: Particle radius [m].
        film_diffusion: Film mass transfer coefficient [m/s].
        pore_diffusion: Pore diffusion coefficient [m²/s].
        porosity_column: Column (interstitial) porosity [-].
        porosity_particle: Particle porosity [-].

    Returns:
        Callable F(s) for the transfer function.
    """
    # Dimensionless groups
    Pe = velocity * length / dispersion

    # Particle time constant
    tau_p = particle_radius**2 / (15 * pore_diffusion)

    # Phase ratio
    phi = (1 - porosity_column) / porosity_column * porosity_particle

    # Residence time
    tau_col = length / velocity

    # Effective parameters for approximate transfer function
    n_eff = max(Pe / 2, 1)  # Effective number of stages

    def F(s: complex) -> complex:
        # Column dispersion (TIS approximation)
        col_term = 1.0 / (1.0 + s * tau_col / n_eff) ** n_eff

        # Particle dynamics (LDF approximation)
        particle_term = 1.0 / (1.0 + s * tau_p * (1 + phi))

        # Film resistance
        tau_film = particle_radius / (3 * film_diffusion)
        film_term = 1.0 / (1.0 + s * tau_film)

        return col_term * particle_term * film_term

    return F


def get_benchmark_functions() -> List[Tuple[str, Callable, Tuple[float, float], bool, float]]:
    """Get list of all benchmark transfer functions for NILT verification.

    Returns:
        List of tuples: (name, F, (t_min, t_max), has_analytical_solution, alpha_c)
    """
    return [
        (
            "advection_dispersion_Pe100",
            advection_dispersion_transfer(velocity=1e-3, dispersion=1e-6, length=0.1),
            (1.0, 500.0),
            False,  # No simple closed-form
            0.0,  # alpha_c
        ),
        (
            "advection_dispersion_Pe10",
            advection_dispersion_transfer(velocity=1e-3, dispersion=1e-5, length=0.1),
            (1.0, 500.0),
            False,
            0.0,
        ),
        (
            "langmuir_linear",
            langmuir_column_transfer(
                velocity=1e-3,
                dispersion=1e-6,
                length=0.1,
                ka=1.0,
                kd=0.1,
                qmax=10.0,
            ),
            (1.0, 1000.0),
            False,
            0.0,
        ),
        (
            "grm_moment_approx",
            grm_moment_transfer(
                velocity=1e-3,
                dispersion=1e-6,
                length=0.1,
                particle_radius=5e-5,
                film_diffusion=1e-5,
                pore_diffusion=1e-10,
            ),
            (1.0, 500.0),
            False,
            0.0,
        ),
    ]


def create_benchmark_problem(
    name: str,
    F: Callable[[complex], complex],
    alpha_c: float = 0.0,
    C: float = 1.0,
    rho: Optional[float] = None,
    description: str = "",
) -> Problem:
    """Create a Problem object for a custom benchmark.

    Args:
        name: Problem name.
        F: Transfer function.
        alpha_c: Abscissa of convergence.
        C: Tail envelope constant.
        rho: Spectral radius (optional).
        description: Problem description.

    Returns:
        Problem object compatible with nilt-cfl.
    """
    return Problem(
        name=name,
        F=F,
        f_ref=None,
        alpha_c=alpha_c,
        C=C,
        rho=rho,
        description=description,
    )
