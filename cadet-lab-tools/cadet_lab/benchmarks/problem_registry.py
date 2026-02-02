"""Problem registry for benchmark suite.

Provides centralized problem definitions, metadata, and scaling configurations
for Phase D acceleration evaluation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum


class ProblemCategory(Enum):
    """Problem category classification."""
    LINEAR = "linear"
    NONLINEAR = "nonlinear"
    TRANSPORT = "transport"
    BINDING = "binding"
    MULTI_COMPONENT = "multi_component"


class Discretization(Enum):
    """Spatial discretization method."""
    FV = "finite_volume"
    DG = "discontinuous_galerkin"


@dataclass
class ScalingTier:
    """Spatial scaling tier configuration.

    Attributes:
        name: Tier name (e.g., "small", "medium", "large", "xlarge")
        ncol: Number of column discretization cells
        npar: Number of particle discretization cells (if applicable)
        expected_dofs: Expected total degrees of freedom
        target_walltime: Expected wall time in seconds (for planning)
    """
    name: str
    ncol: int
    npar: int = 4
    expected_dofs: Optional[int] = None
    target_walltime: Optional[float] = None

    def __post_init__(self):
        if self.expected_dofs is None:
            # Rough estimate: ncol * npar * n_comp (assume 1 component)
            self.expected_dofs = self.ncol * self.npar


@dataclass
class ProblemDefinition:
    """Problem definition for benchmarking.

    Attributes:
        id: Unique problem identifier (e.g., "P1_linear_transport_low_pe")
        name: Human-readable problem name
        description: Brief description of problem characteristics
        categories: Problem category tags
        generator: Function that generates CADET config
        default_params: Default parameter values
        scaling_tiers: Available spatial scaling configurations
        discretization: Preferred discretization method
        is_linear: Whether problem has linear binding
        supports_nilt: Whether NILT acceleration applies
        reference_peclet: Reference Peclet number (if applicable)
        reference_ka: Reference binding rate (if applicable)
    """
    id: str
    name: str
    description: str
    categories: List[ProblemCategory]
    generator: Callable
    default_params: Dict[str, Any] = field(default_factory=dict)
    scaling_tiers: List[ScalingTier] = field(default_factory=list)
    discretization: Discretization = Discretization.FV
    is_linear: bool = False
    supports_nilt: bool = False
    reference_peclet: Optional[float] = None
    reference_ka: Optional[float] = None

    def __post_init__(self):
        # Set default scaling tiers if not provided
        if not self.scaling_tiers:
            self.scaling_tiers = get_default_scaling_tiers()


def get_default_scaling_tiers() -> List[ScalingTier]:
    """Get default 4-tier scaling configuration.

    Returns:
        List of ScalingTier objects for small/medium/large/xlarge.
    """
    return [
        ScalingTier(name="small", ncol=16, npar=2, expected_dofs=128, target_walltime=0.05),
        ScalingTier(name="medium", ncol=32, npar=4, expected_dofs=512, target_walltime=0.2),
        ScalingTier(name="large", ncol=64, npar=8, expected_dofs=2048, target_walltime=1.0),
        ScalingTier(name="xlarge", ncol=128, npar=16, expected_dofs=8192, target_walltime=5.0),
    ]


class ProblemRegistry:
    """Central registry for benchmark problems."""

    def __init__(self):
        self._problems: Dict[str, ProblemDefinition] = {}

    def register(self, problem: ProblemDefinition) -> None:
        """Register a problem definition.

        Args:
            problem: ProblemDefinition to register.

        Raises:
            ValueError: If problem ID already registered.
        """
        if problem.id in self._problems:
            raise ValueError(f"Problem {problem.id} already registered")
        self._problems[problem.id] = problem

    def get(self, problem_id: str) -> ProblemDefinition:
        """Get problem by ID.

        Args:
            problem_id: Problem identifier.

        Returns:
            ProblemDefinition for the requested problem.

        Raises:
            KeyError: If problem ID not found.
        """
        if problem_id not in self._problems:
            raise KeyError(f"Problem {problem_id} not found in registry")
        return self._problems[problem_id]

    def list_all(self) -> List[ProblemDefinition]:
        """List all registered problems.

        Returns:
            List of all ProblemDefinition objects.
        """
        return list(self._problems.values())

    def list_by_category(self, category: ProblemCategory) -> List[ProblemDefinition]:
        """List problems by category.

        Args:
            category: ProblemCategory to filter by.

        Returns:
            List of ProblemDefinition objects matching category.
        """
        return [p for p in self._problems.values() if category in p.categories]

    def list_linear(self) -> List[ProblemDefinition]:
        """List all linear problems (suitable for NILT).

        Returns:
            List of ProblemDefinition objects where is_linear=True.
        """
        return [p for p in self._problems.values() if p.is_linear]

    def list_nilt_compatible(self) -> List[ProblemDefinition]:
        """List problems compatible with NILT acceleration.

        Returns:
            List of ProblemDefinition objects where supports_nilt=True.
        """
        return [p for p in self._problems.values() if p.supports_nilt]


# Global registry instance
_global_registry = ProblemRegistry()


def get_registry() -> ProblemRegistry:
    """Get the global problem registry.

    Returns:
        Global ProblemRegistry instance.
    """
    return _global_registry


def register_problem(problem: ProblemDefinition) -> None:
    """Register a problem in the global registry.

    Args:
        problem: ProblemDefinition to register.
    """
    _global_registry.register(problem)


def get_problem(problem_id: str) -> ProblemDefinition:
    """Get problem from global registry.

    Args:
        problem_id: Problem identifier.

    Returns:
        ProblemDefinition for the requested problem.
    """
    return _global_registry.get(problem_id)


def list_problems(category: Optional[ProblemCategory] = None) -> List[ProblemDefinition]:
    """List problems from global registry.

    Args:
        category: Optional category to filter by.

    Returns:
        List of ProblemDefinition objects.
    """
    if category is None:
        return _global_registry.list_all()
    return _global_registry.list_by_category(category)
