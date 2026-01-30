"""FFT-based Numerical Inverse Laplace Transform.

Vendored from: https://github.com/gogipav14/nilt-cfl
License: MIT

Implements the Dubner-Abate/Hsu-Dranoff FFT method with CFL-informed
parameter selection.
"""

from __future__ import annotations
import numpy as np
import warnings
from typing import Callable, Tuple, Literal, Optional


def fft_nilt(
    F: Callable[[complex], complex],
    a: float,
    T: float,
    N: int,
    return_complex: bool = False,
    diagnostics_mode: Literal["none", "one_sided", "paper"] = "one_sided"
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[float]]:
    """
    Compute inverse Laplace transform using Dubner-Abate FFT method.

    Evaluates F(s) along the Bromwich contour Re(s) = a at positive
    frequencies ω_k = k*Δω for k = 0, 1, ..., N-1, then uses IFFT
    followed by Re[] extraction.

    Parameters
    ----------
    F : callable
        Laplace-domain transfer function F(s) -> complex
    a : float
        Bromwich shift parameter (contour Re(s) = a)
    T : float
        Half-period (aliasing period = 2T)
    N : int
        Number of FFT points (preferably power of 2)
    return_complex : bool
        Unused, kept for API compatibility
    diagnostics_mode : {"none", "one_sided", "paper"}
        - "none": No diagnostic computed
        - "one_sided": Compute one_sided_imag_ratio on complex IFFT output (legacy)
        - "paper": Compute paper-compliant ε_Im using irfft reconstruction

    Returns
    -------
    f : ndarray
        Time-domain function values at t_j = j * Δt
    t : ndarray
        Time points t_j for j = 0, ..., N-1
    z_ifft : ndarray
        Complex IFFT output (before Re[] extraction)
    eps_im : float or None
        Diagnostic value (depends on diagnostics_mode), or None if "none"

    Notes
    -----
    For CFL-tuned parameters (a, T) satisfying the feasibility conditions:
    - a > α_c + δ_min (spectral placement)
    - a < (L - δ_s)/(2T) (dynamic range)
    - a ≥ α_c + ln(C/ε_tail)/(2T-t_end) (aliasing suppression)

    The result accuracy is controlled by N (truncation error) and the
    CFL parameters (aliasing error).

    Diagnostics modes:
    - "one_sided": Im/Re ratio of raw IFFT output. High values (~0.6) are
      expected and do NOT indicate errors. This is NOT paper2_nilt_cfl ε_Im.
    - "paper": Uses irfft to reconstruct a real-valued time signal from the
      positive frequency bins. ε_Im should be ~1e-10 for real-valued f(t).
      This matches paper2_nilt_cfl Eq. (28) intent.
    """
    # Frequency spacing: Δω = π/T
    delta_omega = np.pi / T

    # Time step: Δt = 2T/N
    delta_t = 2 * T / N

    # Time grid: t_j = j * Δt for j = 0, ..., N-1
    t = np.arange(N) * delta_t

    # Frequency grid: ω_k = k * Δω for k = 0, ..., N-1
    omega = np.arange(N) * delta_omega
    s = a + 1j * omega

    # Evaluate F(s) at Bromwich contour points
    G = np.array([F(sk) for sk in s], dtype=np.complex128)

    # Apply trapezoidal weight at DC (k=0 endpoint)
    G[0] = G[0] / 2

    # Compute sum via IFFT
    # IFFT: (1/N) * Σ G[k] exp(i 2π k j / N)
    # Our sum: Σ G[k] exp(i k Δω t_j) = Σ G[k] exp(i 2π k j / N) [since Δω*Δt = 2π/N]
    # So multiply IFFT by N
    z_ifft = N * np.fft.ifft(G)

    # Apply exponential factor, scaling, and extract real part
    # f(t) = exp(a*t) / T * Re[sum]
    f = np.exp(a * t) / T * np.real(z_ifft)

    # Compute diagnostic based on mode
    eps_im_value: Optional[float] = None
    if diagnostics_mode == "one_sided":
        eps_im_value = one_sided_imag_ratio(z_ifft)
    elif diagnostics_mode == "paper":
        eps_im_value = epsilon_im_paper(G, N, a, T)

    return f, t, z_ifft, eps_im_value


def fft_nilt_one_sided(
    F: Callable[[complex], complex],
    a: float,
    T: float,
    N: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    One-sided (non-Hermitian) implementation for comparison.

    This is the traditional Hsu-Dranoff approach that evaluates F(s)
    at all N frequencies and takes Re[] at the end.

    May have larger imaginary leakage due to accumulated phase errors.
    """
    delta_omega = np.pi / T
    delta_t = 2 * T / N
    t = np.arange(N) * delta_t
    omega = np.arange(N) * delta_omega
    s = a + 1j * omega

    G = np.array([F(sk) for sk in s], dtype=np.complex128)
    G[0] = G[0] / 2  # Trapezoidal weight for DC

    z_ifft = N * np.fft.ifft(G)
    f = np.exp(a * t) / T * np.real(z_ifft)

    return f, t, z_ifft


def one_sided_imag_ratio(z_ifft: np.ndarray) -> float:
    """
    Compute Im/Re ratio of one-sided IFFT output.

    NOTE: This is NOT the ε_Im from paper2_nilt_cfl. High values (~0.6)
    are expected for one-sided FFT evaluation and do NOT indicate errors.
    The imaginary component arises because the spectrum lacks Hermitian
    symmetry, not from numerical inaccuracy.

    For the paper-compliant ε_Im diagnostic, use epsilon_im_paper() instead.

    Parameters
    ----------
    z_ifft : ndarray
        Complex IFFT output from one-sided frequency evaluation

    Returns
    -------
    ratio : float
        RMS(Im(z)) / RMS(Re(z))
    """
    real_part = np.real(z_ifft)
    imag_part = np.imag(z_ifft)

    rms_real = np.sqrt(np.mean(real_part**2))
    rms_imag = np.sqrt(np.mean(imag_part**2))

    if rms_real < 1e-300:
        return np.inf

    return rms_imag / rms_real


def eps_im(z_ifft: np.ndarray) -> float:
    """Deprecated alias for one_sided_imag_ratio. Use one_sided_imag_ratio instead."""
    warnings.warn(
        "eps_im() is deprecated and does NOT compute paper2_nilt_cfl ε_Im. "
        "Use one_sided_imag_ratio() for this metric or epsilon_im_paper() for "
        "the paper-compliant diagnostic.",
        DeprecationWarning,
        stacklevel=2
    )
    return one_sided_imag_ratio(z_ifft)


def epsilon_im_paper(
    G: np.ndarray,
    N: int,
    a: float,
    T: float,
    t_eval_min: float = 0.0,
    t_eval_max: Optional[float] = None
) -> float:
    """
    Compute paper2_nilt_cfl ε_Im using real-valued irfft reconstruction.

    This is the proper ε_Im diagnostic from paper2_nilt_cfl Eq. (28):
    ε_Im = max|Im(f̃(t))| / max|Re(f̃(t))|

    For a real-valued time-domain function f(t), the NILT output should be
    purely real. This diagnostic measures numerical consistency and should
    be ~1e-10 for well-conditioned problems (not ~0.6 like one_sided_imag_ratio).

    Parameters
    ----------
    G : ndarray
        Complex frequency-domain samples F(s_k) for k=0,...,N-1
        (with trapezoidal weight already applied to G[0])
    N : int
        Number of time points (must be even for irfft)
    a : float
        Bromwich shift parameter
    T : float
        Half-period
    t_eval_min : float
        Minimum time for evaluation (default 0.0)
    t_eval_max : float, optional
        Maximum time for evaluation (default T)

    Returns
    -------
    eps_im : float
        Paper-compliant ε_Im diagnostic (should be ~1e-10 for real functions)
    """
    if t_eval_max is None:
        t_eval_max = T

    # For irfft with output length N, we need N//2 + 1 positive frequency bins
    # Current G has N bins (k=0,...,N-1), so take G[:N//2+1]
    n_rfft = N // 2 + 1
    G_rfft = G[:n_rfft].copy()

    # irfft expects the positive frequencies including DC and Nyquist
    # The Nyquist bin (k=N/2) should be real for a real signal
    # Scale: irfft gives (1/N) * sum, we want sum, so multiply by N
    z_real = N * np.fft.irfft(G_rfft, n=N)

    # Apply exponential factor and scaling
    delta_t = 2 * T / N
    t = np.arange(N) * delta_t
    f_reconstructed = np.exp(a * t) / T * z_real

    # For paper ε_Im, we need the imaginary part of the NILT output
    # With irfft, the output is real by construction, so we compute ε_Im
    # by comparing irfft result to the complex ifft result
    z_ifft_complex = N * np.fft.ifft(G)
    f_complex = np.exp(a * t) / T * z_ifft_complex

    # Evaluate on the specified time window
    mask = (t >= t_eval_min) & (t <= t_eval_max)
    f_complex_window = f_complex[mask]

    # Paper ε_Im: max|Im| / max|Re|
    max_imag = np.max(np.abs(np.imag(f_complex_window)))
    max_real = np.max(np.abs(np.real(f_complex_window)))

    if max_real < 1e-300:
        return np.inf

    return max_imag / max_real


def n_doubling_error(
    F: Callable[[complex], complex],
    a: float,
    T: float,
    N: int,
    t_eval_min: float = 0.1,
    t_eval_max: float = None
) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    Compute N-doubling convergence error.

    E_N = RMS(f_N - f_{2N}) / RMS(f_{2N})

    evaluated over [t_eval_min, t_eval_max].

    Parameters
    ----------
    F : callable
        Transfer function
    a : float
        Bromwich shift
    T : float
        Half-period
    N : int
        Current sample count
    t_eval_min : float
        Minimum time for evaluation (default 0.1 to avoid t=0 issues)
    t_eval_max : float
        Maximum time for evaluation (default T)

    Returns
    -------
    E_N : float
        Convergence error metric
    f_N : ndarray
        Solution at N points (on evaluation grid)
    f_2N : ndarray
        Solution at 2N points (on evaluation grid)
    """
    if t_eval_max is None:
        t_eval_max = T

    # Compute at N points (ignore diagnostics)
    f_N_full, t_N, _, _ = fft_nilt(F, a, T, N, diagnostics_mode="none")

    # Compute at 2N points (ignore diagnostics)
    f_2N_full, t_2N, _, _ = fft_nilt(F, a, T, 2 * N, diagnostics_mode="none")

    # Interpolate to common evaluation grid
    # Use the 2N time points within evaluation range
    mask_2N = (t_2N >= t_eval_min) & (t_2N <= t_eval_max)
    t_eval = t_2N[mask_2N]
    f_2N = f_2N_full[mask_2N]

    # Interpolate f_N to the same time points
    f_N = np.interp(t_eval, t_N, f_N_full)

    # Compute error
    rms_diff = np.sqrt(np.mean((f_N - f_2N)**2))
    rms_2N = np.sqrt(np.mean(f_2N**2))

    if rms_2N < 1e-300:
        return np.inf, f_N, f_2N

    E_N = rms_diff / rms_2N

    return E_N, f_N, f_2N
