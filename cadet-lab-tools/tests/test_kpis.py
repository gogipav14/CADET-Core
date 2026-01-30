"""Tests for telemetry/kpis.py - KPI computation."""

import numpy as np
import pytest
from pathlib import Path

from cadet_lab.telemetry.kpis import (
    compute_kpis,
    RunKPIs,
    determine_failure_reason,
    compute_profile_norms,
)
from cadet_lab.harness.run_case import RunResult


class TestDetermineFailureReason:
    """Test failure reason detection."""

    def test_success_returns_none(self):
        """Successful run should have no failure reason."""
        reason = determine_failure_reason(
            return_code=0,
            stdout="Simulation completed",
            stderr="",
            solver_stats=None,
        )
        assert reason is None

    def test_nonzero_return_code(self):
        """Non-zero return code indicates failure."""
        reason = determine_failure_reason(
            return_code=1,
            stdout="",
            stderr="Error occurred",
            solver_stats=None,
        )
        assert reason is not None
        assert "NONZERO_EXIT" in reason or "ERROR" in reason.upper()

    def test_convergence_failure_from_log(self):
        """Detect convergence failure from log output."""
        reason = determine_failure_reason(
            return_code=1,
            stdout="IDA_CONV_FAIL: Newton iteration failed to converge",
            stderr="",
            solver_stats=None,
        )
        assert reason is not None
        assert "CONV" in reason.upper()

    def test_error_test_failure_from_log(self):
        """Detect error test failure from log output."""
        reason = determine_failure_reason(
            return_code=1,
            stdout="IDA_ERR_FAIL: Error test failed repeatedly",
            stderr="",
            solver_stats=None,
        )
        assert reason is not None
        assert "ERR" in reason.upper()

    def test_max_steps_exceeded_from_log(self):
        """Detect max steps exceeded from log output."""
        reason = determine_failure_reason(
            return_code=1,
            stdout="Maximum number of steps exceeded",
            stderr="",
            solver_stats=None,
        )
        assert reason is not None
        assert "MAX" in reason.upper() or "STEP" in reason.upper()

    def test_failure_from_solver_stats(self):
        """Detect failure from solver statistics."""
        reason = determine_failure_reason(
            return_code=1,
            stdout="",
            stderr="",
            solver_stats={"NUM_ERR_TEST_FAILS": 100, "NUM_CONV_FAILS": 50},
        )
        assert reason is not None


class TestComputeProfileNorms:
    """Test profile norm computation."""

    def test_compute_norms_1d(self):
        """Compute norms for 1D profile."""
        profile = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        norms = compute_profile_norms(profile)

        assert "l2" in norms
        assert "linf" in norms
        assert "mean" in norms
        assert norms["linf"] == 5.0
        assert norms["mean"] == 3.0

    def test_compute_norms_2d(self):
        """Compute norms for 2D profile (time x components)."""
        profile = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        norms = compute_profile_norms(profile)

        assert "l2" in norms
        assert norms["linf"] == 6.0

    def test_compute_norms_empty(self):
        """Handle empty profile gracefully."""
        profile = np.array([])
        norms = compute_profile_norms(profile)

        assert norms["l2"] == 0.0
        assert norms["linf"] == 0.0


class TestComputeKpis:
    """Test full KPI computation from RunResult."""

    def test_compute_kpis_success(self):
        """Compute KPIs for successful run."""
        result = RunResult(
            return_code=0,
            wall_time=2.5,
            failure_reason=None,
            n_times=101,
            outlet_shape=(101, 1),
            solver_stats={"NUM_STEPS": 500, "NUM_ERR_TEST_FAILS": 2},
            stdout="Simulation complete",
            stderr="",
            log_file=None,
            input_file=Path("/tmp/in.h5"),
            output_file=Path("/tmp/out.h5"),
        )

        kpis = compute_kpis(result)

        assert isinstance(kpis, RunKPIs)
        assert kpis.success is True
        assert kpis.wall_time == 2.5
        assert kpis.failure_reason is None
        assert kpis.n_solution_times == 101

    def test_compute_kpis_failure(self):
        """Compute KPIs for failed run."""
        result = RunResult(
            return_code=1,
            wall_time=0.5,
            failure_reason=None,  # Let compute_kpis determine it
            n_times=0,
            outlet_shape=None,
            solver_stats=None,
            stdout="IDA_CONV_FAIL",
            stderr="",
            log_file=None,
            input_file=Path("/tmp/in.h5"),
            output_file=None,
        )

        kpis = compute_kpis(result)

        assert kpis.success is False
        assert kpis.failure_reason is not None

    def test_compute_kpis_with_solver_stats(self):
        """Compute KPIs including solver statistics."""
        result = RunResult(
            return_code=0,
            wall_time=3.0,
            failure_reason=None,
            n_times=51,
            outlet_shape=(51, 2),
            solver_stats={
                "NUM_STEPS": 1000,
                "NUM_RHS_EVALS": 2500,
                "NUM_ERR_TEST_FAILS": 5,
                "NUM_CONV_FAILS": 1,
            },
            stdout="",
            stderr="",
            log_file=None,
            input_file=Path("/tmp/in.h5"),
            output_file=Path("/tmp/out.h5"),
        )

        kpis = compute_kpis(result)

        assert kpis.num_steps == 1000
        assert kpis.num_rhs_evals == 2500
        assert kpis.num_err_test_fails == 5
        assert kpis.num_conv_fails == 1
        # Reject ratio = err_test_fails / num_steps
        assert kpis.reject_ratio == pytest.approx(5 / 1000)


class TestRunKPIs:
    """Test RunKPIs dataclass."""

    def test_run_kpis_to_dict(self):
        """Test dictionary conversion."""
        kpis = RunKPIs(
            success=True,
            wall_time=1.5,
            failure_reason=None,
            n_solution_times=51,
            outlet_shape=(51, 1),
            num_steps=500,
            num_rhs_evals=1200,
            num_err_test_fails=3,
            num_conv_fails=0,
            reject_ratio=0.006,
            profile_norms={"unit_002": {"l2": 5.5, "linf": 1.2}},
        )

        d = kpis.to_dict()

        assert d["success"] is True
        assert d["wall_time"] == 1.5
        assert d["num_steps"] == 500
        assert d["profile_norms"]["unit_002"]["l2"] == 5.5
