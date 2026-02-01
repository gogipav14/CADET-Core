# Phase C Operationalization: Implementation Guide

## Overview

Phase C transforms the validation infrastructure into a production decision engine that produces:

1. **Recommended tolerance settings per case** (accuracy vs cost optimized)
2. **Minimum spatial resolution requirements per case**
3. **Phase D trigger decision** (whether solver/preconditioning work warranted)

This guide explains how to execute the Phase C operationalization workflow.

---

## Prerequisites

**Infrastructure Complete:**
- ✅ Full-state telemetry (bulk, particle, solid profiles)
- ✅ Accuracy metrics (SUNDIALS-compliant scaled RMS, L∞)
- ✅ Reference protocol (time-mode and space-mode)
- ✅ Tolerance sweep (work-precision analysis)
- ✅ Spatial convergence (with interpolation)
- ✅ Stress suite integration
- ✅ Linear iteration counter exposure (Phase D prep)
- ✅ Coordinate confidence tracking

**Required:**
- `cadet-cli` executable (CADET v6.x or later)
- Python 3.8+ with dependencies: `numpy`, `scipy`, `h5py`

---

## Execution Workflow

### Step 1: Run Production Work-Precision Sweeps

**Purpose:** Generate complete 4×4 tolerance sweeps (16 points each) for all stress cases against time-mode references.

**Command:**

```bash
python cadet-lab-tools/scripts/run_production_sweeps.py \
  --cadet-cli /path/to/cadet-cli \
  --output-dir ./artifacts \
  --cases first_step_fail sharp_front discontinuous_section stiff_binding \
  --tolerance-factor 100.0
```

**What It Does:**

For each case:
1. Generates time-mode reference with very tight tolerances (ABSTOL/100, RELTOL/100)
2. Runs 4×4 tolerance sweep:
   - ABSTOL grid: [1e-9, 3e-9, 1e-8, 3e-8]
   - RELTOL grid: [1e-6, 3e-6, 1e-5, 3e-5]
   - Total: 16 sweep points per case
3. Compares each sweep point against reference using full-state metrics
4. Saves `artifacts/<case>/work_precision_full_state.json`

**Outputs:**

```
artifacts/
├── first_step_fail/
│   ├── work_precision_full_state.json
│   ├── cache/
│   ├── reference/
│   └── sweep/
├── sharp_front/...
├── discontinuous_section/...
└── stiff_binding/...
```

**Expected Runtime:** ~30-60 minutes (4 cases × 17 runs each)

**Caching:** References are cached in `cache/` to prevent expensive re-computation. Delete cache to force regeneration.

---

### Step 2: Run Spatial Convergence Checks

**Purpose:** Verify spatial discretization adequacy via refinement study.

**Command:**

```bash
python cadet-lab-tools/scripts/run_spatial_convergence.py \
  --cadet-cli /path/to/cadet-cli \
  --output-dir ./artifacts \
  --cases first_step_fail sharp_front discontinuous_section stiff_binding
```

**What It Does:**

**Sharp Front (Iterative Resolution Finder):**
- Starts with baseline (NELEM=8)
- Refines by 2×: compare refined vs baseline
- Checks: `scaled_rms_delta <= 1e-3` AND `delta(n+1) < delta(n)` (trend decrease)
- Continues until convergence OR max 3 levels (8→16→32)
- Expected: Requires 2-3 refinement levels

**Other Cases (Single 2× Refinement Check):**
- Single refinement: baseline → 2× refined
- Checks: `scaled_rms_delta <= 1e-2`
- Expected: Convergence at 2× for most cases

**Outputs:**

```
artifacts/
├── first_step_fail/
│   └── spatial_convergence.json
├── sharp_front/
│   └── spatial_convergence.json (with refinement_levels > 1)
├── discontinuous_section/
│   └── spatial_convergence.json
└── stiff_binding/
    └── spatial_convergence.json
```

**Expected Runtime:** ~20-40 minutes (sharp_front takes longest)

**Coordinate Confidence Tracking:**
- Checks if HDF5 contains `AXIAL_COORDINATES`, `PARTICLE_COORDINATES`
- If present: `confidence_level = "high"`, `interpolation_method = "coordinate-based"`
- If absent (CADET v6.x): `confidence_level = "medium"` (uniform) or `"low"` (sharp fronts)
- Warnings added for low-confidence cases

---

### Step 3: Generate Tolerance Recommendations

**Purpose:** Apply acceptance gates and select optimal tolerance settings per case.

**Command:**

```bash
python cadet-lab-tools/cadet_lab/validation/recommend_settings.py \
  --artifacts-dir ./artifacts \
  --output ./artifacts/phase_c_recommended_settings.json \
  --scaled-rms-threshold 1.0 \
  --step-threshold 500
```

**What It Does:**

1. **Loads work-precision sweeps** from `artifacts/<case>/work_precision_full_state.json`

2. **Applies Acceptance Gates:**
   - `scaled_rms_global <= 1.0` (tolerance-scaled error acceptable)
   - `num_err_test_fails <= 10` (stability constraint)
   - Optional: `linf_global <= linf_threshold` (case-dependent)

3. **Selects Optimal Point:** Cheapest sweep point meeting all gates (minimize `num_steps`)

4. **Phase D Trigger Decision** (ANY of):
   - Convergence pressure: `num_conv_fails > 0`
   - Step budget pressure: `min_steps_meeting_gates > 500`
   - Very tight tolerances: `min_abstol_for_gates < 1e-9`

5. **Saves:** `artifacts/phase_c_recommended_settings.json`

**Output Format:**

```json
{
  "metadata": {
    "gates": {
      "scaled_rms_global": 1.0,
      "max_err_test_fails": 10
    },
    "timestamp": "2026-01-31T..."
  },
  "phase_d_decision": {
    "triggered": false,
    "reasons": [],
    "notes": "0 conv_fails observed. No solver work warranted."
  },
  "first_step_fail": {
    "abstol": 1e-8,
    "reltol": 1e-5,
    "expected_steps": 107,
    "accuracy": {
      "scaled_rms_error": 0.0679,
      "linf_error": 1.299e-05
    },
    "solver_stats": {
      "num_err_test_fails": 3,
      "num_conv_fails": 0,
      "wall_time": 0.234
    }
  },
  "sharp_front": {...},
  "discontinuous_section": {...},
  "stiff_binding": {...}
}
```

**Expected Outcome:** Phase D NOT triggered (triage showed 0 conv_fails across all cases)

---

### Step 4: Run Full-State Stress Suite Baseline

**Purpose:** Generate comprehensive baseline with all 4 cases for measuring improvement.

**Command:**

```bash
python cadet-lab-tools/scripts/run_stress_suite_baseline.py \
  --cadet-cli /path/to/cadet-cli \
  --output-dir ./artifacts/stress_suite_baseline \
  --output-file ./artifacts/stress_suite_results_full_state.json
```

**What It Does:**

1. Runs all 4 stress cases with default settings
2. Enables full-state output (bulk, particle, solid)
3. Collects solver stats: steps, err_test_fails, conv_fails, lin_iters (if available)
4. Saves comprehensive JSON artifact

**Output:**

```
artifacts/
└── stress_suite_results_full_state.json
```

**Use Case:** Baseline for comparing against optimized settings from Step 3.

---

## Interpreting Results

### Work-Precision Curves

**Goal:** Understand accuracy/cost trade-off.

**Key Metrics:**
- `scaled_rms_error`: How well does sweep point match reference (within tolerance-scaled error)?
- `num_steps`: Primary cost metric (fewer is better)
- `num_err_test_fails`: Stability indicator (lower is better)

**Pareto Frontier:** Points on the accuracy/cost Pareto frontier are candidates for recommendation.

**Example Analysis:**

| abstol | reltol | steps | scaled_rms | linf_error | err_fails | Status |
|--------|--------|-------|------------|------------|-----------|--------|
| 1e-9   | 1e-6   | 245   | 0.023      | 3.2e-6     | 0         | Overkill (expensive, high accuracy) |
| 3e-9   | 3e-6   | 189   | 0.145      | 8.7e-6     | 2         | Good balance |
| 1e-8   | 1e-5   | 107   | 0.679      | 1.3e-5     | 3         | **Optimal** (cheapest meeting gates) |
| 3e-8   | 3e-5   | 89    | 2.341      | 4.5e-5     | 9         | Too loose (fails scaled_rms gate) |

**Recommendation:** `abstol=1e-8, reltol=1e-5` (cheapest point with `scaled_rms < 1.0`)

---

### Spatial Convergence

**Goal:** Verify spatial resolution adequacy.

**Key Metrics:**
- `scaled_rms_delta`: Difference between refined and baseline (within tolerance-scaled error)
- `convergence_achieved`: Did refinement meet threshold?
- `confidence_level`: Quality of convergence check (high/medium/low)

**Sharp Front Expected Behavior:**

```json
{
  "case_name": "sharp_front",
  "convergence_achieved": true,
  "refinement_levels": 2,
  "threshold": 0.001,
  "convergence_history": [
    {"level": 1, "refinement_factor": 2, "scaled_rms_delta": 0.0567},
    {"level": 2, "refinement_factor": 4, "scaled_rms_delta": 0.0009}
  ],
  "baseline_resolution": {"nelem_col": 8, "nelem_par": 4},
  "recommended_resolution": {"nelem_col": 32, "nelem_par": 16},
  "confidence_level": "medium",
  "warnings": ["Coordinates not present in HDF5 output..."]
}
```

**Interpretation:**
- ✅ Convergence achieved at level 2 (8→32 for column)
- ⚠️ Coordinate confidence is "medium" (uniform grid fallback)
- **Recommendation:** Use NELEM=32 for sharp_front (or 16 as compromise)

---

### Phase D Decision

**Trigger Conditions (ANY of):**

1. **Convergence failures:** `num_conv_fails > 0`
   - Indicates Newton solver struggling
   - Action: Investigate preconditioning, linear solver settings

2. **Step budget pressure:** `min_steps_meeting_gates > 500`
   - Even loosest acceptable tolerances are expensive
   - Action: Improve solver efficiency (better preconditioner, Krylov methods)

3. **Very tight tolerances:** `min_abstol_for_gates < 1e-9`
   - Physical problem extremely stiff
   - Action: Consider reformulation, spatial refinement, solver tuning

**Current Expectation:** Phase D NOT triggered
- Triage showed 0 conv_fails across all cases
- Step advisor successfully reduced err_test_fails
- Recommended tolerances in reasonable range (1e-8 to 1e-6)

**If Triggered:**
- Proceed to Phase D: solver/preconditioning optimization
- Use linear iteration counts (`num_lin_iters`, `num_gmres_restarts`) to quantify impact

---

## File Structure Summary

```
artifacts/
├── first_step_fail/
│   ├── work_precision_full_state.json      # 16-point tolerance sweep
│   ├── spatial_convergence.json            # Spatial adequacy check
│   ├── cache/                              # Reference cache
│   ├── reference/                          # Time-mode reference outputs
│   └── sweep/                              # Sweep run outputs
├── sharp_front/
│   ├── work_precision_full_state.json
│   ├── spatial_convergence.json            # Iterative refinement (levels > 1)
│   └── ...
├── discontinuous_section/...
├── stiff_binding/...
├── phase_c_recommended_settings.json       # Optimal tolerances per case
└── stress_suite_results_full_state.json    # Baseline benchmark
```

---

## Configuration Tuning

### Acceptance Gate Thresholds

**Default:**
```python
SCALED_RMS_GLOBAL_MAX = 1.0          # Tolerance-scaled error within 1×
MAX_ERR_TEST_FAILS = 10              # Stability constraint
```

**Stricter (Physics Validation):**
```python
SCALED_RMS_GLOBAL_MAX = 0.5          # Half of tolerance-scaled error
MAX_ERR_TEST_FAILS = 5
```

**More Permissive (Engineering Estimates):**
```python
SCALED_RMS_GLOBAL_MAX = 2.0
MAX_ERR_TEST_FAILS = 20
```

**How to Apply:**

```bash
python cadet-lab-tools/cadet_lab/validation/recommend_settings.py \
  --scaled-rms-threshold 0.5 \
  --artifacts-dir ./artifacts \
  --output ./artifacts/phase_c_recommended_settings_strict.json
```

---

### Spatial Convergence Thresholds

**Sharp Front (Tight):**
```python
SPATIAL_DELTA_MAX = 1e-3  # Strict for spatial challenge cases
```

**Default Cases (Looser):**
```python
SPATIAL_DELTA_MAX = 1e-2
```

**Modify in Script:**

Edit `cadet-lab-tools/scripts/run_spatial_convergence.py`:

```python
case_configs = {
    "sharp_front": {
        "threshold": 1e-4,  # Even tighter
        ...
    },
    ...
}
```

---

## Troubleshooting

### Issue: Reference simulation fails

**Symptoms:**
```
RuntimeError: Reference simulation failed with return code 1.
Failure reason: CONVERGENCE_FAIL.
```

**Cause:** Tolerance tightening factor too aggressive (e.g., 100× on already tight base tolerances).

**Solution:**
1. Check base case tolerances in `cadet_lab/stress_suite/cases.py`
2. Reduce `--tolerance-factor` (try 10.0 instead of 100.0)
3. Or, increase base tolerances in case generator

---

### Issue: All sweep points fail gates

**Symptoms:**
```json
{
  "first_step_fail": {
    "status": "FAILED",
    "note": "No tolerance point meeting acceptance gates"
  }
}
```

**Cause:** Acceptance gates too strict OR all sweep points have high errors.

**Debugging:**
1. Inspect `work_precision_full_state.json` manually
2. Check `scaled_rms_error` values for all points
3. If all > 1.0: reference may be incorrect OR spatial resolution insufficient

**Solution:**
- Re-run spatial convergence check
- Increase baseline NELEM in case generator
- Or, relax `--scaled-rms-threshold`

---

### Issue: Spatial convergence never achieved

**Symptoms:**
```json
{
  "convergence_achieved": false,
  "refinement_levels": 3,
  "final_scaled_rms_delta": 0.0156
}
```

**Cause:** Sharp front requires NELEM > 32 OR coordinate fallback inaccurate.

**Solution:**
1. Increase `max_refinement_levels` to 4 (8→64)
2. Check `confidence_level`: if "low", spatial convergence may be unreliable
3. If CADET supports coordinates: ensure `WRITE_COORDINATES=1` in config

---

### Issue: Phase D triggered unexpectedly

**Symptoms:**
```json
{
  "phase_d_decision": {
    "triggered": true,
    "reasons": ["stiff_binding: High step count (612 > 500)"]
  }
}
```

**Cause:** Step threshold too conservative OR case inherently expensive.

**Action:**
1. Check if 612 steps is acceptable for `stiff_binding` (it's a stiff case!)
2. Increase `--step-threshold` to 800
3. Or, proceed to Phase D if solver optimization desired

---

## Next Steps

### If Phase D NOT Triggered (Expected):

1. **Apply recommended settings** to production workflows
2. **Document baseline performance** (stress suite results)
3. **Monitor in production** for unexpected failures
4. **Re-run Phase C** if new cases added or physics changed

### If Phase D Triggered:

1. **Review trigger reasons** (conv_fails, step_budget, tight tolerances)
2. **Collect linear iteration baselines** (`num_lin_iters`, `num_gmres_restarts`)
3. **Design Phase D experiments:**
   - Preconditioner tuning (incomplete LU, multigrid)
   - Krylov method selection (GMRES vs BiCGSTAB)
   - Linear solver tolerances
4. **Quantify impact** using work-precision framework

---

## Validation Checklist

- [ ] All 4 cases have `work_precision_full_state.json` with 16 points
- [ ] All 4 cases have `spatial_convergence.json`
- [ ] `phase_c_recommended_settings.json` generated
- [ ] `stress_suite_results_full_state.json` baseline exists
- [ ] All recommended settings tested (spot check)
- [ ] Phase D decision documented with evidence
- [ ] Coordinate confidence warnings present where applicable
- [ ] Linear iteration counters tracked (even if None)

---

## Summary of Tools

| Tool | Purpose | Runtime |
|------|---------|---------|
| `run_production_sweeps.py` | Generate 4×4 tolerance sweeps per case | 30-60 min |
| `run_spatial_convergence.py` | Verify spatial resolution adequacy | 20-40 min |
| `recommend_settings.py` | Select optimal tolerances + Phase D decision | <1 min |
| `run_stress_suite_baseline.py` | Baseline benchmark for improvement | 5-10 min |

**Total Time:** ~1-2 hours for complete Phase C execution

---

## References

- **Phase C Integration Tests:** `cadet-lab-tools/test_integration_phase_c.py`
- **Stress Cases:** `cadet-lab-tools/cadet_lab/stress_suite/cases.py`
- **Full-State Metrics:** `cadet-lab-tools/cadet_lab/telemetry/full_state_metrics.py`
- **Spatial Convergence:** `cadet-lab-tools/cadet_lab/validation/spatial_convergence.py`
- **Tolerance Sweep:** `cadet-lab-tools/cadet_lab/validation/tolerance_sweep.py`

---

## Contact

For issues, questions, or suggestions:
- Review integration tests: `pytest cadet-lab-tools/test_integration_phase_c.py -v`
- Check implementation summary: `PHASE_C_IMPLEMENTATION_SUMMARY.md`
- Consult test results: `PHASE_C_TEST_RESULTS.md`
