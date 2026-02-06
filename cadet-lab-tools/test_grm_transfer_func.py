#!/usr/bin/env python3
"""Diagnose GRM transfer function numerical behavior."""

import numpy as np
import cmath
from cadet_lab.benchmarks.nilt_problem_suite import get_p3_transfer_function

# Get transfer function
F = get_p3_transfer_function()

# Test values at different Laplace frequencies
test_points = [
    0.01 + 0j,
    0.1 + 0j,
    1.0 + 0j,
    10.0 + 0j,
    0.5 + 1.0j,  # Complex
]

print("GRM Langmuir Transfer Function Diagnostic")
print("=" * 60)
print(f"{'s':>20} {'F(s)':>25} {'|F(s)|':>15}")
print("-" * 60)

for s in test_points:
    try:
        result = F(s)
        magnitude = abs(result)
        print(f"{s:>20} {result:>25} {magnitude:>15.6e}")
    except Exception as e:
        print(f"{s:>20} ERROR: {e}")

print()

# Test with alpha-shifted Bromwich contour (typical NILT)
alpha = 0.5
N = 256
T = 50.0  # Half-period
k_test = [0, 1, 10, 50, 100, N//2]

print(f"\nBromwich Contour Test (α={alpha}, N={N}, T={T})")
print("=" * 60)
print(f"{'k':>5} {'s_k':>25} {'F(s_k)':>25} {'|F(s_k)|':>15}")
print("-" * 60)

for k in k_test:
    omega_k = np.pi * k / T
    s_k = alpha + 1j * omega_k
    try:
        result = F(s_k)
        magnitude = abs(result)
        print(f"{k:>5} {s_k:>25} {result:>25} {magnitude:>15.6e}")
    except Exception as e:
        print(f"{k:>5} {s_k:>25} ERROR: {e}")

# Check for singularities near contour
print("\n\nChecking for numerical issues:")
print("=" * 60)

# Test very small s (should approach 1.0 for step response)
s_small = 1e-10 + 0j
try:
    F_small = F(s_small)
    print(f"F(s→0) = {F_small} (should be ~1.0 for step input)")
except Exception as e:
    print(f"F(s→0) ERROR: {e}")

# Test imaginary axis
s_imag = 0.0 + 10.0j
try:
    F_imag = F(s_imag)
    print(f"F(s=10j) = {F_imag} (should have |F| ≤ 1)")
except Exception as e:
    print(f"F(s=10j) ERROR: {e}")

# Test real axis negative (should be stable, no poles for Re(s) > 0)
s_neg = -0.1 + 0j
try:
    F_neg = F(s_neg)
    print(f"F(s=-0.1) = {F_neg} (checking left half-plane)")
except Exception as e:
    print(f"F(s=-0.1) ERROR: {e}")
