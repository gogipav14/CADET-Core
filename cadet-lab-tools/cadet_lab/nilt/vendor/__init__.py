"""Vendored nilt-cfl library.

Source: https://github.com/gogipav14/nilt-cfl
License: MIT

This module provides CFL-informed FFT-based numerical inverse Laplace transform.
"""

from .nilt_fft import (
    fft_nilt,
    fft_nilt_one_sided,
    eps_im,  # Deprecated - use one_sided_imag_ratio instead
    one_sided_imag_ratio,
    epsilon_im_paper,
    n_doubling_error,
)
from .tuner import tune_params, refine_until_accept, check_cfl_feasibility, TunedParams
from .problems import get_problem, get_all_problems, Problem

__all__ = [
    # Core NILT functions
    "fft_nilt",
    "fft_nilt_one_sided",
    "n_doubling_error",
    # Diagnostics (ε_Im)
    "one_sided_imag_ratio",  # Im/Re of one-sided IFFT (NOT paper ε_Im)
    "epsilon_im_paper",       # Paper-compliant ε_Im using irfft
    "eps_im",                 # Deprecated alias for one_sided_imag_ratio
    # Parameter tuning
    "tune_params",
    "refine_until_accept",
    "check_cfl_feasibility",
    "TunedParams",
    # Benchmark problems
    "get_problem",
    "get_all_problems",
    "Problem",
]
