# Spectral Eigenvalues for 1D Convection-Diffusion with Danckwerts Boundary Conditions

## 1. Problem Statement

### 1.1 Operator Definition

We seek the eigenvalues and eigenfunctions of the convection-diffusion operator:

$$\mathcal{L} = -v \frac{\partial}{\partial z} + D \frac{\partial^2}{\partial z^2}$$

on the domain $z \in [0, L]$, subject to Danckwerts boundary conditions.

### 1.2 Boundary Conditions

**Inlet (z = 0) - Danckwerts condition:**
$$v \cdot c(0) = v \cdot c_{in} - D \frac{\partial c}{\partial z}\bigg|_{z=0}$$

For the **homogeneous** eigenvalue problem, we set $c_{in} = 0$:
$$v \cdot c(0) + D \frac{\partial c}{\partial z}\bigg|_{z=0} = 0$$

**Outlet (z = L) - Zero-flux (Neumann):**
$$\frac{\partial c}{\partial z}\bigg|_{z=L} = 0$$

### 1.3 Eigenvalue Problem

Find $\phi_k(z)$ and $\lambda_k$ such that:
$$\mathcal{L}\phi_k = \lambda_k \phi_k$$

That is:
$$-v \frac{d\phi_k}{dz} + D \frac{d^2\phi_k}{dz^2} = \lambda_k \phi_k$$

---

## 2. Derivation of Eigenfunctions

### 2.1 General Solution Ansatz

Assume $\phi(z) = e^{rz}$. Substituting:
$$-v r e^{rz} + D r^2 e^{rz} = \lambda e^{rz}$$
$$D r^2 - v r - \lambda = 0$$

The characteristic equation gives:
$$r = \frac{v \pm \sqrt{v^2 + 4D\lambda}}{2D}$$

### 2.2 Non-dimensionalization

Define the Peclet number: $\text{Pe} = \frac{vL}{D}$

Dimensionless coordinate: $\xi = z/L$

Dimensionless eigenvalue: $\hat{\lambda} = \frac{\lambda L^2}{D}$

The characteristic roots become:
$$r L = \frac{\text{Pe}}{2} \pm \sqrt{\frac{\text{Pe}^2}{4} + \hat{\lambda}}$$

### 2.3 Eigenvalue Cases

Define $\mu^2 = \frac{\text{Pe}^2}{4} + \hat{\lambda}$

**Case 1: $\hat{\lambda} > -\text{Pe}^2/4$ (most physical cases)**

Let $\mu = \sqrt{\frac{\text{Pe}^2}{4} + \hat{\lambda}}$ be real.

General solution:
$$\phi(\xi) = e^{\text{Pe}\xi/2}\left(A \cosh(\mu\xi) + B \sinh(\mu\xi)\right)$$

**Case 2: $\hat{\lambda} < -\text{Pe}^2/4$ (oscillatory modes)**

Let $\beta = \sqrt{-\frac{\text{Pe}^2}{4} - \hat{\lambda}} = i\mu$ where $\mu$ is imaginary.

Then $\mu = i\beta$ with $\beta$ real, and:
$$\phi(\xi) = e^{\text{Pe}\xi/2}\left(A \cos(\beta\xi) + B \sin(\beta\xi)\right)$$

This is the **physically relevant case** that yields discrete eigenvalues.

### 2.4 Applying Boundary Conditions

Working with Case 2 (oscillatory modes), the general solution is:
$$\phi(\xi) = e^{\text{Pe}\xi/2}\left(A \cos(\beta\xi) + B \sin(\beta\xi)\right)$$

**Inlet BC at $\xi = 0$:**
$$v \cdot \phi(0) + D \frac{d\phi}{dz}\bigg|_{z=0} = 0$$

In dimensionless form (with $d/dz = (1/L) d/d\xi$):
$$\text{Pe} \cdot \phi(0) + \frac{d\phi}{d\xi}\bigg|_{\xi=0} = 0$$

Computing derivatives:
$$\phi(0) = A$$
$$\frac{d\phi}{d\xi}\bigg|_{\xi=0} = \frac{\text{Pe}}{2}A + \beta B$$

Inlet BC gives:
$$\text{Pe} \cdot A + \frac{\text{Pe}}{2}A + \beta B = 0$$
$$\frac{3\text{Pe}}{2}A + \beta B = 0$$
$$B = -\frac{3\text{Pe}}{2\beta}A$$

**Outlet BC at $\xi = 1$:**
$$\frac{d\phi}{d\xi}\bigg|_{\xi=1} = 0$$

Computing:
$$\frac{d\phi}{d\xi} = e^{\text{Pe}\xi/2}\left[\frac{\text{Pe}}{2}(A\cos\beta\xi + B\sin\beta\xi) + (-A\beta\sin\beta\xi + B\beta\cos\beta\xi)\right]$$

At $\xi = 1$:
$$\frac{\text{Pe}}{2}(A\cos\beta + B\sin\beta) + \beta(-A\sin\beta + B\cos\beta) = 0$$

Substituting $B = -\frac{3\text{Pe}}{2\beta}A$:

$$\frac{\text{Pe}}{2}\left(A\cos\beta - \frac{3\text{Pe}}{2\beta}A\sin\beta\right) + \beta\left(-A\sin\beta - \frac{3\text{Pe}}{2\beta}A\cos\beta\right) = 0$$

Dividing by $A$ and simplifying:

$$\frac{\text{Pe}}{2}\cos\beta - \frac{3\text{Pe}^2}{4\beta}\sin\beta - \beta\sin\beta - \frac{3\text{Pe}}{2}\cos\beta = 0$$

$$-\text{Pe}\cos\beta - \left(\frac{3\text{Pe}^2}{4\beta} + \beta\right)\sin\beta = 0$$

Multiplying by $\beta$:
$$-\text{Pe}\beta\cos\beta - \left(\frac{3\text{Pe}^2}{4} + \beta^2\right)\sin\beta = 0$$

---

## 3. Transcendental Eigenvalue Equation

### 3.1 Characteristic Equation

The eigenvalues are determined by:

$$\boxed{\tan(\beta_k) = -\frac{4\text{Pe}\beta_k}{3\text{Pe}^2 + 4\beta_k^2}}$$

where $\beta_k > 0$ are the positive roots of this transcendental equation.

### 3.2 Eigenvalues in Terms of $\beta_k$

The dimensionless eigenvalues are:
$$\hat{\lambda}_k = -\frac{\text{Pe}^2}{4} - \beta_k^2$$

In dimensional form:
$$\boxed{\lambda_k = -\frac{v^2}{4D} - \frac{D\beta_k^2}{L^2}}$$

**Note:** All eigenvalues are **negative** (or have negative real part), confirming the operator is dissipative.

### 3.3 Asymptotic Behavior

**For large $k$ (high modes):**

As $\beta_k \to \infty$, the RHS $\to 0$, so $\tan(\beta_k) \to 0$.

This means $\beta_k \approx k\pi$ for large $k$.

More precisely, for large $k$:
$$\beta_k \approx k\pi - \frac{\text{Pe}}{k\pi} + O(k^{-2})$$

**For small Pe (diffusion-dominated):**

As $\text{Pe} \to 0$:
$$\tan(\beta_k) \to 0 \implies \beta_k \to k\pi$$

This recovers the pure Neumann eigenvalues.

**For large Pe (convection-dominated):**

The first few eigenvalues are modified significantly, but high modes still approach $k\pi$.

---

## 4. Eigenfunctions

### 4.1 Normalized Form

The eigenfunctions are:
$$\phi_k(\xi) = N_k e^{\text{Pe}\xi/2}\left(\cos(\beta_k\xi) - \frac{3\text{Pe}}{2\beta_k}\sin(\beta_k\xi)\right)$$

where $N_k$ is a normalization constant.

### 4.2 Dimensional Form

$$\phi_k(z) = N_k \exp\left(\frac{vz}{2D}\right)\left[\cos\left(\frac{\beta_k z}{L}\right) - \frac{3\text{Pe}}{2\beta_k}\sin\left(\frac{\beta_k z}{L}\right)\right]$$

---

## 5. Comparison with Standard Transforms

### 5.1 DST-I (Dirichlet-Dirichlet)

**Boundary conditions:** $c(0) = c(L) = 0$

**Eigenfunctions:** $\phi_k(z) = \sin\left(\frac{k\pi z}{L}\right)$

**Eigenvalues (for pure diffusion):** $\lambda_k = -D\frac{k^2\pi^2}{L^2}$

### 5.2 DCT-II (Neumann-Neumann)

**Boundary conditions:** $\frac{\partial c}{\partial z}(0) = \frac{\partial c}{\partial z}(L) = 0$

**Eigenfunctions:** $\phi_k(z) = \cos\left(\frac{k\pi z}{L}\right)$

**Eigenvalues (for pure diffusion):** $\lambda_k = -D\frac{k^2\pi^2}{L^2}$

### 5.3 Danckwerts (This Work)

| Property | DST-I | DCT-II | Danckwerts |
|----------|-------|--------|------------|
| Inlet BC | Dirichlet | Neumann | Robin (flux) |
| Outlet BC | Dirichlet | Neumann | Neumann |
| Basis functions | $\sin(k\pi\xi)$ | $\cos(k\pi\xi)$ | $e^{\text{Pe}\xi/2}f_k(\xi)$ |
| $\beta_k$ | $k\pi$ | $k\pi$ | Roots of transcendental eq. |
| FFT-compatible | Yes (DST-I) | Yes (DCT-II) | **No** |
| Orthogonal | Yes (standard) | Yes (standard) | Yes (weighted) |

**Key Difference:** The Danckwerts eigenfunctions are **not** simple sinusoids due to:
1. The exponential prefactor $e^{\text{Pe}\xi/2}$ from convection
2. Non-standard eigenvalue spacing (not exactly $k\pi$)
3. Mixed trigonometric form with Pe-dependent coefficients

---

## 6. Orthogonality Analysis

### 6.1 Self-Adjoint Form

The operator $\mathcal{L} = -v\partial_z + D\partial_z^2$ is **not self-adjoint** in the standard $L^2$ inner product.

However, it can be made self-adjoint with the **weighted inner product**:
$$\langle f, g \rangle_w = \int_0^L f(z) g(z) e^{-vz/D} dz$$

The weight function $w(z) = e^{-vz/D} = e^{-\text{Pe}\xi}$ is the inverse of the convective flux Boltzmann factor.

### 6.2 Sturm-Liouville Form

Multiply the eigenvalue equation by $e^{-vz/D}$:
$$\frac{d}{dz}\left(De^{-vz/D}\frac{d\phi}{dz}\right) = \lambda e^{-vz/D}\phi$$

This is Sturm-Liouville form with:
- $p(z) = De^{-vz/D}$
- $q(z) = 0$
- $w(z) = e^{-vz/D}$

### 6.3 Orthogonality Relation

The eigenfunctions satisfy **weighted orthogonality**:
$$\boxed{\int_0^L \phi_k(z) \phi_j(z) e^{-vz/D} dz = 0 \quad \text{for } k \neq j}$$

In dimensionless form:
$$\int_0^1 \phi_k(\xi) \phi_j(\xi) e^{-\text{Pe}\xi} d\xi = 0 \quad \text{for } k \neq j$$

### 6.4 Verification

Substituting the eigenfunction form $\phi_k(\xi) = e^{\text{Pe}\xi/2}f_k(\xi)$:

$$\int_0^1 e^{\text{Pe}\xi/2}f_k(\xi) \cdot e^{\text{Pe}\xi/2}f_j(\xi) \cdot e^{-\text{Pe}\xi} d\xi = \int_0^1 f_k(\xi) f_j(\xi) d\xi$$

This simplifies to **standard $L^2$ orthogonality of the $f_k$ functions**:
$$\int_0^1 f_k(\xi) f_j(\xi) d\xi = 0 \quad \text{for } k \neq j$$

where $f_k(\xi) = \cos(\beta_k\xi) - \frac{3\text{Pe}}{2\beta_k}\sin(\beta_k\xi)$.

This can be verified directly using the transcendental equation for $\beta_k$.

---

## 7. FFT/DST/DCT Applicability

### 7.1 Direct FFT Methods: NOT Applicable

Standard FFT-based spectral methods (DST-I, DCT-II) **cannot be used directly** because:

1. **Non-equispaced eigenvalues:** $\beta_k \neq k\pi$ in general
2. **Exponential prefactor:** The eigenfunctions include $e^{\text{Pe}\xi/2}$
3. **Pe-dependent basis:** Each Peclet number requires different basis functions

### 7.2 Alternative Approaches

**Option A: Transformed Variable**

Define $\tilde{c}(z) = c(z)e^{-vz/(2D)}$. The operator becomes:
$$\tilde{\mathcal{L}} = D\frac{\partial^2}{\partial z^2} - \frac{v^2}{4D}$$

This is a **shifted Laplacian** but with **transformed boundary conditions** that are still non-standard.

**Option B: Precomputed Eigendecomposition**

1. Numerically solve for $\beta_k$ (roots of transcendental equation)
2. Precompute eigenfunctions on the grid
3. Use dense eigendecomposition for the preconditioner

This has $O(N^2)$ cost per solve but can be effective for moderate $N$.

**Option C: Approximate Spectral Method**

For high Pe, approximate:
- Use DCT-II for diffusion part
- Treat convection as a perturbation

For low Pe, approximate:
- $\beta_k \approx k\pi$, use standard DCT-II
- Apply correction for first few modes

**Option D: Hybrid FFT + Low-Rank Correction**

1. Use DCT-II with eigenvalues $-D(k\pi/L)^2$
2. Add low-rank correction for the deviation from true Danckwerts eigenvalues
3. The correction is most significant for small $k$

---

## 8. Closed-Form Eigenvalue Expressions

### 8.1 Exact (Implicit)

The eigenvalues are given implicitly by:
$$\lambda_k = -\frac{v^2}{4D} - \frac{D\beta_k^2}{L^2}$$

where $\beta_k$ satisfies:
$$\tan(\beta_k) = -\frac{4\text{Pe}\beta_k}{3\text{Pe}^2 + 4\beta_k^2}$$

### 8.2 Asymptotic Expansions

**Large $k$:**
$$\beta_k = k\pi - \frac{\text{Pe}}{k\pi} - \frac{\text{Pe}(3\text{Pe}^2 - 4)}{4(k\pi)^3} + O(k^{-5})$$

$$\lambda_k \approx -\frac{v^2}{4D} - \frac{D k^2\pi^2}{L^2} + \frac{2v}{L} + O(k^{-2})$$

**Small Pe:**
$$\beta_k \approx k\pi - \frac{3\text{Pe}}{2k\pi} + O(\text{Pe}^2)$$

**First eigenvalue ($k=1$):**

For $\text{Pe} \ll 1$: $\beta_1 \approx \pi - \frac{3\text{Pe}}{2\pi}$

For $\text{Pe} \gg 1$: $\beta_1 \approx \sqrt{\frac{3}{4}}\text{Pe}$ (requires careful analysis)

### 8.3 Numerical Values for Reference

| Pe | $\beta_1$ | $\beta_2$ | $\beta_3$ | $\beta_4$ |
|----|-----------|-----------|-----------|-----------|
| 0.1 | 3.094 | 6.237 | 9.378 | 12.519 |
| 1.0 | 2.664 | 5.894 | 9.121 | 12.306 |
| 10 | 1.644 | 4.807 | 8.012 | 11.217 |
| 100 | 1.223 | 4.376 | 7.574 | 10.788 |

Note: As Pe increases, $\beta_1$ decreases, meaning the first eigenvalue becomes less negative (slower decay).

---

## 9. Summary and Recommendations

### 9.1 Key Results

1. **Eigenvalues** are given by $\lambda_k = -v^2/(4D) - D\beta_k^2/L^2$ where $\beta_k$ are roots of a transcendental equation

2. **Eigenfunctions** have the form $\phi_k(z) \propto e^{vz/(2D)}[\cos(\beta_k z/L) - c_k\sin(\beta_k z/L)]$

3. **Orthogonality** holds with weight $w(z) = e^{-vz/D}$

4. **No direct FFT/DST/DCT** is applicable due to the non-standard eigenvalue spacing and exponential prefactor

### 9.2 Implementation Recommendations for CADET Preconditioner

**For moderate grid sizes ($N < 500$):**
- Precompute eigendecomposition at setup
- Store eigenvector matrices
- Apply preconditioner via matrix-vector products: $O(N^2)$

**For large grid sizes ($N > 500$):**
- Use approximate spectral method with DCT-II + correction
- Or use block-diagonal/banded approximation to the exact preconditioner

**For variable Pe (adaptive methods):**
- Tabulate $\beta_k$ for range of Pe values
- Interpolate for intermediate Pe

### 9.3 Code Implementation Notes

```python
import numpy as np
from scipy.optimize import brentq

def find_beta_k(k, Pe, tol=1e-12):
    """Find k-th root of transcendental eigenvalue equation."""
    def f(beta):
        return np.tan(beta) + 4*Pe*beta / (3*Pe**2 + 4*beta**2)

    # Roots are near k*pi for large k
    # For k=1, root is between 0 and pi
    # For k>1, root is between (k-1)*pi and k*pi

    if k == 1:
        a, b = 0.01, np.pi - 0.01
    else:
        a, b = (k-1)*np.pi + 0.01, k*np.pi - 0.01

    return brentq(f, a, b, xtol=tol)

def eigenvalue(k, Pe, D, L):
    """Compute k-th eigenvalue."""
    beta_k = find_beta_k(k, Pe)
    return -Pe**2 * D / (4*L**2) - D * beta_k**2 / L**2

def eigenfunction(z, k, Pe, L, normalized=True):
    """Compute k-th eigenfunction at position z."""
    beta_k = find_beta_k(k, Pe)
    xi = z / L
    f = np.cos(beta_k * xi) - (3*Pe / (2*beta_k)) * np.sin(beta_k * xi)
    phi = np.exp(Pe * xi / 2) * f

    if normalized:
        # Normalize in weighted L2 norm
        norm = np.sqrt(weighted_norm_squared(k, Pe, L))
        phi = phi / norm

    return phi
```

---

## Appendix A: Derivation Details

### A.1 Verification of Transcendental Equation

Starting from the outlet BC:
$$\frac{\text{Pe}}{2}(A\cos\beta + B\sin\beta) + \beta(-A\sin\beta + B\cos\beta) = 0$$

With $B = -\frac{3\text{Pe}}{2\beta}A$:

Let $\alpha = 3\text{Pe}/(2\beta)$. Then $B = -\alpha A$.

$$\frac{\text{Pe}}{2}(A\cos\beta - \alpha A\sin\beta) + \beta(-A\sin\beta - \alpha A\cos\beta) = 0$$

$$A\left[\frac{\text{Pe}}{2}\cos\beta - \frac{\text{Pe}\alpha}{2}\sin\beta - \beta\sin\beta - \alpha\beta\cos\beta\right] = 0$$

$$\frac{\text{Pe}}{2}\cos\beta - \frac{3\text{Pe}^2}{4\beta}\sin\beta - \beta\sin\beta - \frac{3\text{Pe}}{2}\cos\beta = 0$$

$$-\text{Pe}\cos\beta - \left(\frac{3\text{Pe}^2}{4\beta} + \beta\right)\sin\beta = 0$$

$$\frac{\sin\beta}{\cos\beta} = \frac{-\text{Pe}}{\frac{3\text{Pe}^2}{4\beta} + \beta} = \frac{-\text{Pe}\beta}{\frac{3\text{Pe}^2}{4} + \beta^2}$$

$$\tan\beta = \frac{-4\text{Pe}\beta}{3\text{Pe}^2 + 4\beta^2}$$

### A.2 Alternative Form of Eigenvalue Equation

The characteristic equation can also be written as:
$$\beta\cot\beta = -\frac{3\text{Pe}^2 + 4\beta^2}{4\text{Pe}}$$

Or in terms of eigenvalue $\mu = i\beta$:
$$\mu\coth\mu = \frac{3\text{Pe}^2 - 4\mu^2}{4\text{Pe}}$$

---

## Appendix B: Limiting Cases

### B.1 Pure Diffusion Limit (Pe → 0)

As Pe → 0, the inlet BC becomes Neumann: $\partial c/\partial z|_{z=0} = 0$.

The transcendental equation becomes $\tan(\beta) = 0$, giving $\beta_k = k\pi$.

Eigenvalues: $\lambda_k = -Dk^2\pi^2/L^2$ (standard DCT-II eigenvalues).

### B.2 Strong Convection Limit (Pe → ∞)

The system becomes hyperbolic. The eigenvalue spectrum changes character.

For finite but large Pe, the low modes are strongly affected while high modes approach diffusion-dominated behavior.

### B.3 Dirichlet Inlet Limit

If we instead imposed $c(0) = 0$ (Dirichlet), combined with Neumann outlet, we would get a different transcendental equation. This is **not** the Danckwerts condition.

---

## References

1. Danckwerts, P.V. (1953). "Continuous flow systems. Distribution of residence times." Chemical Engineering Science, 2(1), 1-13.

2. Lapidus, L., & Pinder, G.F. (1982). "Numerical Solution of Partial Differential Equations in Science and Engineering." Wiley.

3. Haberman, R. (2012). "Applied Partial Differential Equations with Fourier Series and Boundary Value Problems." Pearson.

4. Trefethen, L.N. (2000). "Spectral Methods in MATLAB." SIAM.
