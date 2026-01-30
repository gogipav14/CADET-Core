"""Smoke tests - end-to-end integration tests for cadet-lab-tools."""

import json
import pytest
from pathlib import Path

from cadet_lab.config_gen import create_minimal_grm_config
from cadet_lab.harness import run_case, RunResult
from cadet_lab.telemetry import read_solution, compute_kpis


class TestMinimalConfigGenerator:
    """Test the minimal GRM config generator."""

    def test_creates_valid_hdf5(self, temp_dir):
        """Test that config generator creates a valid HDF5 file."""
        import h5py

        output_path = temp_dir / "test_config.h5"
        create_minimal_grm_config(
            output_path=output_path,
            n_times=11,
            end_time=10.0,
        )

        assert output_path.exists()

        # Verify it's a valid HDF5 file
        with h5py.File(output_path, "r") as f:
            # Check required structure
            assert "input" in f
            assert "model" in f["input"]
            assert "solver" in f["input"]

    def test_config_has_user_solution_times(self, temp_dir):
        """Test that config includes user_solution_times."""
        import h5py
        import numpy as np

        output_path = temp_dir / "test_config.h5"
        create_minimal_grm_config(
            output_path=output_path,
            n_times=21,
            end_time=100.0,
        )

        with h5py.File(output_path, "r") as f:
            times = f["input/solver/USER_SOLUTION_TIMES"][:]
            assert len(times) == 21
            assert times[0] == 0.0
            assert times[-1] == 100.0

    def test_config_has_tolerances(self, temp_dir):
        """Test that config includes solver tolerances."""
        import h5py

        output_path = temp_dir / "test_config.h5"
        create_minimal_grm_config(
            output_path=output_path,
            n_times=11,
            end_time=10.0,
            abstol=1e-8,
            reltol=1e-6,
        )

        with h5py.File(output_path, "r") as f:
            time_int = f["input/solver/time_integrator"]
            assert time_int["ABSTOL"][()] == pytest.approx(1e-8)
            assert time_int["RELTOL"][()] == pytest.approx(1e-6)

    def test_config_structure_inlet_grm_outlet(self, temp_dir):
        """Test that config has INLET -> GRM -> OUTLET structure."""
        import h5py

        output_path = temp_dir / "test_config.h5"
        create_minimal_grm_config(output_path=output_path)

        with h5py.File(output_path, "r") as f:
            model = f["input/model"]
            assert model["NUNITS"][()] == 3

            # Check unit types
            assert model["unit_000/UNIT_TYPE"][()].decode() == "INLET"
            assert model["unit_001/UNIT_TYPE"][()].decode() == "GENERAL_RATE_MODEL"
            assert model["unit_002/UNIT_TYPE"][()].decode() == "OUTLET"


@pytest.mark.integration
class TestSmokeIntegration:
    """Full integration smoke tests requiring cadet-cli."""

    def test_full_workflow(self, cadet_cli_path, temp_dir):
        """Test complete workflow: config -> run -> read -> report."""
        if cadet_cli_path is None:
            pytest.skip("cadet-cli not available")

        # Step 1: Generate config
        input_file = temp_dir / "smoke_test.h5"
        create_minimal_grm_config(
            output_path=input_file,
            n_times=11,
            end_time=10.0,
        )
        assert input_file.exists()

        # Step 2: Run simulation
        result = run_case(
            input_file=input_file,
            cadet_cli_path=cadet_cli_path,
            output_dir=temp_dir,
        )

        # Step 3: Verify run succeeded
        assert result.return_code == 0, f"Simulation failed: {result.stderr}"
        assert result.wall_time > 0
        assert result.output_file is not None
        assert result.output_file.exists()

        # Step 4: Read output
        solution = read_solution(result.output_file)
        assert len(solution.solution_times) == 11
        assert len(solution.outlet_profiles) > 0

        # Step 5: Compute KPIs
        kpis = compute_kpis(result, solution)
        assert kpis.success is True
        assert kpis.n_solution_times == 11

        # Step 6: Save report
        report_file = temp_dir / "report.json"
        result.save_report(report_file)
        assert report_file.exists()

        with open(report_file) as f:
            report = json.load(f)
        assert report["return_code"] == 0
        assert report["n_times"] == 11

    def test_smoke_produces_artifacts(self, cadet_cli_path, temp_dir):
        """Acceptance test: smoke case produces report JSON and HDF5 output."""
        if cadet_cli_path is None:
            pytest.skip("cadet-cli not available")

        # Generate and run
        input_file = temp_dir / "artifact_test.h5"
        create_minimal_grm_config(output_path=input_file, n_times=6, end_time=5.0)

        result = run_case(
            input_file=input_file,
            cadet_cli_path=cadet_cli_path,
            output_dir=temp_dir,
        )

        # Save report
        report_file = temp_dir / "artifact_test_report.json"
        result.save_report(report_file)

        # Verify artifacts exist
        assert result.output_file.exists(), "HDF5 output should exist"
        assert report_file.exists(), "Report JSON should exist"

        # Verify report content
        with open(report_file) as f:
            report = json.load(f)

        required_fields = [
            "return_code",
            "wall_time",
            "failure_reason",
            "n_times",
            "outlet_shape",
            "solver_stats",
        ]
        for field in required_fields:
            assert field in report, f"Report missing field: {field}"


class TestReadReferenceFiles:
    """Test reading existing CADET reference files."""

    def test_read_existing_ref_file(self, sample_ref_h5):
        """Test reading an existing reference HDF5 file."""
        solution = read_solution(sample_ref_h5)

        assert solution.solution_times is not None
        assert len(solution.solution_times) > 0
        assert len(solution.outlet_profiles) > 0

    def test_ref_file_outlet_shape(self, sample_ref_h5):
        """Test that outlet profiles have correct shape."""
        solution = read_solution(sample_ref_h5)

        for unit_id, profile in solution.outlet_profiles.items():
            # First dimension should match solution times
            assert profile.shape[0] == len(solution.solution_times)
