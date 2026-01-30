"""NILT verification pack using CFL-informed FFT-NILT.

This module provides numerical inverse Laplace transform capabilities
for verifying CADET simulations against analytical reference solutions.

The implementation uses the vendored nilt-cfl library from:
https://github.com/gogipav14/nilt-cfl

Key Features:
- CFL-informed parameter selection (Algorithm 1)
- FFT-based Dubner-Abate/Hsu-Dranoff NILT
- ε_Im diagnostic for imaginary leakage detection
- N-doubling convergence test
- CADET-specific benchmark transfer functions
"""

# Re-export vendored library functions
from .vendor import (
    fft_nilt,
    fft_nilt_one_sided,
    eps_im,
    n_doubling_error,
    tune_params,
    refine_until_accept,
    check_cfl_feasibility,
    TunedParams,
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
    # Vendored core
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
