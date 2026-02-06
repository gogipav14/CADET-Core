#!/usr/bin/env python3
"""
Simple validation test for Danckwerts bulk preconditioner (Part A)
Uses existing minimal_grm generator from cadet_lab
"""

import sys
import subprocess
import numpy as np
import h5py
from pathlib import Path

# Add cadet-lab-tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / "cadet-lab-tools"))

from cadet_lab.config_gen.minimal_grm import create_minimal_grm_config


def add_preconditioner_config(h5_file, enable=True, modes=32):
    """Add preconditioner configuration to existing HDF5 file"""
    with h5py.File(h5_file, 'a') as f:
        discr = f['input/model/unit_001/discretization']
        if 'USE_DANCKWERTS_BULK_PRECOND' in discr:
            del discr['USE_DANCKWERTS_BULK_PRECOND']
        if 'DANCKWERTS_BULK_PRECOND_MODES' in discr:
            del discr['DANCKWERTS_BULK_PRECOND_MODES']

        discr.create_dataset('USE_DANCKWERTS_BULK_PRECOND', data=1 if enable else 0)
        if enable:
            discr.create_dataset('DANCKWERTS_BULK_PRECOND_MODES', data=modes)


def run_test(test_name, peclet, ncol):
    """Run a single test case"""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name} (Pe={peclet}, NCOL={ncol})")
    print(f"{'='*70}")

    test_dir = Path("test_precond_results")
    test_dir.mkdir(exist_ok=True)

    # Create configurations
    baseline_input = test_dir / f"{test_name}_baseline.h5"
    precond_input = test_dir / f"{test_name}_precond.h5"
    baseline_output = test_dir / f"{test_name}_baseline_out.h5"
    precond_output = test_dir / f"{test_name}_precond_out.h5"

    print(f"\nCreating configurations...")
    create_minimal_grm_config(
        baseline_input,
        n_col=ncol,
        peclet=peclet,
        end_time=1000.0,
        n_times=101,
    )
    add_preconditioner_config(baseline_input, enable=False)
    print(f"  ✓ Baseline: {baseline_input}")

    create_minimal_grm_config(
        precond_input,
        n_col=ncol,
        peclet=peclet,
        end_time=1000.0,
        n_times=101,
    )
    add_preconditioner_config(precond_input, enable=True, modes=min(ncol, 32))
    print(f"  ✓ Precond: {precond_input}")

    # Run simulations
    cadet_bin = Path("build/src/cadet-cli/cadet-cli")
    if not cadet_bin.exists():
        print(f"✗ CADET binary not found: {cadet_bin}")
        return False

    print(f"\nRunning BASELINE simulation...")
    result = subprocess.run([str(cadet_bin), str(baseline_input), str(baseline_output)],
                          capture_output=True, timeout=120)
    if result.returncode != 0:
        print(f"✗ BASELINE FAILED")
        print(result.stderr.decode())
        return False
    print(f"  ✓ Baseline completed")

    print(f"\nRunning PRECOND simulation...")
    result = subprocess.run([str(cadet_bin), str(precond_input), str(precond_output)],
                          capture_output=True, timeout=120)
    if result.returncode != 0:
        print(f"✗ PRECOND FAILED")
        print(result.stderr.decode())
        return False
    print(f"  ✓ Precond completed")

    # Compare results
    print(f"\nComparing results...")
    with h5py.File(baseline_output, 'r') as f:
        baseline_outlet = f['output/solution/unit_001/SOLUTION_OUTLET'][:]
        baseline_stats = {}
        if 'output/solver_statistics' in f:
            stats_group = f['output/solver_statistics']
            for key in ['NUM_LIN_ITERS', 'NUM_STEPS', 'NUM_GMRES_RESTARTS', 'NUM_NONLIN_ITERS']:
                if key in stats_group:
                    baseline_stats[key] = stats_group[key][()]

    with h5py.File(precond_output, 'r') as f:
        precond_outlet = f['output/solution/unit_001/SOLUTION_OUTLET'][:]
        precond_stats = {}
        if 'output/solver_statistics' in f:
            stats_group = f['output/solver_statistics']
            for key in ['NUM_LIN_ITERS', 'NUM_STEPS', 'NUM_GMRES_RESTARTS', 'NUM_NONLIN_ITERS']:
                if key in stats_group:
                    precond_stats[key] = stats_group[key][()]

    # Check correctness
    abs_diff = np.abs(baseline_outlet - precond_outlet)
    max_diff = np.max(abs_diff)
    mean_diff = np.mean(abs_diff)

    print(f"\n  Solution difference:")
    print(f"    Max:  {max_diff:.2e}")
    print(f"    Mean: {mean_diff:.2e}")

    tolerance = 1e-6
    if max_diff < tolerance:
        print(f"  ✓ CORRECTNESS PASSED (diff < {tolerance:.0e})")
        correctness_ok = True
    else:
        print(f"  ✗ CORRECTNESS FAILED (diff >= {tolerance:.0e})")
        correctness_ok = False

    # Check for NaNs
    if np.any(np.isnan(baseline_outlet)) or np.any(np.isnan(precond_outlet)):
        print(f"  ✗ CONTAINS NaN")
        correctness_ok = False

    # Performance comparison
    print(f"\n  Solver statistics:")
    print(f"    {'Metric':<20} {'Baseline':>12} {'Precond':>12} {'Change':>12}")
    print(f"    {'-'*58}")
    for key in baseline_stats:
        if key in precond_stats:
            b_val = baseline_stats[key]
            p_val = precond_stats[key]
            if b_val > 0:
                change = (p_val - b_val) / b_val * 100
                change_str = f"{change:+.1f}%"
            else:
                change_str = "N/A"
            print(f"    {key:<20} {b_val:>12} {p_val:>12} {change_str:>12}")

    return correctness_ok


def main():
    print("="*70)
    print("PART A BULK PRECONDITIONER - SIMPLE VALIDATION")
    print("="*70)

    tests = [
        ("pe100_n64", 100, 64),
        ("pe1000_n128", 1000, 128),
        ("pe100_n256", 100, 256),
    ]

    all_passed = True
    for test_name, peclet, ncol in tests:
        passed = run_test(test_name, peclet, ncol)
        if not passed:
            all_passed = False

    print(f"\n{'='*70}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*70}")
    if all_passed:
        print(f"✓ ALL TESTS PASSED")
        print(f"  Part A bulk preconditioner is VALIDATED")
        return 0
    else:
        print(f"✗ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
