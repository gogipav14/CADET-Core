"""Generate minimal CADET GRM configurations for testing.

Creates HDF5 input files with INLET -> GENERAL_RATE_MODEL -> OUTLET structure.
Based on CADET-Python tutorial patterns.
"""

from pathlib import Path
from typing import Union, Optional
import numpy as np
import h5py


def create_minimal_grm_config(
    output_path: Union[str, Path],
    n_times: int = 11,
    end_time: float = 10.0,
    abstol: float = 1e-6,
    reltol: float = 1e-6,
    init_step_size: float = 1e-6,
    n_comp: int = 1,
    col_length: float = 0.1,
    col_porosity: float = 0.37,
    par_porosity: float = 0.33,
    par_radius: float = 1e-5,
    velocity: float = 1e-3,
    col_dispersion: float = 1e-7,
    film_diffusion: float = 1e-5,
    pore_diffusion: float = 1e-10,
    binding_ka: float = 1.0,
    binding_kd: float = 1.0,
    inlet_concentration: float = 1.0,
    enable_full_state_output: bool = False,
    n_col: int = 8,
    par_nelem: int = 1,
    peclet: Optional[float] = None,
    max_krylov: int = 0,
    max_restarts: int = 10,
    schur_safety: float = 1e-8,
    spatial_method: str = "FV",  # "FV" or "DG"
) -> Path:
    """Create a minimal CADET GRM configuration HDF5 file.

    Creates INLET -> GENERAL_RATE_MODEL -> OUTLET structure suitable for
    basic breakthrough simulations.

    Args:
        output_path: Path where HDF5 file will be written.
        n_times: Number of solution time points.
        end_time: Simulation end time in seconds.
        abstol: Absolute tolerance for time integrator.
        reltol: Relative tolerance for time integrator.
        init_step_size: Initial step size for time integrator.
        n_comp: Number of components.
        col_length: Column length in meters.
        col_porosity: Column (interstitial) porosity.
        par_porosity: Particle porosity.
        par_radius: Particle radius in meters.
        velocity: Interstitial velocity in m/s.
        col_dispersion: Axial dispersion coefficient in m^2/s.
        film_diffusion: Film diffusion coefficient in m/s.
        pore_diffusion: Pore diffusion coefficient in m^2/s.
        binding_ka: Adsorption rate constant.
        binding_kd: Desorption rate constant.
        inlet_concentration: Inlet concentration for step input.
        enable_full_state_output: Enable bulk, particle, solid, and coordinate output.
        n_col: Number of column discretization elements (NELEM).
        par_nelem: Number of particle discretization elements (PAR_NELEM).
        peclet: Peclet number (if provided, overrides col_dispersion calculation).

    Returns:
        Path to created HDF5 file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate solution times
    solution_times = np.linspace(0, end_time, n_times)

    # Calculate dispersion from Peclet number if provided
    if peclet is not None:
        # Pe = velocity * col_length / col_dispersion
        col_dispersion = velocity * col_length / peclet

    # Flow rate (arbitrary but consistent)
    flow_rate = velocity * col_porosity * 1e-4  # m^3/s for cross-section ~1e-4 m^2

    with h5py.File(output_path, "w") as f:
        # Create input group structure
        inp = f.create_group("input")
        model = inp.create_group("model")
        solver = inp.create_group("solver")
        ret = inp.create_group("return")

        # Number of units
        model.create_dataset("NUNITS", data=3)

        # ===== Unit 000: INLET =====
        unit_000 = model.create_group("unit_000")
        _write_string(unit_000, "UNIT_TYPE", "INLET")
        _write_string(unit_000, "INLET_TYPE", "PIECEWISE_CUBIC_POLY")
        unit_000.create_dataset("NCOMP", data=n_comp)

        # Inlet section 0: step input
        sec_000 = unit_000.create_group("sec_000")
        sec_000.create_dataset("CONST_COEFF", data=[inlet_concentration] * n_comp)
        sec_000.create_dataset("LIN_COEFF", data=[0.0] * n_comp)
        sec_000.create_dataset("QUAD_COEFF", data=[0.0] * n_comp)
        sec_000.create_dataset("CUBE_COEFF", data=[0.0] * n_comp)

        # ===== Unit 001: GENERAL_RATE_MODEL =====
        unit_001 = model.create_group("unit_001")
        _write_string(unit_001, "UNIT_TYPE", "GENERAL_RATE_MODEL")
        unit_001.create_dataset("NCOMP", data=n_comp)
        unit_001.create_dataset("NPARTYPE", data=1)

        # Geometry (column-level)
        unit_001.create_dataset("COL_LENGTH", data=col_length)
        unit_001.create_dataset("COL_POROSITY", data=col_porosity)
        unit_001.create_dataset("CROSS_SECTION_AREA", data=1e-4)  # m^2

        # Transport (column-level)
        unit_001.create_dataset("COL_DISPERSION", data=col_dispersion)
        unit_001.create_dataset("VELOCITY", data=velocity)

        # Initial conditions (column-level)
        unit_001.create_dataset("INIT_C", data=[0.0] * n_comp)
        unit_001.create_dataset("INIT_CS", data=[0.0] * n_comp)

        # Column discretization (CADET v6 format)
        disc = unit_001.create_group("discretization")
        _write_string(disc, "SPATIAL_METHOD", spatial_method)
        disc.create_dataset("USE_ANALYTIC_JACOBIAN", data=1)

        if spatial_method == "FV":
            # Finite Volume: uses NCOL, WENO reconstruction, GMRES for Schur complement
            disc.create_dataset("NCOL", data=n_col)
            _write_string(disc, "RECONSTRUCTION", "WENO")

            # GMRES solver parameters (in discretization group for FV)
            disc.create_dataset("GS_TYPE", data=1)  # 1 = GMRES
            disc.create_dataset("MAX_KRYLOV", data=max_krylov)
            disc.create_dataset("MAX_RESTARTS", data=max_restarts)
            disc.create_dataset("SCHUR_SAFETY", data=schur_safety)

            # WENO parameters (required for WENO reconstruction)
            weno = disc.create_group("weno")
            weno.create_dataset("BOUNDARY_MODEL", data=0)
            weno.create_dataset("WENO_EPS", data=1e-10)
            weno.create_dataset("WENO_ORDER", data=1)

        elif spatial_method == "DG":
            # Discontinuous Galerkin: uses NELEM, polynomial degree
            disc.create_dataset("NELEM", data=n_col)  # n_col used for element count
            disc.create_dataset("POLYDEG", data=3)  # 3rd order polynomial
            disc.create_dataset("EXACT_INTEGRATION", data=1)  # Exact integration

        else:
            raise ValueError(f"Unknown spatial_method: {spatial_method}. Must be 'FV' or 'DG'.")

        # ===== Particle type 0 (CADET v6 format) =====
        par_type_000 = unit_001.create_group("particle_type_000")
        _write_string(par_type_000, "PAR_GEOM", "SPHERE")
        par_type_000.create_dataset("PAR_POROSITY", data=par_porosity)
        par_type_000.create_dataset("PAR_RADIUS", data=par_radius)
        par_type_000.create_dataset("PAR_CORERADIUS", data=0.0)
        par_type_000.create_dataset("NBOUND", data=[1] * n_comp)

        # Transport in particle
        par_type_000.create_dataset("FILM_DIFFUSION", data=[film_diffusion] * n_comp)
        par_type_000.create_dataset("FILM_DIFFUSION_MULTIPLEX", data=0)
        par_type_000.create_dataset("PORE_DIFFUSION", data=[pore_diffusion] * n_comp)
        par_type_000.create_dataset("SURFACE_DIFFUSION", data=[0.0] * n_comp)
        par_type_000.create_dataset("HAS_FILM_DIFFUSION", data=1)
        par_type_000.create_dataset("HAS_PORE_DIFFUSION", data=1)
        par_type_000.create_dataset("HAS_SURFACE_DIFFUSION", data=0)

        # Adsorption (inside particle_type_000 for CADET v6)
        _write_string(par_type_000, "ADSORPTION_MODEL", "LINEAR")
        ads = par_type_000.create_group("adsorption")
        ads.create_dataset("IS_KINETIC", data=1)
        ads.create_dataset("LIN_KA", data=[binding_ka] * n_comp)
        ads.create_dataset("LIN_KD", data=[binding_kd] * n_comp)

        # Particle discretization (inside particle_type_000 for CADET v6)
        par_disc = par_type_000.create_group("discretization")

        if spatial_method == "FV":
            # Finite Volume particle discretization
            _write_string(par_disc, "PAR_DISC_TYPE", "EQUIDISTANT_PAR")
            par_disc.create_dataset("NCELLS", data=par_nelem)
            par_disc.create_dataset("SPATIAL_METHOD", data=0)  # 0 = FV
            par_disc.create_dataset("FV_BOUNDARY_ORDER", data=2)

        elif spatial_method == "DG":
            # Discontinuous Galerkin particle discretization
            _write_string(par_disc, "PAR_DISC_TYPE", "EQUIDISTANT")
            par_disc.create_dataset("PAR_NELEM", data=par_nelem)
            _write_string(par_disc, "SPATIAL_METHOD", "DG")
            par_disc.create_dataset("PAR_POLYDEG", data=3)

        # ===== Unit 002: OUTLET =====
        unit_002 = model.create_group("unit_002")
        _write_string(unit_002, "UNIT_TYPE", "OUTLET")
        unit_002.create_dataset("NCOMP", data=n_comp)

        # ===== Connections =====
        connections = model.create_group("connections")
        connections.create_dataset("NSWITCHES", data=1)

        switch_000 = connections.create_group("switch_000")
        switch_000.create_dataset("SECTION", data=0)
        # Connection format: [from_unit, to_unit, from_comp, to_comp, flow_rate, ...]
        switch_000.create_dataset("CONNECTIONS", data=[
            0, 1, -1, -1, flow_rate,  # Inlet -> GRM
            1, 2, -1, -1, flow_rate,  # GRM -> Outlet
        ])

        # ===== Model solver settings (system-level) =====
        model_solver = model.create_group("solver")
        model_solver.create_dataset("GS_TYPE", data=1)
        model_solver.create_dataset("MAX_KRYLOV", data=max_krylov)
        model_solver.create_dataset("MAX_RESTARTS", data=max_restarts)
        model_solver.create_dataset("SCHUR_SAFETY", data=schur_safety)

        # ===== Solver settings =====
        solver.create_dataset("NTHREADS", data=1)
        solver.create_dataset("USER_SOLUTION_TIMES", data=solution_times)

        # Sections
        sections = solver.create_group("sections")
        sections.create_dataset("NSEC", data=1)
        sections.create_dataset("SECTION_TIMES", data=[0.0, end_time])
        sections.create_dataset("SECTION_CONTINUITY", data=[])

        # Time integrator
        time_int = solver.create_group("time_integrator")
        time_int.create_dataset("ABSTOL", data=abstol)
        time_int.create_dataset("ALGTOL", data=1e-10)
        time_int.create_dataset("RELTOL", data=reltol)
        time_int.create_dataset("INIT_STEP_SIZE", data=init_step_size)
        time_int.create_dataset("MAX_STEPS", data=100000)

        # ===== Return settings =====
        ret.create_dataset("SPLIT_COMPONENTS_DATA", data=0)
        ret.create_dataset("SPLIT_PORTS_DATA", data=0)
        ret.create_dataset("WRITE_SOLVER_STATISTICS", data=1)  # Enable solver stats

        # Determine flags based on enable_full_state_output
        bulk_flag = 1 if enable_full_state_output else 0
        particle_flag = 1 if enable_full_state_output else 0
        solid_flag = 1 if enable_full_state_output else 0
        coordinates_flag = 1 if enable_full_state_output else 0

        for unit_name in ["unit_000", "unit_001", "unit_002"]:
            unit_ret = ret.create_group(unit_name)
            unit_ret.create_dataset("WRITE_SOLUTION_INLET", data=1)
            unit_ret.create_dataset("WRITE_SOLUTION_OUTLET", data=1)
            unit_ret.create_dataset("WRITE_SOLUTION_BULK", data=bulk_flag)
            unit_ret.create_dataset("WRITE_SOLUTION_PARTICLE", data=particle_flag)
            unit_ret.create_dataset("WRITE_SOLUTION_SOLID", data=solid_flag)
            unit_ret.create_dataset("WRITE_SOLUTION_FLUX", data=0)
            unit_ret.create_dataset("WRITE_SOLUTION_VOLUME", data=0)
            unit_ret.create_dataset("WRITE_COORDINATES", data=coordinates_flag)
            unit_ret.create_dataset("WRITE_SENS_OUTLET", data=0)

    return output_path


def _write_string(group: h5py.Group, name: str, value: str) -> None:
    """Write a string dataset to HDF5 group.

    Uses fixed-length ASCII encoding for CADET compatibility.
    """
    dt = h5py.string_dtype(encoding='ascii')
    group.create_dataset(name, data=value, dtype=dt)


def create_pulse_injection_config(
    output_path: Union[str, Path],
    pulse_duration: float = 1.0,
    **kwargs,
) -> Path:
    """Create a config with pulse injection (step on, then off).

    Creates two sections: first with inlet concentration, second with zero.

    Args:
        output_path: Path where HDF5 file will be written.
        pulse_duration: Duration of the injection pulse in seconds.
        **kwargs: Additional arguments passed to create_minimal_grm_config.

    Returns:
        Path to created HDF5 file.
    """
    # First create basic config
    end_time = kwargs.get("end_time", 10.0)
    n_times = kwargs.get("n_times", 11)
    inlet_concentration = kwargs.pop("inlet_concentration", 1.0)

    output_path = create_minimal_grm_config(
        output_path=output_path,
        inlet_concentration=inlet_concentration,
        **kwargs,
    )

    # Modify to add second section
    with h5py.File(output_path, "r+") as f:
        # Update sections
        sections = f["input/solver/sections"]
        del sections["NSEC"]
        sections.create_dataset("NSEC", data=2)
        del sections["SECTION_TIMES"]
        sections.create_dataset("SECTION_TIMES", data=[0.0, pulse_duration, end_time])
        del sections["SECTION_CONTINUITY"]
        sections.create_dataset("SECTION_CONTINUITY", data=[0])  # Discontinuous

        # Add second inlet section with zero concentration
        n_comp = f["input/model/unit_000/NCOMP"][()]
        unit_000 = f["input/model/unit_000"]

        sec_001 = unit_000.create_group("sec_001")
        sec_001.create_dataset("CONST_COEFF", data=[0.0] * n_comp)
        sec_001.create_dataset("LIN_COEFF", data=[0.0] * n_comp)
        sec_001.create_dataset("QUAD_COEFF", data=[0.0] * n_comp)
        sec_001.create_dataset("CUBE_COEFF", data=[0.0] * n_comp)

    return output_path
