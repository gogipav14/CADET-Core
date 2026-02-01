"""Tests for full-state metrics computation."""

import pytest
import numpy as np
from pathlib import Path

from cadet_lab.telemetry.full_state_metrics import (
    compute_scaled_rms,
    compute_linf,
    compare_full_state,
    FullStateMetrics,
)
from cadet_lab.telemetry.read_hdf5 import SolutionData


def test_compute_linf_zero_error():
    """Test Linf with identical arrays."""
    y = np.array([1.0, 2.0, 3.0])
    y_ref = np.array([1.0, 2.0, 3.0])
    linf = compute_linf(y, y_ref)
    assert linf == 0.0


def test_compute_linf_constant_offset():
    """Test Linf with constant offset."""
    y = np.array([1.1, 2.1, 3.1])
    y_ref = np.array([1.0, 2.0, 3.0])
    linf = compute_linf(y, y_ref)
    assert abs(linf - 0.1) < 1e-10


def test_compute_linf_max_error():
    """Test Linf picks maximum error."""
    y = np.array([1.0, 2.5, 3.0])
    y_ref = np.array([1.0, 2.0, 3.0])
    linf = compute_linf(y, y_ref)
    assert abs(linf - 0.5) < 1e-10


def test_compute_linf_multidimensional():
    """Test Linf with multidimensional arrays."""
    y = np.array([[1.0, 2.0], [3.0, 4.0]])
    y_ref = np.array([[1.0, 2.1], [3.0, 4.0]])
    linf = compute_linf(y, y_ref)
    assert abs(linf - 0.1) < 1e-10


def test_compute_linf_empty():
    """Test Linf with empty arrays."""
    y = np.array([])
    y_ref = np.array([])
    linf = compute_linf(y, y_ref)
    assert linf == 0.0


def test_compute_linf_shape_mismatch():
    """Test Linf raises on shape mismatch."""
    y = np.array([1.0, 2.0])
    y_ref = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="Shape mismatch"):
        compute_linf(y, y_ref)


def test_compute_scaled_rms_zero_error():
    """Test scaled RMS with identical arrays."""
    y = np.array([1.0, 2.0, 3.0])
    y_ref = np.array([1.0, 2.0, 3.0])
    rms = compute_scaled_rms(y, y_ref, abstol=1e-6, reltol=1e-6)
    assert rms == 0.0


def test_compute_scaled_rms_constant_offset():
    """Test scaled RMS with constant offset."""
    y = np.ones(100) * 1.1
    y_ref = np.ones(100) * 1.0
    abstol = 1e-6
    reltol = 1e-6

    # Expected scaling: atol + rtol * max(1.1, 1.0) = 1e-6 + 1e-6 * 1.1
    # Error = 0.1
    # Scaled error = 0.1 / (1e-6 + 1.1e-6) ≈ 0.1 / 2.1e-6 ≈ 47619
    # RMS = 47619
    rms = compute_scaled_rms(y, y_ref, abstol, reltol)
    expected_scale = abstol + reltol * 1.1
    expected_rms = 0.1 / expected_scale
    assert abs(rms - expected_rms) < 1e-3


def test_compute_scaled_rms_abstol_dominated():
    """Test scaled RMS when abstol dominates."""
    y = np.array([1e-8, 2e-8, 3e-8])
    y_ref = np.array([0.0, 0.0, 0.0])
    abstol = 1e-6
    reltol = 1e-6

    # For small values, abstol dominates
    # Scaling ≈ abstol = 1e-6
    # Errors: [1e-8, 2e-8, 3e-8]
    # Scaled errors: [0.01, 0.02, 0.03]
    # RMS ≈ sqrt(mean([0.0001, 0.0004, 0.0009])) = sqrt(0.000467) ≈ 0.0216
    rms = compute_scaled_rms(y, y_ref, abstol, reltol)
    assert rms < 0.1  # Should be small when errors << abstol


def test_compute_scaled_rms_reltol_dominated():
    """Test scaled RMS when reltol dominates."""
    y = np.array([1.1, 2.2, 3.3])
    y_ref = np.array([1.0, 2.0, 3.0])
    abstol = 1e-10
    reltol = 0.1

    # For large values, reltol dominates
    # Errors: [0.1, 0.2, 0.3]
    # Scaling for each: 1e-10 + 0.1 * max(y, y_ref)
    # For first: 1e-10 + 0.1 * 1.1 = 0.11
    # Scaled error: 0.1 / 0.11 ≈ 0.909
    rms = compute_scaled_rms(y, y_ref, abstol, reltol)
    # Should be O(1) since relative error is ~10% and reltol is 10%
    assert 0.5 < rms < 2.0


def test_compute_scaled_rms_multidimensional():
    """Test scaled RMS with multidimensional arrays."""
    y = np.ones((10, 10, 10)) * 2.0
    y_ref = np.ones((10, 10, 10)) * 1.0
    rms = compute_scaled_rms(y, y_ref, abstol=1e-6, reltol=1e-6)
    # Constant error of 1.0, scaling ≈ 1e-6 + 1e-6*2 = 3e-6
    expected = 1.0 / 3e-6
    assert abs(rms - expected) < 1.0


def test_compute_scaled_rms_empty():
    """Test scaled RMS with empty arrays."""
    y = np.array([])
    y_ref = np.array([])
    rms = compute_scaled_rms(y, y_ref, abstol=1e-6, reltol=1e-6)
    assert rms == 0.0


def test_compute_scaled_rms_shape_mismatch():
    """Test scaled RMS raises on shape mismatch."""
    y = np.array([1.0, 2.0])
    y_ref = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="Shape mismatch"):
        compute_scaled_rms(y, y_ref, abstol=1e-6, reltol=1e-6)


def test_compare_full_state_bulk_only():
    """Test full-state comparison with bulk phase only."""
    test = SolutionData(
        solution_times=np.array([0.0, 1.0]),
        outlet_profiles={},
        bulk_profiles={"unit_001": np.array([[1.1, 1.1], [2.1, 2.1]])},
    )
    reference = SolutionData(
        solution_times=np.array([0.0, 1.0]),
        outlet_profiles={},
        bulk_profiles={"unit_001": np.array([[1.0, 1.0], [2.0, 2.0]])},
    )

    metrics = compare_full_state(test, reference, abstol=1e-6, reltol=1e-6)

    assert metrics.n_bulk_dofs == 4
    assert metrics.n_particle_dofs == 0
    assert metrics.n_solid_dofs == 0
    assert abs(metrics.linf_bulk - 0.1) < 1e-10
    assert metrics.linf_global == metrics.linf_bulk
    assert metrics.scaled_rms_global == metrics.scaled_rms_bulk


def test_compare_full_state_particle_only():
    """Test full-state comparison with particle phase only."""
    test = SolutionData(
        solution_times=np.array([0.0, 1.0]),
        outlet_profiles={},
        particle_profiles={("unit_001", 0): np.array([[1.1], [2.1]])},
    )
    reference = SolutionData(
        solution_times=np.array([0.0, 1.0]),
        outlet_profiles={},
        particle_profiles={("unit_001", 0): np.array([[1.0], [2.0]])},
    )

    metrics = compare_full_state(test, reference, abstol=1e-6, reltol=1e-6)

    assert metrics.n_bulk_dofs == 0
    assert metrics.n_particle_dofs == 2
    assert metrics.n_solid_dofs == 0
    assert abs(metrics.linf_particle - 0.1) < 1e-10
    assert metrics.linf_global == metrics.linf_particle


def test_compare_full_state_all_phases():
    """Test full-state comparison with all phases."""
    test = SolutionData(
        solution_times=np.array([0.0, 1.0]),
        outlet_profiles={},
        bulk_profiles={"unit_001": np.array([[1.1, 1.1], [2.1, 2.1]])},
        particle_profiles={("unit_001", 0): np.array([[1.2], [2.2]])},
        solid_profiles={("unit_001", 0): np.array([[1.3], [2.3]])},
    )
    reference = SolutionData(
        solution_times=np.array([0.0, 1.0]),
        outlet_profiles={},
        bulk_profiles={"unit_001": np.array([[1.0, 1.0], [2.0, 2.0]])},
        particle_profiles={("unit_001", 0): np.array([[1.0], [2.0]])},
        solid_profiles={("unit_001", 0): np.array([[1.0], [2.0]])},
    )

    metrics = compare_full_state(test, reference, abstol=1e-6, reltol=1e-6)

    assert metrics.n_bulk_dofs == 4
    assert metrics.n_particle_dofs == 2
    assert metrics.n_solid_dofs == 2
    assert abs(metrics.linf_bulk - 0.1) < 1e-10
    assert abs(metrics.linf_particle - 0.2) < 1e-10
    assert abs(metrics.linf_solid - 0.3) < 1e-10
    assert abs(metrics.linf_global - 0.3) < 1e-10  # Max of all phases

    # Global RMS should be DOF-weighted mean
    total_dofs = 4 + 2 + 2
    expected_global_rms = (
        metrics.scaled_rms_bulk * 4 +
        metrics.scaled_rms_particle * 2 +
        metrics.scaled_rms_solid * 2
    ) / total_dofs
    assert abs(metrics.scaled_rms_global - expected_global_rms) < 1e-10


def test_compare_full_state_multiple_particle_types():
    """Test aggregation across multiple particle types."""
    test = SolutionData(
        solution_times=np.array([0.0, 1.0]),
        outlet_profiles={},
        particle_profiles={
            ("unit_001", 0): np.array([[1.1], [2.1]]),
            ("unit_001", 1): np.array([[1.3], [2.3]]),
        },
    )
    reference = SolutionData(
        solution_times=np.array([0.0, 1.0]),
        outlet_profiles={},
        particle_profiles={
            ("unit_001", 0): np.array([[1.0], [2.0]]),
            ("unit_001", 1): np.array([[1.0], [2.0]]),
        },
    )

    metrics = compare_full_state(test, reference, abstol=1e-6, reltol=1e-6)

    assert metrics.n_particle_dofs == 4  # 2 + 2
    # Linf should be max across all particle types
    assert abs(metrics.linf_particle - 0.3) < 1e-10


def test_fullstate_metrics_to_dict():
    """Test FullStateMetrics to_dict serialization."""
    metrics = FullStateMetrics(
        linf_bulk=0.1,
        linf_particle=0.2,
        linf_solid=0.3,
        linf_global=0.3,
        scaled_rms_bulk=1.0,
        scaled_rms_particle=2.0,
        scaled_rms_solid=3.0,
        scaled_rms_global=2.0,
        n_bulk_dofs=100,
        n_particle_dofs=50,
        n_solid_dofs=25,
    )

    d = metrics.to_dict()
    assert d["linf_global"] == 0.3
    assert d["scaled_rms_global"] == 2.0
    assert d["n_bulk_dofs"] == 100
    assert len(d) == 11
