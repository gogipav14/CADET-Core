"""Stress test suite for CADET simulations.

Provides stress test case generators and a runner for batch execution.
"""

from .cases import (
    case_first_step_fail,
    case_sharp_front,
    case_discontinuous_section,
    case_stiff_binding,
    get_all_stress_cases,
)
from .runner import (
    run_stress_suite,
    run_single_case,
    StressSuiteResult,
    CaseResult,
)

__all__ = [
    "case_first_step_fail",
    "case_sharp_front",
    "case_discontinuous_section",
    "case_stiff_binding",
    "get_all_stress_cases",
    "run_stress_suite",
    "run_single_case",
    "StressSuiteResult",
    "CaseResult",
]
