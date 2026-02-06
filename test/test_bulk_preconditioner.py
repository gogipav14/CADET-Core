#!/usr/bin/env python3
"""
Test suite for Danckwerts bulk preconditioner (Part A - Track 2b)

Validates:
1. Correctness: Solution equivalence with/without preconditioner
2. Performance: Timing and iteration count impact
3. Stability: No NaNs, no solver failures
"""

import numpy as np
import h5py
import subprocess
import sys
from pathlib import Path

def create_grm_test_case(filename, use_precond=False, ncol=64, npar=4, ncomp=1, peclet=100):
    """
    Create a GRM test case with Danckwerts BCs

    Parameters:
    - use_precond: Enable Danckwerts bulk preconditioner
    - ncol: Number of axial cells
    - npar: Number of particle cells
    - ncomp: Number of components
    - peclet: Peclet number (Pe = vL/D)
    """

    # Derived parameters
    col_length = 0.1  # 10 cm column
    velocity = 1e-3   # 1 mm/s
    col_dispersion = velocity * col_length / peclet  # D = vL/Pe

    print(f"Creating test case: {filename}")
    print(f"  NCOL={ncol}, NPAR={npar}, NCOMP={ncomp}")
    print(f"  Pe={peclet}, v={velocity} m/s, D={col_dispersion} m²/s")
    print(f"  Preconditioner: {'ENABLED' if use_precond else 'DISABLED'}")

    with h5py.File(filename, 'w') as f:
        # Root attributes
        f.attrs['cadetVersion'] = 'CADET-Core Phase D Track 2b Test'
        f.attrs['fileFormat'] = 100

        # Input group
        inp = f.create_group('input')

        # Model
        model = inp.create_group('model')
        model.create_dataset('NUNITS', data=3)  # Inlet, Column, Outlet

        # Solver settings
        solver = inp.create_group('solver')

        # Time sections (single section)
        solver.create_dataset('USER_SOLUTION_TIMES', data=np.linspace(0, 1000, 101))
        solver.create_dataset('NTHREADS', data=1)

        # Sections
        sections = solver.create_group('sections')
        sections.create_dataset('NSEC', data=1)
        sections.create_dataset('SECTION_TIMES', data=[0.0, 1000.0])
        sections.create_dataset('SECTION_CONTINUITY', data=[0])

        # Time integrator
        time_integrator = solver.create_group('time_integrator')
        time_integrator.create_dataset('ABSTOL', data=1e-8)
        time_integrator.create_dataset('RELTOL', data=1e-6)
        time_integrator.create_dataset('ALGTOL', data=1e-12)
        time_integrator.create_dataset('INIT_STEP_SIZE', data=1e-6)
        time_integrator.create_dataset('MAX_STEPS', data=100000)

        # ==== UNIT 000: INLET ====
        unit_000 = model.create_group('unit_000')
        unit_000.create_dataset('UNIT_TYPE', data=b'INLET')
        unit_000.create_dataset('NCOMP', data=ncomp)
        unit_000.create_dataset('INLET_TYPE', data=b'PIECEWISE_CUBIC_POLY')

        # Inlet profile (pulse injection)
        sec_000 = unit_000.create_group('sec_000')
        sec_000.create_dataset('CONST_COEFF', data=[1.0] * ncomp)
        sec_000.create_dataset('LIN_COEFF', data=[0.0] * ncomp)
        sec_000.create_dataset('QUAD_COEFF', data=[0.0] * ncomp)
        sec_000.create_dataset('CUBE_COEFF', data=[0.0] * ncomp)

        # ==== UNIT 001: GENERAL RATE MODEL (GRM) ====
        unit_001 = model.create_group('unit_001')
        unit_001.create_dataset('UNIT_TYPE', data=b'GENERAL_RATE_MODEL')
        unit_001.create_dataset('NCOMP', data=ncomp)

        # Column geometry
        unit_001.create_dataset('COL_LENGTH', data=col_length)
        unit_001.create_dataset('COL_POROSITY', data=0.37)
        unit_001.create_dataset('PAR_POROSITY', data=0.75)
        unit_001.create_dataset('PAR_RADIUS', data=4.5e-5)

        # Transport parameters
        unit_001.create_dataset('COL_DISPERSION', data=[col_dispersion] * ncomp)
        unit_001.create_dataset('FILM_DIFFUSION', data=[6.9e-6] * ncomp)
        unit_001.create_dataset('PAR_DIFFUSION', data=[7e-10] * ncomp)
        unit_001.create_dataset('PAR_SURFDIFFUSION', data=[0.0] * ncomp)

        # Velocity (constant)
        unit_001.create_dataset('VELOCITY', data=velocity)

        # Discretization
        discretization = unit_001.create_group('discretization')
        discretization.create_dataset('NCOL', data=ncol)
        discretization.create_dataset('NPAR', data=npar)
        discretization.create_dataset('NBOUND', data=[1] * ncomp)
        discretization.create_dataset('PAR_DISC_TYPE', data=b'EQUIDISTANT_PAR')
        discretization.create_dataset('SPATIAL_METHOD', data=b'FV')  # Finite volume (required field)

        # Boundary model (Danckwerts)
        discretization.create_dataset('USE_ANALYTIC_JACOBIAN', data=1)
        discretization.create_dataset('MAX_KRYLOV', data=0)  # Use default
        discretization.create_dataset('GS_TYPE', data=1)     # Modified Gram-Schmidt
        discretization.create_dataset('MAX_RESTARTS', data=10)
        discretization.create_dataset('SCHUR_SAFETY', data=1e-8)

        # **PART A: Danckwerts bulk preconditioner configuration**
        discretization.create_dataset('USE_DANCKWERTS_BULK_PRECOND', data=1 if use_precond else 0)
        if use_precond:
            discretization.create_dataset('DANCKWERTS_BULK_PRECOND_MODES', data=min(ncol, 32))

        # Weno settings
        weno = discretization.create_group('weno')
        weno.create_dataset('BOUNDARY_MODEL', data=0)  # 0 = exact integration (Danckwerts)
        weno.create_dataset('WENO_EPS', data=1e-10)
        weno.create_dataset('WENO_ORDER', data=3)

        # Adsorption (Linear binding)
        adsorption = unit_001.create_group('adsorption')
        adsorption.create_dataset('IS_KINETIC', data=1)
        adsorption.create_dataset('ADSORPTION_MODEL', data=b'LINEAR')
        adsorption_model = adsorption.create_group('adsorption_model')
        adsorption_model.create_dataset('LIN_KA', data=[2.0] * ncomp)
        adsorption_model.create_dataset('LIN_KD', data=[1.0] * ncomp)

        # Initial conditions
        unit_001.create_dataset('INIT_C', data=[0.0] * ncomp)
        unit_001.create_dataset('INIT_Q', data=[0.0] * ncomp)

        # ==== UNIT 002: OUTLET ====
        unit_002 = model.create_group('unit_002')
        unit_002.create_dataset('UNIT_TYPE', data=b'OUTLET')
        unit_002.create_dataset('NCOMP', data=ncomp)

        # Connections (Inlet -> Column -> Outlet)
        connections = model.create_group('connections')
        connections.create_dataset('NSWITCHES', data=1)
        connections.create_dataset('CONNECTIONS_INCLUDE_PORTS', data=1)

        switch_000 = connections.create_group('switch_000')
        # Inlet (000) -> Column (001), port -1 (all) -> port -1 (all)
        # Column (001) -> Outlet (002), port -1 -> port -1
        switch_000.create_dataset('SECTION', data=0)
        switch_000.create_dataset('CONNECTIONS', data=[
            [0, 1, -1, -1, 1.0],  # Inlet -> Column, Q=1.0
            [1, 2, -1, -1, 1.0]   # Column -> Outlet, Q=1.0
        ])

        # Return data
        ret = inp.create_group('return')
        ret.create_dataset('WRITE_SOLUTION_TIMES', data=1)
        ret.create_dataset('WRITE_SOLUTION_LAST', data=1)
        ret.create_dataset('WRITE_SENS_LAST', data=0)

        # Unit operations to return
        unit_001_ret = ret.create_group('unit_001')
        unit_001_ret.create_dataset('WRITE_SOLUTION_BULK', data=1)
        unit_001_ret.create_dataset('WRITE_SOLUTION_PARTICLE', data=0)
        unit_001_ret.create_dataset('WRITE_SOLUTION_SOLID', data=0)
        unit_001_ret.create_dataset('WRITE_SOLUTION_FLUX', data=0)
        unit_001_ret.create_dataset('WRITE_SOLUTION_INLET', data=1)
        unit_001_ret.create_dataset('WRITE_SOLUTION_OUTLET', data=1)
        unit_001_ret.create_dataset('WRITE_SOLDOT', data=0)
        unit_001_ret.create_dataset('WRITE_SENS_BULK', data=0)
        unit_001_ret.create_dataset('WRITE_SENS_PARTICLE', data=0)
        unit_001_ret.create_dataset('WRITE_SENS_SOLID', data=0)
        unit_001_ret.create_dataset('WRITE_SENS_FLUX', data=0)
        unit_001_ret.create_dataset('WRITE_SENS_INLET', data=0)
        unit_001_ret.create_dataset('WRITE_SENS_OUTLET', data=0)

    print(f"✓ Created: {filename}\n")


def run_cadet_simulation(input_file, output_file, cadet_path='./build/bin/cadet-cli'):
    """Run CADET simulation and return result code"""
    cmd = [str(cadet_path), str(input_file), str(output_file)]
    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print(f"✓ Simulation completed successfully")
            return True
        else:
            print(f"✗ Simulation FAILED (return code {result.returncode})")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"✗ Simulation TIMEOUT (>300s)")
        return False
    except Exception as e:
        print(f"✗ Simulation ERROR: {e}")
        return False


def extract_results(output_file):
    """Extract outlet profiles and solver statistics"""
    try:
        with h5py.File(output_file, 'r') as f:
            # Outlet concentration
            outlet = f['output/solution/unit_001/SOLUTION_OUTLET'][:]

            # Solver statistics
            stats = {}
            if 'output/solver/NUM_LIN_ITERS' in f:
                stats['NUM_LIN_ITERS'] = f['output/solver/NUM_LIN_ITERS'][()]
            if 'output/solver/NUM_GMRES_RESTARTS' in f:
                stats['NUM_GMRES_RESTARTS'] = f['output/solver/NUM_GMRES_RESTARTS'][()]
            if 'output/solver/NUM_TIMESTEPS' in f:
                stats['NUM_TIMESTEPS'] = f['output/solver/NUM_TIMESTEPS'][()]

            return outlet, stats

    except Exception as e:
        print(f"✗ Failed to extract results: {e}")
        return None, None


def compare_results(baseline_outlet, precond_outlet, tolerance=1e-6):
    """Compare baseline vs preconditioned results"""

    if baseline_outlet is None or precond_outlet is None:
        print("✗ COMPARISON FAILED: Missing data")
        return False

    # Check shapes match
    if baseline_outlet.shape != precond_outlet.shape:
        print(f"✗ SHAPE MISMATCH: {baseline_outlet.shape} vs {precond_outlet.shape}")
        return False

    # Compute differences
    abs_diff = np.abs(baseline_outlet - precond_outlet)
    rel_diff = abs_diff / (np.abs(baseline_outlet) + 1e-12)

    max_abs_diff = np.max(abs_diff)
    max_rel_diff = np.max(rel_diff)
    mean_abs_diff = np.mean(abs_diff)

    print(f"\n{'='*70}")
    print(f"SOLUTION COMPARISON")
    print(f"{'='*70}")
    print(f"Max absolute difference: {max_abs_diff:.2e}")
    print(f"Max relative difference: {max_rel_diff:.2e}")
    print(f"Mean absolute difference: {mean_abs_diff:.2e}")
    print(f"Tolerance: {tolerance:.2e}")

    # Check for NaNs
    if np.any(np.isnan(baseline_outlet)) or np.any(np.isnan(precond_outlet)):
        print(f"✗ CONTAINS NaN VALUES")
        return False

    # Check tolerance
    if max_abs_diff < tolerance:
        print(f"✓ CORRECTNESS GATE PASSED (max_diff < tol)")
        return True
    else:
        print(f"✗ CORRECTNESS GATE FAILED (max_diff >= tol)")
        return False


def compare_performance(baseline_stats, precond_stats):
    """Compare solver performance metrics"""

    print(f"\n{'='*70}")
    print(f"PERFORMANCE COMPARISON")
    print(f"{'='*70}")
    print(f"{'Metric':<30} {'Baseline':>15} {'Precond':>15} {'Change':>15}")
    print(f"{'-'*70}")

    for key in baseline_stats:
        if key in precond_stats:
            baseline_val = baseline_stats[key]
            precond_val = precond_stats[key]

            if baseline_val > 0:
                change = (precond_val - baseline_val) / baseline_val * 100
                change_str = f"{change:+.1f}%"
            else:
                change_str = "N/A"

            print(f"{key:<30} {baseline_val:>15} {precond_val:>15} {change_str:>15}")


def main():
    """Run comprehensive Part A validation suite"""

    print("="*70)
    print("PART A BULK PRECONDITIONER VALIDATION SUITE")
    print("Track 2b - Danckwerts Spectral Preconditioner")
    print("="*70)
    print()

    # Test configuration
    test_dir = Path("test_bulk_precond_results")
    test_dir.mkdir(exist_ok=True)

    # Try multiple possible locations for CADET binary
    cadet_paths = [
        Path("build/bin/cadet-cli"),
        Path("build/src/cadet-cli/cadet-cli"),
        Path("build/cadet-cli"),
    ]

    cadet_binary = None
    for path in cadet_paths:
        if path.exists():
            cadet_binary = path
            break

    if cadet_binary is None:
        print(f"✗ CADET binary not found in any of:")
        for path in cadet_paths:
            print(f"  {path}")
        print("  Run: cmake --build build -j $(nproc)")
        return 1

    print(f"Found CADET binary: {cadet_binary}\n")

    # Test cases: (name, ncol, npar, ncomp, peclet)
    test_cases = [
        ("baseline_small", 64, 4, 1, 100),
        ("baseline_medium", 128, 8, 1, 500),
        ("baseline_multicomp", 64, 4, 3, 100),
    ]

    all_passed = True

    for test_name, ncol, npar, ncomp, peclet in test_cases:
        print(f"\n{'#'*70}")
        print(f"TEST CASE: {test_name}")
        print(f"{'#'*70}\n")

        # Create input files
        baseline_input = test_dir / f"{test_name}_baseline.h5"
        precond_input = test_dir / f"{test_name}_precond.h5"
        baseline_output = test_dir / f"{test_name}_baseline_out.h5"
        precond_output = test_dir / f"{test_name}_precond_out.h5"

        # Generate configurations
        create_grm_test_case(baseline_input, use_precond=False,
                           ncol=ncol, npar=npar, ncomp=ncomp, peclet=peclet)
        create_grm_test_case(precond_input, use_precond=True,
                           ncol=ncol, npar=npar, ncomp=ncomp, peclet=peclet)

        # Run simulations
        print("\n--- Running BASELINE ---")
        baseline_ok = run_cadet_simulation(baseline_input, baseline_output, cadet_binary)

        print("\n--- Running PRECONDITIONED ---")
        precond_ok = run_cadet_simulation(precond_input, precond_output, cadet_binary)

        if not baseline_ok or not precond_ok:
            print(f"\n✗ TEST FAILED: Simulation error")
            all_passed = False
            continue

        # Extract results
        baseline_outlet, baseline_stats = extract_results(baseline_output)
        precond_outlet, precond_stats = extract_results(precond_output)

        # Compare correctness
        correctness_ok = compare_results(baseline_outlet, precond_outlet, tolerance=1e-6)

        # Compare performance
        compare_performance(baseline_stats, precond_stats)

        # Overall test result
        if correctness_ok:
            print(f"\n✓ TEST PASSED: {test_name}")
        else:
            print(f"\n✗ TEST FAILED: {test_name}")
            all_passed = False

    # Final summary
    print(f"\n{'='*70}")
    print(f"VALIDATION SUITE SUMMARY")
    print(f"{'='*70}")

    if all_passed:
        print(f"✓ ALL TESTS PASSED")
        print(f"   Part A bulk preconditioner is VALIDATED")
        print(f"   Ready to proceed to Part B (full GRM Jacobian)")
        return 0
    else:
        print(f"✗ SOME TESTS FAILED")
        print(f"   Review errors above before proceeding to Part B")
        return 1


if __name__ == '__main__':
    sys.exit(main())
