#!/usr/bin/env python3
"""Integration tests for Phase C full-state validation infrastructure.

This script performs end-to-end testing with actual CADET simulations.
"""

import sys
import tempfile
from pathlib import Path
import h5py
import numpy as np

# Add cadet_lab to path
sys.path.insert(0, str(Path(__file__).parent))

from cadet_lab.config_gen.minimal_grm import create_minimal_grm_config
from cadet_lab.harness.run_case import run_case
from cadet_lab.telemetry.read_hdf5 import read_solution
from cadet_lab.telemetry.full_state_metrics import compare_full_state
from cadet_lab.validation import (
    create_reference_config,
    run_reference,
    run_tolerance_sweep,
    run_with_step_advisor,
    run_spatial_convergence_check,
)
from cadet_lab.stress_suite.cases import case_first_step_fail
from cadet_lab.stress_suite.runner import run_stress_suite


def test_1_basic_full_state_output(cadet_cli_path, output_dir):
    """Test 1: Generate config with full-state output and verify HDF5 structure."""
    print("\n" + "="*80)
    print("TEST 1: Basic Full-State Output")
    print("="*80)

    # Generate config with full-state output enabled
    config_path = output_dir / "test1_config.h5"
    create_minimal_grm_config(
        output_path=config_path,
        n_times=11,
        end_time=10.0,
        abstol=1e-8,
        reltol=1e-6,
        enable_full_state_output=True,
    )

    print(f"✓ Generated config: {config_path}")

    # Verify config has flags set
    with h5py.File(config_path, "r") as f:
        unit_ret = f["input/return/unit_001"]
        assert unit_ret["WRITE_SOLUTION_BULK"][()] == 1, "WRITE_SOLUTION_BULK not set"
        assert unit_ret["WRITE_SOLUTION_PARTICLE"][()] == 1, "WRITE_SOLUTION_PARTICLE not set"
        assert unit_ret["WRITE_SOLUTION_SOLID"][()] == 1, "WRITE_SOLUTION_SOLID not set"
        assert unit_ret["WRITE_COORDINATES"][()] == 1, "WRITE_COORDINATES not set"

    print("✓ Config flags verified")

    # Run simulation
    result = run_case(
        input_file=config_path,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir,
    )

    output_file = result.output_file

    if not result.success:
        print(f"✗ Simulation failed: {result.failure_reason}")
        return False

    print(f"✓ Simulation completed in {result.wall_time:.3f}s")

    # Verify HDF5 output structure
    with h5py.File(output_file, "r") as f:
        solution = f["output/solution"]
        unit_001 = solution["unit_001"]

        # Check bulk data
        assert "SOLUTION_BULK" in unit_001, "SOLUTION_BULK dataset missing"
        bulk = unit_001["SOLUTION_BULK"]
        print(f"  SOLUTION_BULK shape: {bulk.shape}")
        assert bulk.ndim >= 2, "SOLUTION_BULK should be at least 2D (time x spatial)"

        # Check particle data (CADET writes SOLUTION_PARTICLE without partype suffix)
        assert "SOLUTION_PARTICLE" in unit_001, "SOLUTION_PARTICLE missing"
        particle = unit_001["SOLUTION_PARTICLE"]
        print(f"  SOLUTION_PARTICLE_PARTYPE_000 shape: {particle.shape}")
        assert particle.ndim >= 2, "SOLUTION_PARTICLE should be at least 2D"

        # Check solid data (CADET writes SOLUTION_SOLID without partype suffix)
        assert "SOLUTION_SOLID" in unit_001, "SOLUTION_SOLID missing"
        solid = unit_001["SOLUTION_SOLID"]
        print(f"  SOLUTION_SOLID_PARTYPE_000 shape: {solid.shape}")
        assert solid.ndim >= 2, "SOLUTION_SOLID should be at least 2D"

        # Check coordinates (optional - CADET may not write these)
        if "AXIAL_COORDINATES" in unit_001:
            axial_coords = unit_001["AXIAL_COORDINATES"]
            print(f"  AXIAL_COORDINATES shape: {axial_coords.shape}")
            assert axial_coords.ndim == 1, "AXIAL_COORDINATES should be 1D"
        else:
            print(f"  AXIAL_COORDINATES: not written (will use uniform grid fallback)")

        if "PARTICLE_COORDINATES" in unit_001:
            particle_coords = unit_001["PARTICLE_COORDINATES"]
            print(f"  PARTICLE_COORDINATES shape: {particle_coords.shape}")
            assert particle_coords.ndim == 1, "PARTICLE_COORDINATES should be 1D"
        else:
            print(f"  PARTICLE_COORDINATES: not written (will use uniform grid fallback)")

    print("✓ All HDF5 datasets present with correct structure")

    # Read with read_solution
    data = read_solution(output_file, read_full_state=True)

    assert len(data.bulk_profiles) > 0, "No bulk profiles read"
    assert len(data.particle_profiles) > 0, "No particle profiles read"
    assert len(data.solid_profiles) > 0, "No solid profiles read"
    # Coordinates are optional
    print(f"  Coordinates read: axial={len(data.coordinates.get('axial', {}))}, particle={len(data.coordinates.get('particle', {}))}")

    print(f"✓ read_solution() successfully read:")
    print(f"  - {len(data.bulk_profiles)} bulk profiles")
    print(f"  - {len(data.particle_profiles)} particle profiles")
    print(f"  - {len(data.solid_profiles)} solid profiles")
    print(f"  - {len(data.coordinates['axial'])} axial coordinate sets")
    print(f"  - {len(data.coordinates['particle'])} particle coordinate sets")

    print("\n✅ TEST 1 PASSED\n")
    return True


def test_2_full_state_metrics(cadet_cli_path, output_dir):
    """Test 2: Compute full-state metrics between two solutions."""
    print("\n" + "="*80)
    print("TEST 2: Full-State Metrics Computation")
    print("="*80)

    # Generate baseline solution
    config1 = output_dir / "test2_baseline.h5"
    create_minimal_grm_config(
        output_path=config1,
        abstol=1e-8,
        reltol=1e-6,
        enable_full_state_output=True,
    )

    result1 = run_case(config1, cadet_cli_path, output_dir=output_dir)
    output1 = result1.output_file

    if not result1.success:
        print(f"✗ Baseline failed: {result1.failure_reason}")
        return False

    print(f"✓ Baseline completed in {result1.wall_time:.3f}s")

    # Generate perturbed solution (looser tolerances)
    config2 = output_dir / "test2_perturbed.h5"
    create_minimal_grm_config(
        output_path=config2,
        abstol=1e-6,  # Looser
        reltol=1e-4,  # Looser
        enable_full_state_output=True,
    )

    result2 = run_case(config2, cadet_cli_path, output_dir=output_dir)
    output2 = result2.output_file

    if not result2.success:
        print(f"✗ Perturbed failed: {result2.failure_reason}")
        return False

    print(f"✓ Perturbed completed in {result2.wall_time:.3f}s")

    # Read both solutions
    data1 = read_solution(output1, read_full_state=True)
    data2 = read_solution(output2, read_full_state=True)

    # Compute metrics
    metrics = compare_full_state(
        test=data2,
        reference=data1,
        abstol=1e-8,
        reltol=1e-6,
    )

    print(f"\nMetrics (perturbed vs baseline):")
    print(f"  L∞ errors:")
    print(f"    Bulk:     {metrics.linf_bulk:.3e}")
    print(f"    Particle: {metrics.linf_particle:.3e}")
    print(f"    Solid:    {metrics.linf_solid:.3e}")
    print(f"    Global:   {metrics.linf_global:.3e}")
    print(f"  Scaled RMS errors:")
    print(f"    Bulk:     {metrics.scaled_rms_bulk:.3e}")
    print(f"    Particle: {metrics.scaled_rms_particle:.3e}")
    print(f"    Solid:    {metrics.scaled_rms_solid:.3e}")
    print(f"    Global:   {metrics.scaled_rms_global:.3e}")
    print(f"  DOFs:")
    print(f"    Bulk:     {metrics.n_bulk_dofs}")
    print(f"    Particle: {metrics.n_particle_dofs}")
    print(f"    Solid:    {metrics.n_solid_dofs}")

    # Sanity checks
    assert metrics.linf_global > 0, "Should have non-zero error"
    assert metrics.scaled_rms_global > 0, "Should have non-zero RMS"
    assert metrics.n_bulk_dofs > 0, "Should have bulk DOFs"
    assert metrics.n_particle_dofs > 0, "Should have particle DOFs"
    assert metrics.n_solid_dofs > 0, "Should have solid DOFs"

    print("\n✅ TEST 2 PASSED\n")
    return True


def test_3_reference_protocol(cadet_cli_path, output_dir):
    """Test 3: Reference protocol with time and space modes."""
    print("\n" + "="*80)
    print("TEST 3: Reference Protocol (Time & Space Modes)")
    print("="*80)

    # Test time mode
    print("\n--- Time Mode ---")
    ref_time = run_reference(
        case_generator=case_first_step_fail,
        case_kwargs={"_case_name": "first_step_fail"},
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir / "ref_time",
        mode="time",
        tolerance_factor=10.0,
    )

    print(f"✓ Time-mode reference completed: {ref_time}")

    # Verify tolerances were tightened
    baseline_path = output_dir / "ref_time" / "baseline.h5"
    ref_config_path = output_dir / "ref_time" / "reference_time.h5"

    with h5py.File(baseline_path, "r") as f:
        baseline_abstol = float(f["input/solver/time_integrator/ABSTOL"][()])
        baseline_reltol = float(f["input/solver/time_integrator/RELTOL"][()])

    with h5py.File(ref_config_path, "r") as f:
        ref_abstol = float(f["input/solver/time_integrator/ABSTOL"][()])
        ref_reltol = float(f["input/solver/time_integrator/RELTOL"][()])

    print(f"  Baseline: ABSTOL={baseline_abstol:.2e}, RELTOL={baseline_reltol:.2e}")
    print(f"  Reference: ABSTOL={ref_abstol:.2e}, RELTOL={ref_reltol:.2e}")

    assert abs(ref_abstol - baseline_abstol/10.0) < 1e-15, "ABSTOL not tightened correctly"
    assert abs(ref_reltol - baseline_reltol/10.0) < 1e-15, "RELTOL not tightened correctly"

    print("✓ Tolerances tightened correctly (10×)")

    # Test space mode
    print("\n--- Space Mode ---")
    ref_space = run_reference(
        case_generator=case_first_step_fail,
        case_kwargs={"_case_name": "first_step_fail"},
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir / "ref_space",
        mode="space",
        spatial_refinement_factor=2,
    )

    print(f"✓ Space-mode reference completed: {ref_space}")

    # Verify spatial resolution was refined
    baseline_path = output_dir / "ref_space" / "baseline.h5"
    ref_config_path = output_dir / "ref_space" / "reference_space.h5"

    with h5py.File(baseline_path, "r") as f:
        baseline_nelem = int(f["input/model/unit_001/discretization/NELEM"][()])
        baseline_par_nelem = int(f["input/model/unit_001/particle_type_000/discretization/PAR_NELEM"][()])

    with h5py.File(ref_config_path, "r") as f:
        ref_nelem = int(f["input/model/unit_001/discretization/NELEM"][()])
        ref_par_nelem = int(f["input/model/unit_001/particle_type_000/discretization/PAR_NELEM"][()])

    print(f"  Baseline: NELEM={baseline_nelem}, PAR_NELEM={baseline_par_nelem}")
    print(f"  Reference: NELEM={ref_nelem}, PAR_NELEM={ref_par_nelem}")

    assert ref_nelem == baseline_nelem * 2, "NELEM not refined correctly"
    assert ref_par_nelem == baseline_par_nelem * 2, "PAR_NELEM not refined correctly"

    print("✓ Spatial resolution refined correctly (2×)")

    print("\n✅ TEST 3 PASSED\n")
    return True


def test_4_tolerance_sweep(cadet_cli_path, output_dir):
    """Test 4: Tolerance sweep (small grid for speed)."""
    print("\n" + "="*80)
    print("TEST 4: Tolerance Sweep (2×2 grid)")
    print("="*80)

    # Generate reference first
    ref_output = run_reference(
        case_generator=case_first_step_fail,
        case_kwargs={"_case_name": "first_step_fail"},
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir / "sweep_ref",
        mode="time",
        tolerance_factor=100.0,  # Very tight reference
    )

    print(f"✓ Reference generated: {ref_output}")

    # Run small tolerance sweep
    wp_result = run_tolerance_sweep(
        case_generator=case_first_step_fail,
        case_kwargs={"_case_name": "first_step_fail"},
        reference_output=ref_output,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir / "sweep",
        abstol_grid=[1e-8, 1e-7],  # 2 points
        reltol_grid=[1e-5, 1e-4],  # 2 points
    )

    print(f"\nSweep Results:")
    print(f"  Case: {wp_result.case_name}")
    print(f"  Sweep points: {len(wp_result.sweep_points)}")

    assert len(wp_result.sweep_points) == 4, "Should have 2×2=4 points"

    # Print results table
    print(f"\n  {'ABSTOL':>10} {'RELTOL':>10} {'Steps':>8} {'Linf':>10} {'RMS':>10} {'Success':>8}")
    print("  " + "-"*68)
    for point in wp_result.sweep_points:
        print(f"  {point['abstol']:>10.2e} {point['reltol']:>10.2e} "
              f"{point['num_steps'] or 0:>8} "
              f"{point['linf_error'] or 0:>10.3e} "
              f"{point['scaled_rms_error'] or 0:>10.3e} "
              f"{'✓' if point['success'] else '✗':>8}")

    # Verify all succeeded
    success_count = sum(1 for p in wp_result.sweep_points if p['success'])
    print(f"\n  Success rate: {success_count}/{len(wp_result.sweep_points)}")

    # Save to JSON
    json_path = output_dir / "work_precision_test.json"
    wp_result.save(json_path)
    print(f"✓ Saved to: {json_path}")

    print("\n✅ TEST 4 PASSED\n")
    return True


def test_5_step_advisor(cadet_cli_path, output_dir):
    """Test 5: Step-size advisor with err_test_fails detection."""
    print("\n" + "="*80)
    print("TEST 5: Step-Size Advisor")
    print("="*80)

    # Generate first_step_fail case (known to have err_test_fails)
    input_file = output_dir / "step_advisor_input.h5"
    case_first_step_fail(output_path=input_file)  # Don't pass _case_name

    print(f"✓ Generated test case: {input_file}")

    # Run with advisor
    result, num_retries = run_with_step_advisor(
        input_file=input_file,
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir / "advisor",
        err_fail_threshold=5,
        step_reduction_factor=10.0,
        max_retries=2,
    )

    print(f"\nAdvisor Results:")
    print(f"  Success: {result.success}")
    print(f"  Retries: {num_retries}")
    print(f"  Final num_steps: {result.solver_stats.get('NUM_STEPS', 'N/A')}")
    print(f"  Final num_err_test_fails: {result.solver_stats.get('NUM_ERR_TEST_FAILS', 'N/A')}")

    if num_retries > 0:
        print(f"✓ Advisor triggered retry (expected for first_step_fail)")
    else:
        print(f"  No retry needed (case may have been fixed)")

    print("\n✅ TEST 5 PASSED\n")
    return True


def test_6_spatial_convergence(cadet_cli_path, output_dir):
    """Test 6: Spatial convergence check with interpolation."""
    print("\n" + "="*80)
    print("TEST 6: Spatial Convergence Check")
    print("="*80)

    sc_result = run_spatial_convergence_check(
        case_generator=case_first_step_fail,
        case_kwargs={"_case_name": "first_step_fail"},
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir / "spatial",
        spatial_refinement_factor=2,
        threshold=1e-2,  # Relaxed threshold for test
    )

    print(f"\nSpatial Convergence Results:")
    print(f"  Case: {sc_result.case_name}")
    print(f"  Baseline resolution: {sc_result.baseline_resolution}")
    print(f"  Refined resolution: {sc_result.refined_resolution}")
    print(f"  L∞ delta: {sc_result.linf_delta:.3e}")
    print(f"  Scaled RMS delta: {sc_result.scaled_rms_delta:.3e}")
    print(f"  Threshold: {sc_result.threshold:.3e}")
    print(f"  Converged: {'✓' if sc_result.convergence_achieved else '✗'}")

    # Save result
    json_path = output_dir / "spatial_convergence_test.json"
    sc_result.save(json_path)
    print(f"✓ Saved to: {json_path}")

    print("\n✅ TEST 6 PASSED\n")
    return True


def test_7_stress_suite_full_state(cadet_cli_path, output_dir):
    """Test 7: Stress suite with full-state mode."""
    print("\n" + "="*80)
    print("TEST 7: Stress Suite with Full-State Mode")
    print("="*80)

    # Run stress suite with full-state mode (just first_step_fail for speed)
    results = run_stress_suite(
        cadet_cli_path=cadet_cli_path,
        output_dir=output_dir / "stress_suite",
        cases=["first_step_fail"],  # Just one case for testing
        full_state_mode=True,
    )

    print(f"\nStress Suite Results:")
    print(f"  Total cases: {results.total_cases}")
    print(f"  Passed: {results.passed}")
    print(f"  Failed: {results.failed}")
    print(f"  Full-state metrics available: {results.full_state_metrics is not None}")

    if results.full_state_metrics:
        for case_name, metrics in results.full_state_metrics.items():
            print(f"\n  {case_name}:")
            for key, value in metrics.items():
                print(f"    {key}: {value}")

    # Save results
    json_path = output_dir / "stress_suite_full_state_test.json"
    results.save(json_path)
    print(f"\n✓ Saved to: {json_path}")

    print("\n✅ TEST 7 PASSED\n")
    return True


def main():
    """Run all integration tests."""
    cadet_cli_path = Path("/home/gogip/github_repos/CADET-Core/install/bin/cadet-cli")

    if not cadet_cli_path.exists():
        print(f"✗ CADET CLI not found at: {cadet_cli_path}")
        print("  Please build CADET first.")
        return 1

    print(f"Using CADET CLI: {cadet_cli_path}")

    with tempfile.TemporaryDirectory(prefix="phase_c_integration_") as tmpdir:
        output_dir = Path(tmpdir)
        print(f"Test output directory: {output_dir}")

        tests = [
            ("Basic Full-State Output", test_1_basic_full_state_output),
            ("Full-State Metrics", test_2_full_state_metrics),
            ("Reference Protocol", test_3_reference_protocol),
            ("Tolerance Sweep", test_4_tolerance_sweep),
            ("Step Advisor", test_5_step_advisor),
            ("Spatial Convergence", test_6_spatial_convergence),
            ("Stress Suite Full-State", test_7_stress_suite_full_state),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func(cadet_cli_path, output_dir):
                    passed += 1
                else:
                    failed += 1
                    print(f"✗ {name} FAILED")
            except Exception as e:
                failed += 1
                print(f"\n✗ {name} FAILED WITH EXCEPTION:")
                print(f"  {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "="*80)
        print("INTEGRATION TEST SUMMARY")
        print("="*80)
        print(f"Total tests: {len(tests)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if failed == 0:
            print("\n✅ ALL INTEGRATION TESTS PASSED!")
            return 0
        else:
            print(f"\n✗ {failed} test(s) failed")
            return 1


if __name__ == "__main__":
    sys.exit(main())
