# GRM Transfer Function Derivation for Kinetic Binding

**Author:** Phase D Track 1 Extension
**Date:** 2026-02-01
**Purpose:** Derive analytical Laplace-domain transfer functions for GRM with kinetic binding (Langmuir and SMA)

---

## 1. Introduction

### 1.1 Problem Statement

The General Rate Model (GRM) includes:
- **Column transport:** Advection-dispersion in bulk phase
- **Film mass transfer:** Resistance at particle surface
- **Pore diffusion:** Radial diffusion within particles
- **Kinetic binding:** Adsorption/desorption dynamics

**Goal:** Derive outlet transfer function F(s) such that:
```
C_outlet(s) = F(s) · C_inlet(s)
```

Where s is the Laplace variable (complex frequency).

### 1.2 Assumptions for Linearization

**Valid for:**
1. **Single component** (protein of interest)
2. **Dilute regime:** c << qmax (Langmuir) or small perturbations (SMA)
3. **Linear binding kinetics:** First-order rate laws
4. **Isothermal conditions:** No temperature effects
5. **Constant flow rate:** No pressure effects

**Limitations:**
- Cannot model competitive binding (multi-component requires vectorization)
- Cannot model high-loading (nonlinear isotherm)
- Cannot model sharp saturation fronts

---

## 2. GRM Governing Equations

### 2.1 Column Mass Balance (Bulk Phase)

```
∂c_b/∂t + v ∂c_b/∂z = D_ax ∂²c_b/∂z² - (1-ε_c)/ε_c · 3/r_p · k_f · (c_b - c_p|r=r_p)
```

**Variables:**
- `c_b(z,t)`: Bulk phase concentration [mol/m³]
- `v`: Interstitial velocity [m/s]
- `D_ax`: Axial dispersion coefficient [m²/s]
- `ε_c`: Column porosity [-]
- `r_p`: Particle radius [m]
- `k_f`: Film mass transfer coefficient [m/s]
- `c_p|r=r_p`: Particle surface concentration [mol/m³]

**Physical Meaning:**
- Left side: Accumulation + advection
- Right side: Dispersion - mass transfer to particles

### 2.2 Particle Mass Balance (Pore Phase)

```
ε_p ∂c_p/∂t + (1-ε_p) ∂q/∂t = D_p/r² ∂/∂r(r² ∂c_p/∂r)
```

**Variables:**
- `c_p(z,r,t)`: Pore phase concentration [mol/m³]
- `q(z,r,t)`: Solid phase concentration (bound) [mol/m³]
- `ε_p`: Particle porosity [-]
- `D_p`: Pore diffusion coefficient [m²/s]
- `r`: Radial coordinate within particle [m]

**Boundary Conditions:**
- At particle surface (`r = r_p`): Film mass transfer
  ```
  D_p ∂c_p/∂r|r=r_p = k_f (c_b - c_p|r=r_p)
  ```
- At particle center (`r = 0`): Symmetry
  ```
  ∂c_p/∂r|r=0 = 0
  ```

### 2.3 Binding Kinetics

**Langmuir (Linear):**
```
∂q/∂t = k_a · c_p · (q_max - q) - k_d · q
```

For dilute conditions (q << q_max):
```
∂q/∂t = k_a · q_max · c_p - k_d · q
```

**SMA (Steric Mass Action):**
```
∂q/∂t = k_a · c_p · (Λ - z_p·q)^(ν_p) - k_d · q
```

For small perturbations around base state (c₀, q₀):
```
∂(δq)/∂t = k_a,eff · δc_p - k_d,eff · δq
```

Where:
```
k_a,eff = k_a · (Λ - z_p·q₀)^(ν_p)
k_d,eff = k_d + k_a · c₀ · ν_p · z_p · (Λ - z_p·q₀)^(ν_p-1)
```

---

## 3. Laplace Transform Strategy

### 3.1 Transform Definitions

```
C_b(z,s) = ℒ{c_b(z,t)} = ∫₀^∞ c_b(z,t) e^(-st) dt
C_p(z,r,s) = ℒ{c_p(z,r,t)}
Q(z,r,s) = ℒ{q(z,r,t)}
```

**Key Property:** `ℒ{∂f/∂t} = s·F(s) - f(0)` (assuming zero initial conditions: f(0)=0)

### 3.2 Transformed Equations

**Column balance:**
```
s·C_b + v ∂C_b/∂z = D_ax ∂²C_b/∂z² - (1-ε_c)/ε_c · 3/r_p · k_f · (C_b - C_p|r=r_p)
```

**Particle balance:**
```
(s·ε_p + (1-ε_p)·s·Q/C_p) · C_p = D_p/r² · d/dr(r² dC_p/dr)
```

**Binding (Langmuir):**
```
Q = (k_a·q_max)/(s + k_d) · C_p
```

Substituting binding into particle balance:
```
s · [ε_p + (1-ε_p)·k_a·q_max/(s+k_d)] · C_p = D_p/r² · d/dr(r² dC_p/dr)
```

Define **effective particle accumulation factor:**
```
β(s) = ε_p + (1-ε_p) · k_a·q_max/(s+k_d)
```

Then:
```
s·β(s)·C_p = D_p/r² · d/dr(r² dC_p/dr)
```

---

## 4. Particle Problem Solution

### 4.1 Radial Diffusion with Binding

**ODE in Laplace space:**
```
d²C_p/dr² + 2/r · dC_p/dr - (s·β(s)/D_p) · C_p = 0
```

**Substitution:** Let `u(r) = r·C_p(r)`, then:
```
d²u/dr² - (s·β(s)/D_p) · u = 0
```

**General solution:**
```
u(r) = A·sinh(√(s·β(s)/D_p) · r) + B·cosh(√(s·β(s)/D_p) · r)
```

**Boundary condition at r=0 (symmetry):**
- Require: `C_p(0)` finite
- This forces: `B = 0` (since cosh(0)=1 but u(0)=0)

So:
```
C_p(r,s) = (A/r) · sinh(√(s·β(s)/D_p) · r)
```

**Boundary condition at r=r_p (film mass transfer):**
```
D_p · dC_p/dr|r=r_p = k_f · (C_b - C_p|r=r_p)
```

Taking derivative:
```
dC_p/dr = A · [√(s·β/D_p)·cosh(√(s·β/D_p)·r)/r - sinh(√(s·β/D_p)·r)/r²]
```

At `r = r_p`:
```
D_p · A · [√(s·β/D_p)·cosh(ξ)/r_p - sinh(ξ)/r_p²] = k_f · [C_b - A·sinh(ξ)/r_p]
```

Where: `ξ = r_p · √(s·β(s)/D_p)` (dimensionless)

**Solving for A:**
```
A = C_b · r_p / [sinh(ξ) + (k_f/D_p)·r_p·(sinh(ξ)/ξ - cosh(ξ))]
```

**Simplification using Biot number:**
```
Bi = k_f · r_p / D_p  (film resistance relative to pore diffusion)
```

**Surface concentration:**
```
C_p|r=r_p = C_b · sinh(ξ) / [sinh(ξ) + Bi·(sinh(ξ)/ξ - cosh(ξ))]
```

Define **particle transfer function:**
```
Φ(s) = C_p|r=r_p / C_b = sinh(ξ) / [sinh(ξ) + Bi·(sinh(ξ) - ξ·cosh(ξ))/ξ]
```

### 4.2 Average Particle Concentration

For column balance, we need:
```
⟨C_p⟩ = (3/r_p³) · ∫₀^r_p C_p(r) · r² dr
```

**Integral:**
```
∫₀^r_p (A/r)·sinh(√(s·β/D_p)·r) · r² dr
= (A·r_p²/ξ²) · [sinh(ξ) - ξ·cosh(ξ)]
```

**Result:**
```
⟨C_p⟩ = C_b · 3/ξ² · [sinh(ξ) - ξ·cosh(ξ)] / [sinh(ξ) + Bi·(sinh(ξ) - ξ·cosh(ξ))/ξ]
```

---

## 5. Column Problem Solution

### 5.1 Effective Column Equation

**Mass balance with particle sink:**
```
s·C_b + v·dC_b/dz = D_ax·d²C_b/dz² - (1-ε_c)/ε_c · s·β(s)·⟨C_p⟩
```

Using `⟨C_p⟩ = η(s)·C_b` where η(s) is the effective particle response:
```
η(s) = 3/ξ² · [sinh(ξ) - ξ·cosh(ξ)] / [sinh(ξ) + Bi·(sinh(ξ) - ξ·cosh(ξ))/ξ]
```

**Combined:**
```
s·[1 + (1-ε_c)/ε_c · β(s)·η(s)] · C_b + v·dC_b/dz = D_ax·d²C_b/dz²
```

Define **effective retardation factor:**
```
R_eff(s) = 1 + (1-ε_c)/ε_c · β(s)·η(s)
```

**Dimensionless form:**

Let `Z = z/L` (dimensionless axial position), then:
```
s·R_eff(s)·C_b + (v·L)·dC_b/dZ = (D_ax·L)·d²C_b/dZ²
```

Divide by `D_ax·L`:
```
(s·L²/D_ax)·R_eff(s)·C_b + Pe·dC_b/dZ = d²C_b/dZ²
```

Where: `Pe = v·L/D_ax` (Peclet number)

### 5.2 Transfer Function Derivation

**Standard form:**
```
d²C_b/dZ² - Pe·dC_b/dZ - (s·L²/D_ax)·R_eff(s)·C_b = 0
```

**Characteristic equation:**
```
λ² - Pe·λ - (s·L²/D_ax)·R_eff(s) = 0
```

**Roots:**
```
λ = Pe/2 ± √[(Pe/2)² + (s·L²/D_ax)·R_eff(s)]
```

**Danckwerts boundary conditions:**
- Inlet (Z=0): `C_b(0) - (1/Pe)·dC_b/dZ|Z=0 = C_inlet`
- Outlet (Z=1): `dC_b/dZ|Z=1 = 0`

**Transfer function (after algebraic manipulation):**
```
F(s) = C_b(Z=1)/C_inlet = exp(Pe/2 · (1 - √[1 + 4·s·τ²·R_eff(s)/Pe]))
```

Where: `τ = L/v` (residence time)

---

## 6. Final Transfer Functions

### 6.1 Langmuir with Kinetic Binding and Particle Dynamics

**Full GRM transfer function:**

```python
def grm_langmuir_transfer(
    velocity: float,      # [m/s]
    dispersion: float,    # [m²/s]
    length: float,        # [m]
    col_porosity: float,  # [-]
    par_radius: float,    # [m]
    par_porosity: float,  # [-]
    film_diffusion: float,  # [m/s]
    pore_diffusion: float,  # [m²/s]
    ka: float,            # [1/s]
    kd: float,            # [1/s]
    qmax: float,          # [mol/m³]
) -> Callable[[complex], complex]:

    Pe = velocity * length / dispersion
    tau = length / velocity
    Bi = film_diffusion * par_radius / pore_diffusion
    phase_ratio = (1 - col_porosity) / col_porosity

    def F(s: complex) -> complex:
        # Effective binding capacity
        beta = par_porosity + (1 - par_porosity) * ka * qmax / (s + kd)

        # Particle diffusion parameter
        xi = par_radius * cmath.sqrt(s * beta / pore_diffusion)

        # Particle response function (hyperbolic functions)
        sinh_xi = cmath.sinh(xi)
        cosh_xi = cmath.cosh(xi)

        # Avoid division by zero
        if abs(xi) < 1e-10:
            # Taylor expansion for small xi
            eta = 1.0  # Limit as xi→0
        else:
            numerator = 3 * (sinh_xi - xi * cosh_xi)
            denominator = xi**2 * (sinh_xi + Bi * (sinh_xi - xi * cosh_xi) / xi)
            eta = numerator / denominator

        # Effective retardation
        R_eff = 1 + phase_ratio * beta * eta

        # Column transfer function
        inner = 1 + 4 * s * tau**2 * R_eff / Pe
        return cmath.exp(Pe / 2 * (1 - cmath.sqrt(inner)))

    return F
```

**Simplified limits:**

1. **Fast film + pore diffusion (Bi→∞, xi→0):**
   - η → 1 (instant particle equilibrium)
   - Reduces to: `R_eff = 1 + phase_ratio * [ε_p + (1-ε_p)·ka·qmax/(s+kd)]`
   - This is the **equilibrium retardation** model

2. **Fast binding kinetics (kd→∞):**
   - β → ε_p + (1-ε_p) (particle just acts as void volume)
   - Binding dynamics disappear

3. **No binding (ka=0):**
   - β → ε_p
   - Reduces to **advection-dispersion with particle holdup**

### 6.2 SMA (Steric Mass Action) with Linearization

**Linearized SMA binding:**

For small perturbations around base state (c₀, q₀):
```
∂(δq)/∂t = k_a,eff · δc_p - k_d,eff · δq
```

**Effective rate constants:**
```python
# Base state from equilibrium
Λ_eff = Λ - z_salt * c_salt  # Effective capacity
q0 = Λ_eff / (1 + (k_d / (k_a * c0)) * Λ_eff**(-nu))  # Equilibrium bound

# Linearized rates
k_a_eff = k_a * (Λ_eff - z_protein * q0)**nu
k_d_eff = k_d + k_a * c0 * nu * z_protein * (Λ_eff - z_protein * q0)**(nu - 1)
```

**Transfer function:** Same form as Langmuir, but use k_a_eff, k_d_eff:

```python
def grm_sma_transfer(
    velocity: float,
    dispersion: float,
    length: float,
    col_porosity: float,
    par_radius: float,
    par_porosity: float,
    film_diffusion: float,
    pore_diffusion: float,
    ka: float,           # [m³/(mol·s)]
    kd: float,           # [1/s]
    Lambda: float,       # Steric capacity [mol/m³]
    nu: float,           # Characteristic charge [-]
    z_protein: float,    # Protein charge [-]
    z_salt: float,       # Salt valence [-]
    c0: float,           # Base protein concentration [mol/m³]
    c_salt: float,       # Salt concentration [mol/m³]
) -> Callable[[complex], complex]:

    # Compute base state
    Lambda_eff = Lambda - z_salt * c_salt
    # Solve: q0 = K_eq * c0 * (Lambda_eff - z_protein*q0)^nu
    # For simplicity, use low-loading approximation: q0 ≈ K_eq * c0 * Lambda_eff^nu
    K_eq = ka / kd
    q0 = K_eq * c0 * Lambda_eff**nu / (1 + K_eq * c0 * Lambda_eff**(nu-1))

    # Linearized rate constants
    shield_term = Lambda_eff - z_protein * q0
    k_a_eff = ka * shield_term**nu
    k_d_eff = kd + ka * c0 * nu * z_protein * shield_term**(nu - 1)

    # Use Langmuir form with effective rates
    return grm_langmuir_transfer(
        velocity=velocity,
        dispersion=dispersion,
        length=length,
        col_porosity=col_porosity,
        par_radius=par_radius,
        par_porosity=par_porosity,
        film_diffusion=film_diffusion,
        pore_diffusion=pore_diffusion,
        ka=k_a_eff,
        kd=k_d_eff,
        qmax=Lambda_eff,  # Effective capacity
    )
```

---

## 7. Validation Strategy

### 7.1 Limiting Cases

**Test 1: Fast kinetics (kd >> 1)**
- Should reduce to advection-dispersion with particle holdup
- Compare with: `advection_dispersion_transfer()` with modified velocity

**Test 2: Fast diffusion (k_f, D_p >> 1)**
- Should reduce to equilibrium retardation model
- Compare with: `langmuir_column_transfer()` (current implementation)

**Test 3: No binding (ka = 0)**
- Should give pure transport
- Compare with: `advection_dispersion_transfer()`

### 7.2 CADET Validation

**Procedure:**
1. Configure CADET with full GRM (particles, binding, diffusion)
2. Run CADET simulation
3. Run NILT with `grm_langmuir_transfer()` using **same parameters**
4. Compare: Relative L2 error should be < 1%

**Test cases:**
- **P3 (dilute Langmuir):** ka=1.0, kd=0.1, qmax=100.0
- **P10 (stiff kinetics):** ka=100.0, kd=10.0, qmax=100.0
- **New: SMA example:** IgG on Protein A resin

---

## 8. Implementation Checklist

- [x] Mathematical derivation complete
- [ ] Implement `grm_langmuir_transfer()` in `/cadet_lab/nilt/benchmarks.py`
- [ ] Implement `grm_sma_transfer()` in `/cadet_lab/nilt/benchmarks.py`
- [ ] Add hyperbolic function helpers (sinh, cosh in complex domain)
- [ ] Update P3 problem to use `grm_langmuir_transfer()`
- [ ] Update P10 problem to use `grm_langmuir_transfer()`
- [ ] Create P11: SMA benchmark problem
- [ ] Validation tests: Limiting cases
- [ ] Validation tests: CADET comparison
- [ ] Update PHASE_D_TRACK1_REPORT.md with new results

---

## References

1. Guiochon et al., "Fundamentals of Preparative and Nonlinear Chromatography" (2006)
2. CADET Documentation: General Rate Model equations
3. Leweke & von Lieres, "Chromatography Analysis and Design Toolkit (CADET)" (2018)
4. Brooks & Cramer, "Steric mass-action ion exchange" (1992)

---

**Derivation Status:** ✅ Complete
**Implementation Status:** ⏳ In Progress
**Next Step:** Implement transfer functions in Python
