#!/usr/bin/env python3
"""Test P3 with advanced GRM Langmuir transfer function."""

from pathlib import Path
from cadet_lab.benchmarks.problem_registry import get_problem
from cadet_lab.benchmarks.nilt_problem_suite import get_transfer_function_for_problem
from cadet_lab.benchmarks.nilt_comparison import run_nilt_vs_cadet_benchmark

# Get P3 problem
problem = get_problem("P3_linear_langmuir_dilute")
transfer_func = get_transfer_function_for_problem("P3_linear_langmuir_dilute")

# Test small tier
tier = problem.scaling_tiers[0]  # small: NCOL=16, NPAR=2

print(f"Testing {problem.name} @ {tier.name} with GRM transfer function")
print(f"NCOL={tier.ncol}, NPAR={tier.npar}, DOFs={tier.expected_dofs}")
print()

result = run_nilt_vs_cadet_benchmark(
    problem=problem,
    tier=tier,
    transfer_function=transfer_func,
    cadet_cli_path=Path("/home/gogip/github_repos/CADET-Core/install/bin/cadet-cli"),
    output_dir=Path("artifacts/p3_grm_test"),
    nilt_params={"alpha": 0.5, "N": 256, "t_final": 100.0},
)

print("Results:")
print(f"  RMSE: {result.rmse:.6e}")
print(f"  Relative L2 error: {result.relative_l2_error:.6f}%")
print(f"  L∞ norm: {result.linf_norm:.6e}")
print(f"  NILT time: {result.nilt_time:.4f} s")
print(f"  CADET time: {result.cadet_time:.4f} s")
print(f"  Speedup: {result.speedup:.2f}×")
print(f"  ε_Im: {result.eps_im:.6e}")
print(f"  CADET steps: {result.cadet_steps}")
print()

if result.relative_l2_error < 1.0:
    print(f"✅ PASSED: Accuracy meets criterion (Rel L2 = {result.relative_l2_error:.2f}% < 1%)")
else:
    print(f"⚠️  FAILED: Accuracy too low (Rel L2 = {result.relative_l2_error:.2f}% > 1%)")
