"""Vendored nilt-cfl library.

Source: https://github.com/gogipav14/nilt-cfl
License: MIT

This module provides CFL-informed FFT-based numerical inverse Laplace transform.
"""

from .nilt_fft import fft_nilt, fft_nilt_one_sided, eps_im, n_doubling_error
from .tuner import tune_params, refine_until_accept, check_cfl_feasibility, TunedParams
from .problems import get_problem, get_all_problems, Problem

__all__ = [
    "fft_nilt",
    "fft_nilt_one_sided",
    "eps_im",
    "n_doubling_error",
    "tune_params",
    "refine_until_accept",
    "check_cfl_feasibility",
    "TunedParams",
    "get_problem",
    "get_all_problems",
    "Problem",
]
