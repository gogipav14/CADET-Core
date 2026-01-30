"""Tests for compare_to_cadet module.

Tests for comparing NILT reference solutions with CADET simulations.
"""

import numpy as np
import pytest
import h5py
from pathlib import Path

from cadet_lab.nilt.compare_to_cadet import (
    create_matching_cadet_config,
    compute_comparison_metrics,
    ComparisonResult,
    interpolate_to_common_grid,
)


class TestInterpolateToCommonGrid:
    """Tests for time grid interpolation."""

    def test_interpolates_to_common_grid(self):
        """Interpolates two signals to a common time grid."""
        t1 = np.array([0.0, 1.0, 2.0, 3.0])
        y1 = np.array([0.0, 1.0, 2.0, 3.0])
        t2 = np.array([0.0, 0.5, 1.5, 2.5, 3.0])
        y2 = np.array([0.0, 0.5, 1.5, 2.5, 3.0])

        t_common, y1_interp, y2_interp = interpolate_to_common_grid(t1, y1, t2, y2)

        # Common grid should span intersection of both
        assert t_common[0] >= max(t1[0], t2[0])
        assert t_common[-1] <= min(t1[-1], t2[-1])
        # Interpolated values should be close to original for linear data
        assert len(y1_interp) == len(t_common)
        assert len(y2_interp) == len(t_common)

    def test_handles_identical_grids(self):
        """Handles case where both grids are identical."""
        t = np.array([0.0, 1.0, 2.0, 3.0])
        y1 = np.array([1.0, 2.0, 3.0, 4.0])
        y2 = np.array([1.1, 2.1, 3.1, 4.1])

        t_common, y1_interp, y2_interp = interpolate_to_common_grid(t, y1, t, y2)

        # Results should be interpolated versions
        assert len(t_common) > 0
        assert len(y1_interp) == len(t_common)
        assert len(y2_interp) == len(t_common)

    def test_preserves_linear_relationship(self):
        """Linear data should be preserved after interpolation."""
        t1 = np.linspace(0, 10, 11)
        y1 = 2 * t1 + 1  # y = 2x + 1
        t2 = np.linspace(0, 10, 21)
        y2 = 2 * t2 + 1

        t_common, y1_interp, y2_interp = interpolate_to_common_grid(t1, y1, t2, y2)

        # Both should still follow y = 2x + 1
        expected = 2 * t_common + 1
        np.testing.assert_allclose(y1_interp, expected, rtol=1e-10)
        np.testing.assert_allclose(y2_interp, expected, rtol=1e-10)


class TestComputeComparisonMetrics:
    """Tests for computing comparison metrics."""

    def test_computes_rmse(self):
        """Computes RMSE correctly."""
        y_ref = np.array([1.0, 2.0, 3.0, 4.0])
        y_test = np.array([1.1, 2.1, 3.1, 4.1])

        result = compute_comparison_metrics(y_ref, y_test)

        expected_rmse = np.sqrt(np.mean((y_ref - y_test) ** 2))
        assert result.rmse == pytest.approx(expected_rmse)

    def test_computes_l2_norm(self):
        """Computes L2 norm of difference correctly."""
        y_ref = np.array([1.0, 2.0, 3.0, 4.0])
        y_test = np.array([1.0, 2.0, 3.0, 4.0])  # Identical

        result = compute_comparison_metrics(y_ref, y_test)

        assert result.l2_norm == pytest.approx(0.0)

    def test_computes_linf_norm(self):
        """Computes L-infinity (max) norm correctly."""
        y_ref = np.array([1.0, 2.0, 3.0, 4.0])
        y_test = np.array([1.0, 2.5, 3.0, 4.0])  # Max diff at index 1

        result = compute_comparison_metrics(y_ref, y_test)

        expected_linf = 0.5
        assert result.linf_norm == pytest.approx(expected_linf)

    def test_computes_relative_error(self):
        """Computes relative L2 error correctly."""
        y_ref = np.array([1.0, 2.0, 3.0, 4.0])
        y_test = np.array([1.1, 2.2, 3.3, 4.4])  # 10% error

        result = compute_comparison_metrics(y_ref, y_test)

        # Relative error = ||y_ref - y_test||_2 / ||y_ref||_2
        expected_rel = np.linalg.norm(y_ref - y_test) / np.linalg.norm(y_ref)
        assert result.relative_l2_error == pytest.approx(expected_rel)

    def test_comparison_result_structure(self):
        """ComparisonResult has all expected fields."""
        y_ref = np.array([1.0, 2.0, 3.0])
        y_test = np.array([1.0, 2.0, 3.0])

        result = compute_comparison_metrics(y_ref, y_test)

        assert hasattr(result, "rmse")
        assert hasattr(result, "l2_norm")
        assert hasattr(result, "linf_norm")
        assert hasattr(result, "relative_l2_error")

    def test_handles_zero_reference(self):
        """Handles case where reference is all zeros."""
        y_ref = np.array([0.0, 0.0, 0.0])
        y_test = np.array([0.1, 0.1, 0.1])

        result = compute_comparison_metrics(y_ref, y_test)

        # Should not raise, relative error should be inf or handled
        assert np.isfinite(result.rmse)
        assert np.isfinite(result.l2_norm)


class TestCreateMatchingCadetConfig:
    """Tests for creating CADET configs matching NILT benchmark parameters."""

    def test_creates_valid_hdf5(self, tmp_path):
        """Creates a valid HDF5 configuration file."""
        output_path = tmp_path / "matching_config.h5"

        result = create_matching_cadet_config(
            output_path=output_path,
            velocity=1e-3,
            dispersion=1e-6,
            length=0.1,
            t_max=100.0,
            n_times=101,
        )

        assert result.exists()

    def test_config_has_matching_parameters(self, tmp_path):
        """Config parameters match requested values."""
        output_path = tmp_path / "matching_config.h5"
        velocity = 1e-3
        dispersion = 1e-6
        length = 0.1
        t_max = 100.0

        create_matching_cadet_config(
            output_path=output_path,
            velocity=velocity,
            dispersion=dispersion,
            length=length,
            t_max=t_max,
            n_times=101,
        )

        with h5py.File(output_path, "r") as f:
            v = f["input/model/unit_001/VELOCITY"][()]
            d = f["input/model/unit_001/COL_DISPERSION"][()]
            L = f["input/model/unit_001/COL_LENGTH"][()]

            assert v == pytest.approx(velocity)
            assert d == pytest.approx(dispersion)
            assert L == pytest.approx(length)


class TestComparisonResultSerialization:
    """Tests for ComparisonResult serialization."""

    def test_to_dict(self):
        """ComparisonResult can be converted to dict."""
        result = ComparisonResult(
            rmse=0.01,
            l2_norm=0.05,
            linf_norm=0.02,
            relative_l2_error=0.001,
            t_grid=np.array([0.0, 1.0, 2.0]),
            y_ref=np.array([1.0, 2.0, 3.0]),
            y_cadet=np.array([1.01, 2.01, 3.01]),
        )

        d = result.to_dict()

        assert d["rmse"] == pytest.approx(0.01)
        assert d["l2_norm"] == pytest.approx(0.05)
        assert d["linf_norm"] == pytest.approx(0.02)
        assert d["relative_l2_error"] == pytest.approx(0.001)

    def test_to_json(self):
        """ComparisonResult can be serialized to JSON."""
        result = ComparisonResult(
            rmse=0.01,
            l2_norm=0.05,
            linf_norm=0.02,
            relative_l2_error=0.001,
        )

        json_str = result.to_json()

        assert '"rmse": 0.01' in json_str
        assert '"l2_norm": 0.05' in json_str
