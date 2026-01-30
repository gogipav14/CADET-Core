"""NILT verification pack using CFL-informed FFT-NILT.

This module provides numerical inverse Laplace transform capabilities
for verifying CADET simulations against analytical reference solutions.

The implementation uses the vendored nilt-cfl library from:
https://github.com/gogipav14/nilt-cfl

Key Features:
- CFL-informed parameter selection (Algorithm 1)
- FFT-based Dubner-Abate/Hsu-Dranoff NILT
- Two ε_Im diagnostics:
  - one_sided_imag_ratio: Im/Re of one-sided IFFT (fast, high values normal)
  - epsilon_im_paper: Paper-compliant ε_Im using irfft (should be ~1e-10)
- N-doubling convergence test
- CADET-specific benchmark transfer functions
"""

# Re-export vendored library functions
from .vendor import (
    fft_nilt,
    fft_nilt_one_sided,
    # Diagnostics
    one_sided_imag_ratio,  # Im/Re of one-sided IFFT (NOT paper ε_Im)
    epsilon_im_paper,       # Paper-compliant ε_Im using irfft
    eps_im,                 # Deprecated alias for one_sided_imag_ratio
    n_doubling_error,
    # Parameter tuning
    tune_params,
    refine_until_accept,
    check_cfl_feasibility,
    TunedParams,
    # Benchmark problems
    get_problem,
    get_all_problems,
    Problem,
)

# High-level convergence wrappers
from .convergence import (
    epsilon_im_test,
    n_doubling_test,
    NiltConvergenceResult,
)

# CADET-specific benchmarks
from .benchmarks import (
    get_benchmark_functions,
    advection_dispersion_transfer,
    langmuir_column_transfer,
    grm_moment_transfer,
)

__all__ = [
    # Vendored core NILT
    "fft_nilt",
    "fft_nilt_one_sided",
    "n_doubling_error",
    # Diagnostics (ε_Im)
    "one_sided_imag_ratio",  # Im/Re of one-sided IFFT (fast, high values normal)
    "epsilon_im_paper",       # Paper-compliant ε_Im (should be ~1e-10)
    "eps_im",                 # Deprecated alias
    # Parameter tuning
    "tune_params",
    "refine_until_accept",
    "check_cfl_feasibility",
    "TunedParams",
    # Benchmark problems
    "get_problem",
    "get_all_problems",
    "Problem",
    # High-level wrappers
    "epsilon_im_test",
    "n_doubling_test",
    "NiltConvergenceResult",
    # CADET benchmarks
    "get_benchmark_functions",
    "advection_dispersion_transfer",
    "langmuir_column_transfer",
    "grm_moment_transfer",
]
