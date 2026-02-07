"""Integration tests for NILT first-class solver.

Tests the full stack: extract_params, classify, solver, output, CLI.
No CADET binary required for these tests (pure Python).
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import h5py
import numpy as np
import pytest

from cadet_lab.config_gen.minimal_grm import create_minimal_grm_config
from cadet_lab.nilt.extract_params import extract_nilt_params
from cadet_lab.nilt.classify import classify_problem, ProblemClassification
from cadet_lab.nilt.solver import NiltSolver, NiltSolution
from cadet_lab.nilt.output import write_cadet_h5, write_json
from cadet_lab.nilt.benchmarks import advection_dispersion_transfer


@pytest.fixture
def grm_config(tmp_path):
    """Create a minimal GRM config HDF5 file for testing."""
    config_path = tmp_path / "test_grm.h5"
    create_minimal_grm_config(
        output_path=config_path,
        velocity=1e-3,
        col_dispersion=1e-6,
        col_length=0.1,
        col_porosity=0.37,
        par_porosity=0.33,
        par_radius=1e-5,
        film_diffusion=1e-5,
        pore_diffusion=1e-10,
        binding_ka=1.0,
        binding_kd=1.0,
        end_time=100.0,
        n_times=11,
    )
    return config_path


@pytest.fixture
def transport_only_config(tmp_path):
    """Create a config with NONE binding (transport only)."""
    config_path = tmp_path / "test_transport.h5"
    create_minimal_grm_config(
        output_path=config_path,
        velocity=1e-3,
        col_dispersion=1e-6,
        col_length=0.1,
        col_porosity=0.37,
        par_porosity=0.33,
        par_radius=1e-5,
        film_diffusion=1e-5,
        pore_diffusion=1e-10,
        binding_ka=0.0,
        binding_kd=0.0,
        end_time=500.0,
        n_times=51,
    )
    # Overwrite the binding model to NONE
    with h5py.File(config_path, "r+") as f:
        pt = f["input/model/unit_001/particle_type_000"]
        del pt["ADSORPTION_MODEL"]
        dt = h5py.string_dtype(encoding="ascii")
        pt.create_dataset("ADSORPTION_MODEL", data="NONE", dtype=dt)
    return config_path


class TestExtractParams:
    """Tests for extract_nilt_params."""

    def test_extract_from_grm_config(self, grm_config):
        """Extract params from GRM config and verify values match."""
        params = extract_nilt_params(grm_config)

        assert params["velocity"] == pytest.approx(1e-3)
        assert params["dispersion"] == pytest.approx(1e-6)
        assert params["length"] == pytest.approx(0.1)
        assert params["col_porosity"] == pytest.approx(0.37)
        assert params["par_porosity"] == pytest.approx(0.33)
        assert params["par_radius"] == pytest.approx(1e-5)
        assert params["film_diffusion"] == pytest.approx(1e-5)
        assert params["pore_diffusion"] == pytest.approx(1e-10)
        assert params["end_time"] == pytest.approx(100.0)
        assert params["n_comp"] == 1

    def test_extract_binding_model(self, grm_config):
        """Verify binding model and parameters are extracted."""
        params = extract_nilt_params(grm_config)

        assert params["binding_model"] == "LINEAR"
        assert params["binding_params"]["ka"] == pytest.approx(1.0)
        assert params["binding_params"]["kd"] == pytest.approx(1.0)

    def test_extract_transport_only(self, transport_only_config):
        """Verify NONE binding model is detected."""
        params = extract_nilt_params(transport_only_config)

        assert params["binding_model"] == "NONE"
        assert params["binding_params"] == {}
        assert params["end_time"] == pytest.approx(500.0)

    def test_file_not_found(self):
        """FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            extract_nilt_params("/nonexistent/path.h5")


class TestClassify:
    """Tests for classify_problem."""

    def test_classify_grm_no_binding(self, transport_only_config):
        """GRM with NONE binding should classify as grm_no_binding (has particles)."""
        params = extract_nilt_params(transport_only_config)
        cls = classify_problem(params)

        assert cls.problem_type == "grm_no_binding"
        assert cls.transfer_function_name == "grm_langmuir_transfer"
        assert cls.production_ready is True

    def test_classify_transport_only_no_particles(self):
        """Pure transport (no particles) should classify as transport_only."""
        params = {
            "binding_model": "NONE",
            "binding_params": {},
            "par_radius": None,
            "pore_diffusion": None,
            "film_diffusion": None,
        }
        cls = classify_problem(params)

        assert cls.problem_type == "transport_only"
        assert cls.transfer_function_name == "advection_dispersion_transfer"
        assert cls.production_ready is True

    def test_classify_linear_binding(self, grm_config):
        """Linear binding with GRM should classify as experimental."""
        params = extract_nilt_params(grm_config)
        cls = classify_problem(params)

        assert cls.problem_type == "transport_binding_linear"
        assert cls.transfer_function_name == "grm_langmuir_transfer"
        assert cls.production_ready is False
        assert len(cls.warnings) > 0

    def test_classify_langmuir(self):
        """Multi-component Langmuir classification."""
        params = {
            "binding_model": "MULTI_COMPONENT_LANGMUIR",
            "binding_params": {"ka": 1.0, "kd": 0.1, "qmax": 10.0},
            "par_radius": 1e-5,
            "pore_diffusion": 1e-10,
            "film_diffusion": 1e-5,
        }
        cls = classify_problem(params)

        assert cls.problem_type == "grm_langmuir"
        assert cls.transfer_function_name == "grm_langmuir_transfer"
        assert cls.production_ready is False

    def test_classify_sma(self):
        """Steric Mass Action classification."""
        params = {
            "binding_model": "STERIC_MASS_ACTION",
            "binding_params": {"ka": 1.0, "kd": 0.1, "Lambda": 10.0, "nu": 4.5},
        }
        cls = classify_problem(params)

        assert cls.problem_type == "grm_sma"
        assert cls.transfer_function_name == "grm_sma_transfer"

    def test_classify_unsupported(self):
        """Unknown binding model is unsupported."""
        params = {
            "binding_model": "MOBILE_PHASE_MODULATOR",
            "binding_params": {},
        }
        cls = classify_problem(params)

        assert cls.problem_type == "unsupported"
        assert cls.production_ready is False

    def test_classify_zero_binding_no_particles(self):
        """LINEAR with ka=kd=0 and no particles is transport-only."""
        params = {
            "binding_model": "LINEAR",
            "binding_params": {"ka": 0.0, "kd": 0.0},
            "par_radius": None,
            "pore_diffusion": None,
            "film_diffusion": None,
        }
        cls = classify_problem(params)

        assert cls.problem_type == "transport_only"
        assert cls.production_ready is True

    def test_classify_zero_binding_with_particles(self):
        """LINEAR with ka=kd=0 but GRM particles is grm_no_binding."""
        params = {
            "binding_model": "LINEAR",
            "binding_params": {"ka": 0.0, "kd": 0.0},
            "par_radius": 1e-5,
            "pore_diffusion": 1e-10,
            "film_diffusion": 1e-5,
        }
        cls = classify_problem(params)

        assert cls.problem_type == "grm_no_binding"
        assert cls.transfer_function_name == "grm_langmuir_transfer"
        assert cls.production_ready is True


class TestSolver:
    """Tests for NiltSolver."""

    def test_solve_direct(self):
        """Solve with direct transfer function (tight loop API)."""
        solver = NiltSolver(t_end=500.0)
        F = advection_dispersion_transfer(
            velocity=1e-3, dispersion=1e-6, length=0.1
        )
        solution = solver.solve(F)

        assert isinstance(solution, NiltSolution)
        assert solution.convergence.passed
        assert len(solution.t) > 0
        assert len(solution.y) == len(solution.t)
        assert np.all(np.isfinite(solution.y))
        assert solution.wall_time_us > 0
        assert solution.params.N > 0

    def test_solve_from_h5(self, transport_only_config):
        """End-to-end: HDF5 config -> solve_from_h5 -> verify solution."""
        solver = NiltSolver(t_end=500.0)
        solution = solver.solve_from_h5(transport_only_config)

        assert isinstance(solution, NiltSolution)
        assert solution.classification is not None
        assert solution.classification.problem_type == "grm_no_binding"
        assert len(solution.t) > 0
        assert len(solution.y) == len(solution.t)
        assert np.all(np.isfinite(solution.y))

    def test_solve_from_params(self, transport_only_config):
        """Solve from extracted params dict."""
        params = extract_nilt_params(transport_only_config)
        solver = NiltSolver(t_end=params["end_time"])
        solution = solver.solve_from_params(params)

        assert solution.classification.problem_type == "grm_no_binding"
        assert solution.convergence.passed
        assert len(solution.t) > 0

    def test_solve_metadata(self):
        """Metadata contains expected diagnostic keys."""
        solver = NiltSolver(t_end=500.0)
        F = advection_dispersion_transfer(
            velocity=1e-3, dispersion=1e-6, length=0.1
        )
        solution = solver.solve(F)

        assert "N" in solution.metadata
        assert "eps_im" in solution.metadata
        assert "E_N" in solution.metadata
        assert "timing_median_us" in solution.metadata


class TestOutput:
    """Tests for output writers."""

    def test_write_h5_readable(self, tmp_path):
        """Write NILT solution as HDF5, read back with read_solution."""
        from cadet_lab.telemetry.read_hdf5 import read_solution

        # Solve
        solver = NiltSolver(t_end=500.0)
        F = advection_dispersion_transfer(
            velocity=1e-3, dispersion=1e-6, length=0.1
        )
        solution = solver.solve(F)

        # Write
        output_path = tmp_path / "nilt_output.h5"
        write_cadet_h5(solution, output_path)
        assert output_path.exists()

        # Read back with CADET telemetry reader
        sol_data = read_solution(output_path)
        assert len(sol_data.solution_times) == len(solution.t)
        np.testing.assert_array_almost_equal(
            sol_data.solution_times, solution.t
        )

        # Check outlet profile exists and matches
        assert "unit_001" in sol_data.outlet_profiles
        outlet = sol_data.outlet_profiles["unit_001"]
        # Should be (n_times, 1) shape
        assert outlet.shape[0] == len(solution.t)
        np.testing.assert_array_almost_equal(
            outlet[:, 0], solution.y
        )

    def test_write_h5_diagnostics(self, tmp_path):
        """HDF5 output includes NILT diagnostics section."""
        solver = NiltSolver(t_end=500.0)
        F = advection_dispersion_transfer(
            velocity=1e-3, dispersion=1e-6, length=0.1
        )
        solution = solver.solve(F)

        output_path = tmp_path / "diag_output.h5"
        write_cadet_h5(solution, output_path)

        with h5py.File(output_path, "r") as f:
            assert "output/nilt_diagnostics" in f
            diag = f["output/nilt_diagnostics"]
            assert diag["N"][()] == solution.params.N
            assert diag["CONVERGED"][()] == int(solution.convergence.passed)

    def test_write_json(self, tmp_path):
        """Write NILT solution as JSON and verify structure."""
        solver = NiltSolver(t_end=500.0)
        F = advection_dispersion_transfer(
            velocity=1e-3, dispersion=1e-6, length=0.1
        )
        solution = solver.solve(F)

        output_path = tmp_path / "nilt_output.json"
        write_json(solution, output_path)
        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert "t" in data
        assert "y" in data
        assert len(data["t"]) == len(solution.t)
        assert len(data["y"]) == len(solution.y)
        assert "convergence" in data
        assert "params" in data
        assert data["params"]["N"] == solution.params.N


class TestCLI:
    """Tests for CLI entry point."""

    def test_cli_list(self):
        """CLI 'nilt list' should print transfer functions."""
        result = subprocess.run(
            [sys.executable, "-m", "cadet_lab.cli", "nilt", "list"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0
        assert "advection_dispersion_transfer" in result.stdout
        assert "grm_langmuir_transfer" in result.stdout

    def test_cli_classify(self, transport_only_config):
        """CLI 'nilt classify' should report problem type."""
        result = subprocess.run(
            [sys.executable, "-m", "cadet_lab.cli", "nilt", "classify",
             str(transport_only_config)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0
        assert "grm_no_binding" in result.stdout
        assert "Production ready" in result.stdout

    def test_cli_no_args(self):
        """CLI with no args prints help."""
        result = subprocess.run(
            [sys.executable, "-m", "cadet_lab.cli"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 1
