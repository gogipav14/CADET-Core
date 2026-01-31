"""Tests for stress_suite module.

Tests verify deterministic generation of stress test cases (not execution).
"""

import tempfile
from pathlib import Path

import h5py
import numpy as np
import pytest

from cadet_lab.stress_suite import (
    case_first_step_fail,
    case_sharp_front,
    case_discontinuous_section,
    case_stiff_binding,
    get_all_stress_cases,
    StressSuiteResult,
    CaseResult,
)


class TestCaseFirstStepFail:
    """Tests for case_first_step_fail generator."""

    def test_creates_valid_hdf5(self, tmp_path):
        """Generated file is valid HDF5 with expected structure."""
        output_path = tmp_path / "first_step_fail.h5"
        result = case_first_step_fail(output_path)

        assert result.exists()
        with h5py.File(result, "r") as f:
            # Check required groups exist
            assert "input/model" in f
            assert "input/solver" in f
            assert "input/return" in f

    def test_large_init_step_size(self, tmp_path):
        """Default config has large init_step_size."""
        output_path = tmp_path / "first_step_fail.h5"
        case_first_step_fail(output_path)

        with h5py.File(output_path, "r") as f:
            init_step = f["input/solver/time_integrator/INIT_STEP_SIZE"][()]
            # Default is 1.0, which is very large for stiff systems
            assert init_step >= 1.0

    def test_custom_init_step_size(self, tmp_path):
        """Custom init_step_size is applied."""
        output_path = tmp_path / "first_step_fail.h5"
        case_first_step_fail(output_path, init_step_size=5.0)

        with h5py.File(output_path, "r") as f:
            init_step = f["input/solver/time_integrator/INIT_STEP_SIZE"][()]
            assert init_step == pytest.approx(5.0)

    def test_deterministic_generation(self, tmp_path):
        """Same inputs produce identical files."""
        output1 = tmp_path / "first_step_fail_1.h5"
        output2 = tmp_path / "first_step_fail_2.h5"

        case_first_step_fail(output1, init_step_size=2.0)
        case_first_step_fail(output2, init_step_size=2.0)

        # Compare key parameters
        with h5py.File(output1, "r") as f1, h5py.File(output2, "r") as f2:
            init1 = f1["input/solver/time_integrator/INIT_STEP_SIZE"][()]
            init2 = f2["input/solver/time_integrator/INIT_STEP_SIZE"][()]
            assert init1 == init2

            abstol1 = f1["input/solver/time_integrator/ABSTOL"][()]
            abstol2 = f2["input/solver/time_integrator/ABSTOL"][()]
            assert abstol1 == abstol2


class TestCaseSharpFront:
    """Tests for case_sharp_front generator."""

    def test_creates_valid_hdf5(self, tmp_path):
        """Generated file is valid HDF5 with expected structure."""
        output_path = tmp_path / "sharp_front.h5"
        result = case_sharp_front(output_path)

        assert result.exists()
        with h5py.File(result, "r") as f:
            assert "input/model" in f
            assert "input/solver" in f

    def test_high_peclet_number(self, tmp_path):
        """Config achieves high Peclet number via low dispersion."""
        output_path = tmp_path / "sharp_front.h5"
        peclet = 1000.0
        case_sharp_front(output_path, peclet=peclet)

        with h5py.File(output_path, "r") as f:
            col_disp = f["input/model/unit_001/COL_DISPERSION"][()]
            velocity = f["input/model/unit_001/VELOCITY"][()]
            col_length = f["input/model/unit_001/COL_LENGTH"][()]

            # Pe = v*L/D, so D = v*L/Pe
            expected_disp = velocity * col_length / peclet
            assert col_disp == pytest.approx(expected_disp, rel=1e-6)

    def test_coarse_discretization(self, tmp_path):
        """Config uses coarse spatial discretization."""
        output_path = tmp_path / "sharp_front.h5"
        n_col = 8
        case_sharp_front(output_path, n_col=n_col)

        with h5py.File(output_path, "r") as f:
            nelem = f["input/model/unit_001/discretization/NELEM"][()]
            assert nelem == n_col

    def test_custom_discretization(self, tmp_path):
        """Custom n_col is applied."""
        output_path = tmp_path / "sharp_front.h5"
        case_sharp_front(output_path, n_col=4)

        with h5py.File(output_path, "r") as f:
            nelem = f["input/model/unit_001/discretization/NELEM"][()]
            assert nelem == 4

    def test_deterministic_generation(self, tmp_path):
        """Same inputs produce identical files."""
        output1 = tmp_path / "sharp_front_1.h5"
        output2 = tmp_path / "sharp_front_2.h5"

        case_sharp_front(output1, peclet=500.0, n_col=10)
        case_sharp_front(output2, peclet=500.0, n_col=10)

        with h5py.File(output1, "r") as f1, h5py.File(output2, "r") as f2:
            disp1 = f1["input/model/unit_001/COL_DISPERSION"][()]
            disp2 = f2["input/model/unit_001/COL_DISPERSION"][()]
            assert disp1 == disp2

            nelem1 = f1["input/model/unit_001/discretization/NELEM"][()]
            nelem2 = f2["input/model/unit_001/discretization/NELEM"][()]
            assert nelem1 == nelem2


class TestCaseDiscontinuousSection:
    """Tests for case_discontinuous_section generator."""

    def test_creates_valid_hdf5(self, tmp_path):
        """Generated file is valid HDF5 with expected structure."""
        output_path = tmp_path / "discontinuous.h5"
        result = case_discontinuous_section(output_path)

        assert result.exists()
        with h5py.File(result, "r") as f:
            assert "input/model" in f
            assert "input/solver" in f

    def test_two_sections(self, tmp_path):
        """Config has two sections."""
        output_path = tmp_path / "discontinuous.h5"
        case_discontinuous_section(output_path)

        with h5py.File(output_path, "r") as f:
            nsec = f["input/solver/sections/NSEC"][()]
            assert nsec == 2

    def test_discontinuous_transition(self, tmp_path):
        """Section continuity is set to discontinuous."""
        output_path = tmp_path / "discontinuous.h5"
        case_discontinuous_section(output_path)

        with h5py.File(output_path, "r") as f:
            continuity = f["input/solver/sections/SECTION_CONTINUITY"][()]
            # 0 means discontinuous
            assert np.array(continuity).flatten()[0] == 0

    def test_section_times(self, tmp_path):
        """Section times match pulse_duration and default end_time."""
        output_path = tmp_path / "discontinuous.h5"
        pulse_duration = 2.0
        # end_time defaults to 10.0 in the function
        case_discontinuous_section(output_path, pulse_duration=pulse_duration)

        with h5py.File(output_path, "r") as f:
            section_times = f["input/solver/sections/SECTION_TIMES"][()]
            assert section_times[0] == pytest.approx(0.0)
            assert section_times[1] == pytest.approx(pulse_duration)
            assert section_times[2] == pytest.approx(10.0)  # default end_time

    def test_concentration_ratio(self, tmp_path):
        """Second section has lower concentration by specified ratio."""
        output_path = tmp_path / "discontinuous.h5"
        ratio = 100.0
        high_conc = 1.0
        case_discontinuous_section(
            output_path, concentration_ratio=ratio, inlet_concentration=high_conc
        )

        with h5py.File(output_path, "r") as f:
            # First section (sec_000) has high concentration
            sec0_conc = f["input/model/unit_000/sec_000/CONST_COEFF"][()]
            # Second section (sec_001) has low concentration
            sec1_conc = f["input/model/unit_000/sec_001/CONST_COEFF"][()]

            expected_high = high_conc
            expected_low = high_conc / ratio

            assert float(np.array(sec0_conc).flatten()[0]) == pytest.approx(expected_high)
            assert float(np.array(sec1_conc).flatten()[0]) == pytest.approx(expected_low)

    def test_deterministic_generation(self, tmp_path):
        """Same inputs produce identical files."""
        output1 = tmp_path / "discontinuous_1.h5"
        output2 = tmp_path / "discontinuous_2.h5"

        case_discontinuous_section(output1, pulse_duration=3.0, concentration_ratio=50.0)
        case_discontinuous_section(output2, pulse_duration=3.0, concentration_ratio=50.0)

        with h5py.File(output1, "r") as f1, h5py.File(output2, "r") as f2:
            times1 = f1["input/solver/sections/SECTION_TIMES"][()]
            times2 = f2["input/solver/sections/SECTION_TIMES"][()]
            np.testing.assert_array_equal(times1, times2)

            sec1_1 = f1["input/model/unit_000/sec_001/CONST_COEFF"][()]
            sec1_2 = f2["input/model/unit_000/sec_001/CONST_COEFF"][()]
            np.testing.assert_array_equal(sec1_1, sec1_2)


class TestCaseStiffBinding:
    """Tests for case_stiff_binding generator."""

    def test_creates_valid_hdf5(self, tmp_path):
        """Generated file is valid HDF5 with expected structure."""
        output_path = tmp_path / "stiff_binding.h5"
        result = case_stiff_binding(output_path)

        assert result.exists()
        with h5py.File(result, "r") as f:
            assert "input/model" in f
            assert "input/solver" in f
            assert "input/return" in f

    def test_high_binding_rate(self, tmp_path):
        """Default config has high binding rate constants."""
        output_path = tmp_path / "stiff_binding.h5"
        case_stiff_binding(output_path)

        with h5py.File(output_path, "r") as f:
            ka = f["input/model/unit_001/adsorption/LIN_KA"][()]
            kd = f["input/model/unit_001/adsorption/LIN_KD"][()]
            # Default ka=1e4, kd=1e2
            assert float(np.array(ka).flatten()[0]) >= 1e4
            assert float(np.array(kd).flatten()[0]) >= 1e2

    def test_custom_binding_rates(self, tmp_path):
        """Custom binding rates are applied."""
        output_path = tmp_path / "stiff_binding.h5"
        case_stiff_binding(output_path, binding_ka=1e5, binding_kd=1e3)

        with h5py.File(output_path, "r") as f:
            ka = f["input/model/unit_001/adsorption/LIN_KA"][()]
            kd = f["input/model/unit_001/adsorption/LIN_KD"][()]
            assert float(np.array(ka).flatten()[0]) == pytest.approx(1e5)
            assert float(np.array(kd).flatten()[0]) == pytest.approx(1e3)

    def test_tight_tolerances(self, tmp_path):
        """Config uses tight tolerances for stiff system."""
        output_path = tmp_path / "stiff_binding.h5"
        case_stiff_binding(output_path)

        with h5py.File(output_path, "r") as f:
            abstol = f["input/solver/time_integrator/ABSTOL"][()]
            reltol = f["input/solver/time_integrator/RELTOL"][()]
            # Expect tight tolerances: abstol=1e-10, reltol=1e-8
            assert abstol <= 1e-9
            assert reltol <= 1e-7

    def test_deterministic_generation(self, tmp_path):
        """Same inputs produce identical files."""
        output1 = tmp_path / "stiff_binding_1.h5"
        output2 = tmp_path / "stiff_binding_2.h5"

        case_stiff_binding(output1, binding_ka=5e4, binding_kd=5e2)
        case_stiff_binding(output2, binding_ka=5e4, binding_kd=5e2)

        with h5py.File(output1, "r") as f1, h5py.File(output2, "r") as f2:
            ka1 = f1["input/model/unit_001/adsorption/LIN_KA"][()]
            ka2 = f2["input/model/unit_001/adsorption/LIN_KA"][()]
            np.testing.assert_array_equal(ka1, ka2)

            abstol1 = f1["input/solver/time_integrator/ABSTOL"][()]
            abstol2 = f2["input/solver/time_integrator/ABSTOL"][()]
            assert abstol1 == abstol2


class TestGetAllStressCases:
    """Tests for get_all_stress_cases registry."""

    def test_returns_list(self):
        """Returns a list of case definitions."""
        cases = get_all_stress_cases()
        assert isinstance(cases, list)
        assert len(cases) == 4

    def test_case_structure(self):
        """Each case is a tuple of (name, func, kwargs)."""
        cases = get_all_stress_cases()
        for case in cases:
            assert len(case) == 3
            name, func, kwargs = case
            assert isinstance(name, str)
            assert callable(func)
            assert isinstance(kwargs, dict)

    def test_case_names(self):
        """Expected case names are present."""
        cases = get_all_stress_cases()
        names = [c[0] for c in cases]
        assert "first_step_fail" in names
        assert "sharp_front" in names
        assert "discontinuous_section" in names
        assert "stiff_binding" in names

    def test_all_cases_callable(self, tmp_path):
        """All registered generators can produce files."""
        cases = get_all_stress_cases()
        for name, func, kwargs in cases:
            output_path = tmp_path / f"{name}.h5"
            result = func(output_path=output_path, **kwargs)
            assert result.exists(), f"Case {name} did not produce output file"


class TestCaseResult:
    """Tests for CaseResult dataclass."""

    def test_to_dict(self):
        """CaseResult can be converted to dict."""
        result = CaseResult(
            name="test_case",
            success=True,
            return_code=0,
            wall_time=1.5,
            failure_reason=None,
            num_steps=100,
            num_err_test_fails=5,
            num_conv_fails=2,
            input_file="/path/to/input.h5",
            output_file="/path/to/output.h5",
        )
        d = result.to_dict()
        assert d["name"] == "test_case"
        assert d["success"] is True
        assert d["return_code"] == 0
        assert d["wall_time"] == 1.5
        assert d["num_steps"] == 100

    def test_optional_fields(self):
        """Optional fields can be None."""
        result = CaseResult(
            name="failed_case",
            success=False,
            return_code=1,
            wall_time=0.0,
            failure_reason="EXECUTION_ERROR: timeout",
            num_steps=None,
            num_err_test_fails=None,
            num_conv_fails=None,
            input_file="/path/to/input.h5",
            output_file=None,
        )
        d = result.to_dict()
        assert d["num_steps"] is None
        assert d["output_file"] is None
        assert d["failure_reason"] == "EXECUTION_ERROR: timeout"


class TestStressSuiteResult:
    """Tests for StressSuiteResult dataclass."""

    def test_to_dict(self):
        """StressSuiteResult can be converted to dict."""
        result = StressSuiteResult(
            timestamp="2025-01-01T00:00:00",
            total_cases=3,
            passed=2,
            failed=1,
            failure_rate=1 / 3,
            median_wall_time=1.5,
            median_err_test_fails=5.0,
            median_conv_fails=2.0,
            case_results={"case1": {"success": True}},
        )
        d = result.to_dict()
        assert d["total_cases"] == 3
        assert d["passed"] == 2
        assert d["failed"] == 1
        assert d["failure_rate"] == pytest.approx(1 / 3)

    def test_to_json(self):
        """StressSuiteResult can be serialized to JSON."""
        result = StressSuiteResult(
            timestamp="2025-01-01T00:00:00",
            total_cases=2,
            passed=2,
            failed=0,
            failure_rate=0.0,
            median_wall_time=1.0,
            median_err_test_fails=None,
            median_conv_fails=None,
            case_results={},
        )
        json_str = result.to_json()
        assert '"total_cases": 2' in json_str
        assert '"passed": 2' in json_str

    def test_save(self, tmp_path):
        """StressSuiteResult can be saved to file."""
        result = StressSuiteResult(
            timestamp="2025-01-01T00:00:00",
            total_cases=1,
            passed=1,
            failed=0,
            failure_rate=0.0,
            median_wall_time=0.5,
            median_err_test_fails=0.0,
            median_conv_fails=0.0,
            case_results={},
        )
        output_path = tmp_path / "results.json"
        result.save(output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert '"total_cases": 1' in content
