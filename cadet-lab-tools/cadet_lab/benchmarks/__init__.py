"""Benchmark suite for Phase D acceleration evaluation.

This package provides infrastructure for evaluating NILT acceleration,
FFT preconditioning, and baseline GMRES characterization across a
comprehensive suite of test problems.

Modules:
    problem_registry: Problem definitions and metadata
    nilt_comparison: NILT vs CADET comparison utilities
    nilt_problem_suite: Linear problem definitions for Track 1
    acceleration_suite: Master problem suite for all tracks
    analyze_acceleration: Results analysis and visualization
"""

__version__ = "1.0.0"

from cadet_lab.benchmarks.problem_registry import (
    ProblemDefinition,
    ProblemRegistry,
    get_problem,
    list_problems,
)

__all__ = [
    "ProblemDefinition",
    "ProblemRegistry",
    "get_problem",
    "list_problems",
]
