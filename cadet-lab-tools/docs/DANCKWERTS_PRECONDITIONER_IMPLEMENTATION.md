# Danckwerts Spectral Preconditioner Implementation

## Overview

This document describes the implementation of the `DanckwertsSpectralPreconditioner` class for CADET, which provides a spectral preconditioner for the 1D convection-diffusion operator with Danckwerts boundary conditions.

## Mathematical Foundation

See [DANCKWERTS_EIGENVALUES_DERIVATION.md](DANCKWERTS_EIGENVALUES_DERIVATION.md) for the complete mathematical derivation.

### Key Equations

**Eigenvalues:**
```
λ_k = -v²/(4D) - D·β_k²/L²
```

**Transcendental Equation:**
```
tan(β_k) = -4·Pe·β_k / (3·Pe² + 4·β_k²)
```

where `Pe = vL/D` is the Peclet number.

**Eigenfunctions:**
```
φ_k(z) = N_k · exp(Pe·ξ/2) · [cos(β_k·ξ) - (3·Pe)/(2·β_k)·sin(β_k·ξ)]
```

where `ξ = z/L` and `N_k` is a normalization constant.

## Implementation Details

### File Structure

```
src/libcadet/linalg/
├── DanckwertsSpectralPreconditioner.hpp  (Header file)
└── DanckwertsSpectralPreconditioner.cpp  (Implementation)

test/
└── test_danckwerts_preconditioner.cpp    (Unit tests)
```

### Class: `DanckwertsSpectralPreconditioner`

**Namespace:** `cadet::linalg`

**Purpose:** Provides spectral preconditioning for GMRES when solving linear systems arising from implicit time integration of 1D convection-diffusion PDEs with Danckwerts BCs.

### Public Methods

#### `initialize(nPoints, colLength, velocity, dispersion, nModes)`

Initializes the preconditioner by computing the eigendecomposition.

**Parameters:**
- `nPoints` - Number of spatial grid points
- `colLength` - Column length L (meters)
- `velocity` - Interstitial velocity v (m/s)
- `dispersion` - Axial dispersion coefficient D (m²/s)
- `nModes` - Number of spectral modes (default: min(nPoints, 32))

**Algorithm:**
1. Compute Peclet number `Pe = vL/D`
2. Solve transcendental equation for β_k (k = 1, ..., nModes)
3. Compute eigenvalues λ_k
4. Assemble eigenvector matrix Φ (nPoints × nModes)
5. Compute transpose Φᵀ for efficient application
6. Normalize eigenvectors using weighted L² norm

#### `apply(timestep, residual, solution)`

Applies the preconditioner: `solution = M⁻¹ · residual`

**Parameters:**
- `timestep` - Time step dt for backward Euler operator (I - dt·L)
- `residual` - Input residual vector (length nPoints)
- `solution` - Output solution vector (length nPoints)

**Algorithm:**
1. Project residual onto spectral basis: α = Φᵀ·r
2. Scale by diagonal operator: β_k = α_k / (1 - dt·λ_k)
3. Transform back to physical space: z = Φ·β

**Complexity:** O(nPoints · nModes)

#### `update(velocity, dispersion)`

Updates the preconditioner for new physical parameters without reallocation.

**Use case:** Adaptive methods where Pe changes during simulation.

### Protected Methods

#### `findBetaK(k, Pe)`

Solves the transcendental equation for the k-th eigenvalue using Newton-Raphson iteration.

**Algorithm:**
1. Initial guess:
   - For k=1, high Pe: `β₁ ≈ √(3/4)·Pe`
   - Otherwise: `β_k ≈ (k - 0.5)·π`
2. Newton-Raphson on `f(β) = tan(β) + 4·Pe·β/(3·Pe² + 4·β²) = 0`
3. Derivative: `f'(β) = sec²(β) + 4·Pe·(3·Pe² - 4·β²)/(3·Pe² + 4·β²)²`
4. Convergence tolerance: `|Δβ| < 10⁻¹²·|β|`

**Numerical Considerations:**
- Avoid singularities at `β = π/2, 3π/2, ...` by small perturbations
- Enforce bounds: `(k-1)·π < β_k < k·π`

#### `assembleEigenvectors()`

Constructs the eigenvector matrix on the discrete grid.

**Algorithm:**
```cpp
for each mode k:
    for each grid point i:
        z = i * dz
        ξ = z / L
        φ_k(i) = exp(Pe·ξ/2) · [cos(β_k·ξ) - c_k·sin(β_k·ξ)]
        where c_k = 3·Pe/(2·β_k)

    // Normalize using weighted L² norm
    norm = √(∫₀ᴸ φ_k²(z) · exp(-Pe·z/L) dz)
    φ_k /= norm
```

#### `computeWeightedNorm(k)`

Computes the weighted L² norm for orthogonality.

**Weight function:** `w(z) = exp(-Pe·z/L)`

**Integration:** Trapezoidal rule on the discrete grid

## Memory Requirements

For `N` grid points and `M` modes:

| Component | Size | Typical (N=64, M=32) |
|-----------|------|----------------------|
| `_eigenvectors` | N × M doubles | 16 KB |
| `_eigenvectorsT` | M × N doubles | 16 KB |
| `_eigenvalues` | M doubles | 256 B |
| `_betaValues` | M doubles | 256 B |
| `_workspace*` | 2M doubles | 512 B |
| **Total** | ~2NM + 4M | **~33 KB** |

For typical chromatography problems (N ≈ 100, M ≈ 32), memory usage is negligible compared to the full Jacobian.

## Performance Characteristics

### Initialization Cost

- Transcendental solves: O(M) Newton iterations (< 10 iterations per mode)
- Matrix assembly: O(N·M)
- **Total:** ~1-10 ms for typical cases

### Application Cost per GMRES Iteration

- Matrix-vector products: 2 × O(N·M)
- Diagonal scaling: O(M)
- **Total:** ~0.1 ms for N=100, M=32

### Preconditioning Effectiveness

Expected iteration reduction depends on Peclet number:

| Regime | Pe Range | Expected Speedup |
|--------|----------|------------------|
| Diffusion-dominated | Pe < 1 | 2-5× |
| Balanced | 1 < Pe < 100 | 5-10× |
| Convection-dominated | Pe > 100 | 3-7× |

## Integration with CADET Models

### Minimal Integration Example

```cpp
#include "linalg/DanckwertsSpectralPreconditioner.hpp"

// In GeneralRateModel class:
class GeneralRateModel {
protected:
    linalg::DanckwertsSpectralPreconditioner _spectralPrecond;
    bool _useSpectralPrecond;

public:
    void configure(IParameterProvider& paramProvider) {
        _useSpectralPrecond = paramProvider.getInt("USE_SPECTRAL_PRECOND");

        if (_useSpectralPrecond) {
            _spectralPrecond.initialize(
                _disc.nCol,           // Grid points
                _colLength,           // Column length
                _velocity,            // Velocity
                _colDispersion        // Dispersion
            );
        }
    }

    int linearSolve(double t, double alpha, double tol,
                    double* const rhs, double const* const weight) {
        if (_useSpectralPrecond) {
            // Apply preconditioner before GMRES
            std::vector<double> precondRhs(_disc.nCol);
            _spectralPrecond.apply(alpha, rhs, precondRhs.data());

            // Solve with preconditioned system
            return _gmres.solve(tol, weight, precondRhs.data(), rhs);
        } else {
            // Standard GMRES without preconditioning
            return _gmres.solve(tol, weight, rhs, rhs);
        }
    }
};
```

## Testing

### Unit Tests (`test_danckwerts_preconditioner.cpp`)

1. **testTranscendentalRoots()** - Verifies β_k values match analytical predictions
2. **testEigenvalueSign()** - Confirms all λ_k < 0 (dissipative operator)
3. **testPreconditionerApplication()** - Tests apply() produces non-trivial output
4. **testOrthogonality()** - Checks weighted orthogonality of eigenvectors

**Build and run:**
```bash
cd test
./build_danckwerts_test.sh
```

### Integration Tests

Recommended integration tests:
1. Compare GMRES iterations with/without preconditioning on 1D GRM
2. Verify solution accuracy is unchanged
3. Benchmark wall-clock time for various Pe numbers

## Limitations and Future Work

### Current Limitations

1. **1D Only** - Only supports 1D axial flow (not 2D/3D operators)
2. **Constant Coefficients** - Assumes v and D are spatially constant
3. **Dense Storage** - O(N·M) memory, not suitable for very large N
4. **Column Models Only** - Designed for bulk phase transport, not particle diffusion

### Potential Extensions

1. **Adaptive Mode Selection** - Choose M based on Pe and desired accuracy
2. **FFT Acceleration** - For Pe ≈ 0, eigenfunctions approach DCT-II (FFT-compatible)
3. **Low-Rank Approximation** - Compress Φ using truncated SVD for large N
4. **Particle Diffusion** - Extend to spherical coordinates for GRM particle models
5. **2D Extension** - Tensor product approach for 2D operators

## References

1. Danckwerts, P.V. (1953). "Continuous flow systems." Chemical Engineering Science.
2. Lapidus & Pinder (1982). "Numerical Solution of PDEs in Science and Engineering."
3. Trefethen, L.N. (2000). "Spectral Methods in MATLAB." SIAM.
4. VonLieres et al. (2010). "A fast and accurate solver for GRM." Computers & Chemical Engineering.

## Code Example: Minimal Working Program

```cpp
#include "linalg/DanckwertsSpectralPreconditioner.hpp"
#include <iostream>
#include <vector>
#include <cmath>

int main() {
    using namespace cadet::linalg;

    // Physical parameters
    const double L = 0.1;      // 10 cm column
    const double v = 0.001;    // 1 mm/s velocity
    const double D = 1e-6;     // Typical dispersion
    const double dt = 0.1;     // Time step
    const unsigned int N = 64; // Grid points

    // Initialize preconditioner
    DanckwertsSpectralPreconditioner precond;
    precond.initialize(N, L, v, D);

    std::cout << "Initialized with Pe = " << precond.pecletNumber() << std::endl;
    std::cout << "Using " << precond.numModes() << " spectral modes" << std::endl;

    // Create test residual
    std::vector<double> residual(N);
    std::vector<double> solution(N);
    for (unsigned int i = 0; i < N; ++i) {
        residual[i] = std::sin(2.0 * M_PI * i / (N - 1.0));
    }

    // Apply preconditioner
    if (precond.apply(dt, residual.data(), solution.data())) {
        std::cout << "Preconditioner applied successfully" << std::endl;
    }

    return 0;
}
```

## Build Integration

The preconditioner is automatically built with CADET when added to `src/libcadet/CMakeLists.txt`:

```cmake
set (LIBCADET_NONLINALG_SOURCES
    # ... other sources ...
    ${CMAKE_SOURCE_DIR}/src/libcadet/linalg/DanckwertsSpectralPreconditioner.cpp
)
```

No additional dependencies are required beyond existing LAPACK/BLAS for dense matrix operations.
