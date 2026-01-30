"""Tests for telemetry/read_hdf5.py - HDF5 output parsing."""

import numpy as np
import pytest
import h5py
from pathlib import Path

from cadet_lab.telemetry.read_hdf5 import read_solution, SolutionData


class TestReadSolution:
    """Test reading solution data from CADET HDF5 output files."""

    def test_read_solution_from_ref_file(self, sample_ref_h5):
        """Test reading solution from an existing reference file."""
        result = read_solution(sample_ref_h5)

        assert isinstance(result, SolutionData)
        assert result.solution_times is not None
        assert len(result.solution_times) > 0
        assert isinstance(result.solution_times, np.ndarray)

    def test_solution_times_are_monotonic(self, sample_ref_h5):
        """Verify solution times are monotonically increasing."""
        result = read_solution(sample_ref_h5)

        diffs = np.diff(result.solution_times)
        assert np.all(diffs >= 0), "Solution times should be monotonically increasing"

    def test_outlet_profiles_shape(self, sample_ref_h5):
        """Test that outlet profiles have expected shape."""
        result = read_solution(sample_ref_h5)

        # Should have at least one outlet profile
        assert len(result.outlet_profiles) > 0

        # Each profile should be a numpy array
        for unit_id, profile in result.outlet_profiles.items():
            assert isinstance(profile, np.ndarray)
            # First dimension should match solution times
            assert profile.shape[0] == len(result.solution_times)

    def test_read_nonexistent_file_raises(self, temp_dir):
        """Test that reading a nonexistent file raises appropriate error."""
        fake_path = temp_dir / "nonexistent.h5"

        with pytest.raises(FileNotFoundError):
            read_solution(fake_path)

    def test_read_invalid_hdf5_raises(self, temp_dir):
        """Test that reading an invalid HDF5 file raises appropriate error."""
        invalid_file = temp_dir / "invalid.h5"
        invalid_file.write_text("not an hdf5 file")

        with pytest.raises((OSError, ValueError)):
            read_solution(invalid_file)


class TestSolutionDataAttributes:
    """Test SolutionData dataclass attributes."""

    def test_solution_data_has_required_fields(self, sample_ref_h5):
        """Verify SolutionData has all required fields."""
        result = read_solution(sample_ref_h5)

        # Required fields
        assert hasattr(result, "solution_times")
        assert hasattr(result, "outlet_profiles")
        assert hasattr(result, "inlet_profiles")
        assert hasattr(result, "solver_stats")
        assert hasattr(result, "file_path")

    def test_solver_stats_is_dict_or_none(self, sample_ref_h5):
        """Solver stats should be a dict or None."""
        result = read_solution(sample_ref_h5)

        assert result.solver_stats is None or isinstance(result.solver_stats, dict)


class TestCreateSyntheticHDF5:
    """Test reading from synthetically created HDF5 files."""

    def test_read_minimal_synthetic_output(self, temp_dir):
        """Create and read a minimal synthetic CADET output file."""
        h5_path = temp_dir / "synthetic_output.h5"

        # Create minimal valid structure
        with h5py.File(h5_path, "w") as f:
            output = f.create_group("output")
            solution = output.create_group("solution")

            # Create solution times
            times = np.linspace(0, 100, 51)
            solution.create_dataset("SOLUTION_TIMES", data=times)

            # Create outlet for unit_002 (typical outlet unit)
            unit = solution.create_group("unit_002")
            outlet_data = np.random.rand(51, 1)  # 51 times, 1 component
            unit.create_dataset("SOLUTION_OUTLET", data=outlet_data)

        # Read it back
        result = read_solution(h5_path)

        assert len(result.solution_times) == 51
        assert np.allclose(result.solution_times, times)
        assert "unit_002" in result.outlet_profiles
        assert result.outlet_profiles["unit_002"].shape == (51, 1)
