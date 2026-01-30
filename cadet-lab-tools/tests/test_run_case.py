"""Tests for harness/run_case.py - CADET execution harness."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from cadet_lab.harness.run_case import run_case, RunResult


class TestRunResult:
    """Test RunResult dataclass."""

    def test_run_result_creation(self):
        """Test creating a RunResult with all fields."""
        result = RunResult(
            return_code=0,
            wall_time=1.5,
            failure_reason=None,
            n_times=101,
            outlet_shape=(101, 1),
            solver_stats={"NUM_STEPS": 500},
            stdout="Simulation complete",
            stderr="",
            log_file=None,
            input_file=Path("/tmp/input.h5"),
            output_file=Path("/tmp/output.h5"),
        )

        assert result.return_code == 0
        assert result.wall_time == 1.5
        assert result.failure_reason is None
        assert result.n_times == 101
        assert result.outlet_shape == (101, 1)
        assert result.solver_stats["NUM_STEPS"] == 500

    def test_run_result_success_property(self):
        """Test success property for different return codes."""
        success = RunResult(
            return_code=0, wall_time=1.0, failure_reason=None,
            n_times=10, outlet_shape=(10, 1), solver_stats=None,
            stdout="", stderr="", log_file=None,
            input_file=Path("/tmp/in.h5"), output_file=Path("/tmp/out.h5"),
        )
        assert success.success is True

        failure = RunResult(
            return_code=1, wall_time=0.5, failure_reason="CONVERGENCE_FAIL",
            n_times=0, outlet_shape=None, solver_stats=None,
            stdout="", stderr="Error", log_file=None,
            input_file=Path("/tmp/in.h5"), output_file=None,
        )
        assert failure.success is False

    def test_run_result_to_json(self):
        """Test JSON serialization of RunResult."""
        result = RunResult(
            return_code=0,
            wall_time=2.5,
            failure_reason=None,
            n_times=51,
            outlet_shape=(51, 2),
            solver_stats={"NUM_STEPS": 100, "NUM_ERR_TEST_FAILS": 2},
            stdout="OK",
            stderr="",
            log_file=None,
            input_file=Path("/tmp/input.h5"),
            output_file=Path("/tmp/output.h5"),
        )

        json_data = result.to_json()
        parsed = json.loads(json_data)

        assert parsed["return_code"] == 0
        assert parsed["wall_time"] == 2.5
        assert parsed["n_times"] == 51
        assert parsed["outlet_shape"] == [51, 2]
        assert parsed["solver_stats"]["NUM_STEPS"] == 100

    def test_run_result_save_report(self, temp_dir):
        """Test saving RunResult as JSON report."""
        result = RunResult(
            return_code=0,
            wall_time=1.0,
            failure_reason=None,
            n_times=10,
            outlet_shape=(10, 1),
            solver_stats=None,
            stdout="",
            stderr="",
            log_file=None,
            input_file=Path("/tmp/in.h5"),
            output_file=Path("/tmp/out.h5"),
        )

        report_path = temp_dir / "report.json"
        result.save_report(report_path)

        assert report_path.exists()
        with open(report_path) as f:
            loaded = json.load(f)
        assert loaded["return_code"] == 0


class TestRunCase:
    """Test run_case function."""

    def test_run_case_missing_cadet_cli(self, temp_dir):
        """Test that missing cadet-cli raises appropriate error."""
        fake_input = temp_dir / "input.h5"
        fake_input.touch()

        with pytest.raises(FileNotFoundError, match="cadet-cli"):
            run_case(
                input_file=fake_input,
                cadet_cli_path="/nonexistent/cadet-cli",
                output_dir=temp_dir,
            )

    def test_run_case_missing_input_file(self, temp_dir, cadet_cli_path):
        """Test that missing input file raises appropriate error."""
        if cadet_cli_path is None:
            pytest.skip("cadet-cli not available")

        fake_input = temp_dir / "nonexistent.h5"

        with pytest.raises(FileNotFoundError, match="input"):
            run_case(
                input_file=fake_input,
                cadet_cli_path=cadet_cli_path,
                output_dir=temp_dir,
            )

    @patch("subprocess.run")
    def test_run_case_captures_subprocess_output(self, mock_run, temp_dir):
        """Test that stdout/stderr are captured from subprocess."""
        # Create fake input file
        input_file = temp_dir / "input.h5"
        input_file.touch()

        # Mock subprocess result
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Simulation completed successfully",
            stderr="",
        )

        # Create fake output file that would be generated
        output_file = temp_dir / "input_output.h5"

        with patch("cadet_lab.harness.run_case._read_output_if_exists") as mock_read:
            mock_read.return_value = (101, (101, 1), None)

            # Create the output file to simulate CADET creating it
            import h5py
            import numpy as np
            with h5py.File(output_file, "w") as f:
                output = f.create_group("output")
                solution = output.create_group("solution")
                solution.create_dataset("SOLUTION_TIMES", data=np.linspace(0, 100, 101))

            result = run_case(
                input_file=input_file,
                cadet_cli_path="/fake/cadet-cli",
                output_dir=temp_dir,
                _skip_cli_check=True,  # Skip CLI existence check for mocking
            )

        assert "Simulation completed" in result.stdout

    def test_run_case_returns_wall_time(self, temp_dir):
        """Test that run_case measures and returns wall time."""
        # This test verifies the wall_time field is populated
        # Full integration test requires actual cadet-cli
        pass  # Covered by integration test


class TestRunCaseIntegration:
    """Integration tests that require actual cadet-cli."""

    @pytest.mark.integration
    def test_run_minimal_simulation(self, cadet_cli_path, temp_dir):
        """Integration test: run a minimal simulation end-to-end."""
        if cadet_cli_path is None:
            pytest.skip("cadet-cli not available")

        from cadet_lab.config_gen import create_minimal_grm_config

        # Generate minimal config
        input_file = temp_dir / "minimal_test.h5"
        create_minimal_grm_config(
            output_path=input_file,
            n_times=11,
            end_time=10.0,
        )

        # Run simulation
        result = run_case(
            input_file=input_file,
            cadet_cli_path=cadet_cli_path,
            output_dir=temp_dir,
        )

        # Verify result
        assert result.return_code == 0
        assert result.wall_time > 0
        assert result.n_times == 11
        assert result.outlet_shape is not None
        assert result.output_file.exists()
