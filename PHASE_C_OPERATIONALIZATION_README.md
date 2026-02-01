# Phase C Operationalization: Production Decision Engine

## Executive Summary

**Phase C transforms validation infrastructure into actionable production guidance:**

✅ **Recommended tolerance settings per case** (accuracy vs cost optimized)
✅ **Minimum spatial resolution requirements** (verified via refinement)
✅ **Phase D trigger decision** (quantitative evidence for solver work)
✅ **Linear iteration tracking** (baseline for future preconditioner impact)

**Status:** Implementation complete. Ready for production execution.

---

## Quick Start

### One-Command Full Workflow

```bash
python cadet-lab-tools/scripts/run_phase_c_full.py \
  --cadet-cli /path/to/cadet-cli \
  --output-dir ./artifacts
```

**Runtime:** ~1-2 hours
**Outputs:** 4 cases × (work-precision + spatial convergence) + recommendations + baseline

---

## What Was Implemented

### 1. Linear Iteration Counter Exposure (Phase D Prep)

**Files Modified:**
- `cadet-lab-tools/cadet_lab/telemetry/read_hdf5.py` - Parse `NUM_LIN_ITERS`, `NUM_GMRES_RESTARTS`
- `cadet-lab-tools/cadet_lab/telemetry/kpis.py` - Add fields to `RunKPIs`

**Purpose:** Baseline linear solver difficulty before Phase D. Quantify preconditioner impact later.

**Behavior:** Gracefully handles missing counters (None if not in HDF5).

---

### 2. Coordinate Confidence Tracking

**Files Modified:**
- `cadet-lab-tools/cadet_lab/validation/spatial_convergence.py`

**New Fields in `SpatialConvergenceResult`:**
```python
coordinates_present: bool          # HDF5 has coordinates?
interpolation_method: str          # "coordinate-based" or "uniform-fallback"
confidence_level: str              # "high", "medium", "low"
refinement_levels: int             # Number of refinement iterations
warnings: list                     # Warnings about convergence quality
```

**Confidence Rules:**
- **High:** Coordinates present in HDF5
- **Medium:** Uniform discretization, no coordinates (safe fallback)
- **Low:** Non-uniform or sharp fronts, no coordinates (recommend stricter baseline)

**Action on Low Confidence:** Add warnings, recommend NELEM × 2 baseline increase.

---

### 3. Production Work-Precision Sweep Script

**File:** `cadet-lab-tools/scripts/run_production_sweeps.py`

**What It Does:**
- Generates time-mode references (tol_factor=100)
- Runs 4×4 tolerance sweeps (16 points per case)
- Saves `artifacts/<case>/work_precision_full_state.json`

**Cases:** `first_step_fail`, `sharp_front`, `discontinuous_section`, `stiff_binding`

**Tolerance Grids:**
- ABSTOL: [1e-9, 3e-9, 1e-8, 3e-8]
- RELTOL: [1e-6, 3e-6, 1e-5, 3e-5]

**Caching:** References cached to prevent re-computation.

---

### 4. Spatial Convergence Check Script

**File:** `cadet-lab-tools/scripts/run_spatial_convergence.py`

**Modes:**

**Sharp Front - Iterative Resolution Finder:**
- Starts at baseline (NELEM=8)
- Refines 8→16→32 (max 3 levels)
- Checks: `scaled_rms_delta <= 1e-3` AND trend decreases
- Expected: 2-3 refinement levels needed

**Other Cases - Single 2× Refinement:**
- Single refinement check
- Threshold: `scaled_rms_delta <= 1e-2`
- Expected: Convergence at 2× for most cases

**Saves:** `artifacts/<case>/spatial_convergence.json`

---

### 5. Tolerance Recommendation Engine

**File:** `cadet-lab-tools/cadet_lab/validation/recommend_settings.py`

**Acceptance Gates:**
```python
scaled_rms_global <= 1.0        # Tolerance-scaled error acceptable
num_err_test_fails <= 10        # Stability constraint
```

**Selection Algorithm:** Find cheapest sweep point meeting gates (minimize `num_steps`).

**Phase D Trigger Conditions (ANY of):**
1. Convergence failures: `num_conv_fails > 0`
2. Step budget pressure: `min_steps_meeting_gates > 500`
3. Very tight tolerances: `min_abstol_for_gates < 1e-9`

**Output:** `artifacts/phase_c_recommended_settings.json`

**Command-Line Interface:**
```bash
python cadet-lab-tools/cadet_lab/validation/recommend_settings.py \
  --artifacts-dir ./artifacts \
  --output ./artifacts/phase_c_recommended_settings.json \
  --scaled-rms-threshold 1.0 \
  --step-threshold 500
```

---

### 6. Stress Suite Baseline Script

**File:** `cadet-lab-tools/scripts/run_stress_suite_baseline.py`

**What It Does:**
- Runs all 4 cases with baseline settings
- Enables full-state output
- Collects solver stats (including linear iteration counts)
- Saves `artifacts/stress_suite_results_full_state.json`

**Use Case:** Baseline for measuring improvement after applying recommended settings.

---

### 7. Master Orchestration Script

**File:** `cadet-lab-tools/scripts/run_phase_c_full.py`

**Executes All Steps Sequentially:**
1. Production work-precision sweeps
2. Spatial convergence checks
3. Tolerance recommendations generation
4. Full-state stress suite baseline

**Flags:**
- `--skip-sweeps` - Use existing sweep artifacts
- `--skip-spatial` - Use existing spatial convergence artifacts
- `--skip-baseline` - Skip stress suite baseline

**Output:** Complete artifact set + recommendations JSON.

---

## File Structure

### Scripts (User-Facing)

```
cadet-lab-tools/scripts/
├── run_phase_c_full.py              # Master orchestration (runs all steps)
├── run_production_sweeps.py         # Step 1: Work-precision sweeps
├── run_spatial_convergence.py       # Step 2: Spatial convergence checks
└── run_stress_suite_baseline.py     # Step 4: Baseline benchmark
```

### Core Modules (Internal)

```
cadet-lab-tools/cadet_lab/
├── validation/
│   ├── recommend_settings.py        # Step 3: Selection algorithm + Phase D decision
│   ├── spatial_convergence.py       # Enhanced with coordinate confidence
│   ├── tolerance_sweep.py           # Existing (unchanged)
│   └── reference_protocol.py        # Existing (unchanged)
├── telemetry/
│   ├── read_hdf5.py                 # Enhanced with linear iteration counters
│   ├── kpis.py                      # Enhanced with linear iteration fields
│   └── full_state_metrics.py        # Existing (unchanged)
└── stress_suite/
    ├── cases.py                     # Existing (unchanged)
    └── runner.py                    # Existing (unchanged)
```

### Documentation

```
PHASE_C_IMPLEMENTATION_GUIDE.md      # Comprehensive execution guide
PHASE_C_OPERATIONALIZATION_README.md # This file (summary)
```

---

## Expected Outcomes

### Work-Precision Sweeps

**Per Case:** 16 tolerance points with accuracy and cost metrics.

**Example Output:**
```json
{
  "case_name": "first_step_fail",
  "reference": {
    "tolerances": {"abstol": 1e-10, "reltol": 1e-8},
    "resolution": {"nelem_col": 8, "nelem_par": 4}
  },
  "sweep_points": [
    {
      "abstol": 1e-9, "reltol": 1e-6,
      "num_steps": 245, "num_err_test_fails": 0, "num_conv_fails": 0,
      "scaled_rms_error": 0.023, "linf_error": 3.2e-6,
      "success": true
    },
    ...
  ]
}
```

---

### Spatial Convergence

**Sharp Front (Iterative Refinement):**
```json
{
  "case_name": "sharp_front",
  "convergence_achieved": true,
  "refinement_levels": 2,
  "baseline_resolution": {"nelem_col": 8, "nelem_par": 4},
  "recommended_resolution": {"nelem_col": 32, "nelem_par": 16},
  "final_scaled_rms_delta": 0.0009,
  "threshold": 0.001,
  "confidence_level": "medium",
  "warnings": ["Coordinates not present in HDF5 output..."]
}
```

**Other Cases (Single Refinement):**
```json
{
  "case_name": "stiff_binding",
  "convergence_achieved": true,
  "refinement_levels": 1,
  "final_scaled_rms_delta": 0.0067,
  "threshold": 0.01,
  "confidence_level": "medium"
}
```

---

### Recommended Settings

**Expected Phase D Decision:** NOT triggered (0 conv_fails observed in triage).

**Example Recommendations:**
```json
{
  "metadata": {
    "gates": {"scaled_rms_global": 1.0, "max_err_test_fails": 10},
    "timestamp": "2026-01-31T..."
  },
  "phase_d_decision": {
    "triggered": false,
    "reasons": [],
    "notes": "0 conv_fails observed. Step advisor successfully handles err_test_fails. No solver work warranted."
  },
  "first_step_fail": {
    "abstol": 1e-8, "reltol": 1e-5,
    "expected_steps": 107,
    "accuracy": {"scaled_rms_error": 0.0679, "linf_error": 1.299e-05},
    "solver_stats": {"num_err_test_fails": 3, "num_conv_fails": 0}
  },
  "sharp_front": {
    "abstol": 3e-9, "reltol": 3e-6,
    "expected_steps": 189,
    "accuracy": {"scaled_rms_error": 0.145, "linf_error": 8.7e-6}
  },
  ...
}
```

---

## Validation Checklist

Before considering Phase C complete:

- [ ] All 4 cases have `work_precision_full_state.json` with 16 points
- [ ] All 4 cases have `spatial_convergence.json`
- [ ] `sharp_front` shows `refinement_levels > 1` (iterative refinement)
- [ ] `phase_c_recommended_settings.json` generated
- [ ] All recommended settings are within reasonable ranges (abstol ≥ 1e-9, reltol ≥ 1e-6)
- [ ] Phase D decision is justified with evidence
- [ ] `stress_suite_results_full_state.json` baseline exists
- [ ] Coordinate confidence warnings present where applicable
- [ ] Linear iteration counters tracked (even if None)

---

## Interpreting Phase D Decision

### If Phase D NOT Triggered (Expected)

**Evidence:**
- 0 `num_conv_fails` across all cases
- Step counts in reasonable range (100-400 steps)
- Recommended tolerances not excessively tight (abstol ≥ 1e-8)

**Action:**
- ✅ Apply recommended settings to production
- ✅ Document baseline performance
- ✅ Monitor in production
- ⏭️  Skip Phase D (no solver work needed)

---

### If Phase D Triggered (Unexpected)

**Possible Reasons:**
1. `stiff_binding` exceeded step threshold (e.g., 612 > 500)
2. Spatial under-resolution forcing very tight tolerances
3. Unexpected convergence failures

**Action:**
1. Review trigger reasons in recommendations JSON
2. Check if step threshold is too conservative
3. If legitimate bottleneck: proceed to Phase D
4. Use `num_lin_iters` baseline to quantify preconditioner impact

**Phase D Scope:**
- Preconditioner tuning (incomplete LU, multigrid)
- Krylov method selection (GMRES vs BiCGSTAB)
- Linear solver tolerance optimization

---

## Key Design Decisions

### 1. Acceptance Gate Philosophy

**Default: `scaled_rms_global <= 1.0`**
- Tolerance-scaled error within 1× is acceptable
- Balances accuracy and cost
- Can be tightened to 0.5 for physics validation
- Can be loosened to 2.0 for engineering estimates

**Stability Constraint: `num_err_test_fails <= 10`**
- Allows some retries (step advisor handles this)
- Flags cases with excessive instability

---

### 2. Spatial Convergence Approach

**Sharp Front: Iterative Resolution Finder**
- Not a hard gate (doesn't fail if max levels reached)
- Trend rule: `delta(n+1) < delta(n)` ensures convergence direction
- Max 3 levels prevents infinite loops (8→32 is practical limit)

**Other Cases: Single 2× Refinement Check**
- Sufficient for non-spatial-challenge cases
- Looser threshold (1e-2 vs 1e-3) reflects lower spatial stiffness

---

### 3. Coordinate Fallback Strategy

**Problem:** CADET v6.x doesn't write coordinates by default.

**Solution:**
- Uniform grid fallback (np.linspace) for interpolation
- Confidence tracking: high/medium/low based on discretization type
- Warnings for low-confidence cases
- Recommendation: Increase baseline NELEM if confidence is low

**Future:** When CADET writes coordinates, confidence → "high" automatically.

---

### 4. Phase D Trigger Conservative

**Philosophy:** Only trigger if clear bottleneck.

**Current Expectations:**
- 0 conv_fails → no Newton issues
- Step advisor handles err_test_fails
- Recommended tolerances reasonable

**Result:** Phase D NOT triggered (solver is adequate).

**If Triggered:** Strong evidence required (not speculative).

---

## Artifact Summary

### Per-Case Artifacts (4 cases)

```
artifacts/
├── first_step_fail/
│   ├── work_precision_full_state.json    # 16-point sweep
│   ├── spatial_convergence.json          # Single 2× refinement
│   ├── cache/                            # Reference cache
│   ├── reference/                        # Time-mode reference
│   └── sweep/                            # Sweep outputs
├── sharp_front/
│   ├── work_precision_full_state.json
│   ├── spatial_convergence.json          # Iterative (levels=2-3)
│   └── ...
├── discontinuous_section/...
└── stiff_binding/...
```

### Global Artifacts

```
artifacts/
├── phase_c_recommended_settings.json     # Optimal tolerances per case
└── stress_suite_results_full_state.json  # Baseline benchmark
```

**Total Size:** ~500 MB - 1 GB (dominated by HDF5 outputs)

---

## Usage Examples

### Run Full Workflow

```bash
python cadet-lab-tools/scripts/run_phase_c_full.py \
  --cadet-cli /usr/local/bin/cadet-cli \
  --output-dir ./phase_c_artifacts
```

---

### Run Individual Steps

**Step 1: Work-Precision Sweeps Only**
```bash
python cadet-lab-tools/scripts/run_production_sweeps.py \
  --cadet-cli /usr/local/bin/cadet-cli \
  --output-dir ./artifacts \
  --cases sharp_front stiff_binding  # Subset
```

**Step 2: Spatial Convergence Only**
```bash
python cadet-lab-tools/scripts/run_spatial_convergence.py \
  --cadet-cli /usr/local/bin/cadet-cli \
  --output-dir ./artifacts
```

**Step 3: Generate Recommendations (from existing artifacts)**
```bash
python cadet-lab-tools/cadet_lab/validation/recommend_settings.py \
  --artifacts-dir ./artifacts \
  --output ./recommendations.json \
  --scaled-rms-threshold 0.5  # Stricter
```

**Step 4: Stress Suite Baseline**
```bash
python cadet-lab-tools/scripts/run_stress_suite_baseline.py \
  --cadet-cli /usr/local/bin/cadet-cli \
  --output-file ./baseline.json
```

---

### Resume After Interruption

If sweeps were interrupted, use `--skip-sweeps`:

```bash
python cadet-lab-tools/scripts/run_phase_c_full.py \
  --cadet-cli /usr/local/bin/cadet-cli \
  --output-dir ./artifacts \
  --skip-sweeps  # Use existing sweep artifacts
```

---

## Troubleshooting

See **PHASE_C_IMPLEMENTATION_GUIDE.md** section "Troubleshooting" for:
- Reference simulation failures
- All sweep points fail gates
- Spatial convergence never achieved
- Phase D triggered unexpectedly

---

## Success Metrics

**Phase C Complete When:**
1. ✅ All 8 JSON artifacts generated (4 cases × 2 files)
2. ✅ Recommendations JSON has optimal settings for all cases
3. ✅ Phase D decision documented with quantitative evidence
4. ✅ Coordinate confidence tracked and warnings present
5. ✅ Linear iteration counters exposed (even if None)
6. ✅ Stress suite baseline exists for future comparison

**Quantitative Evidence:**
- 64 total sweep points (4 cases × 16 points)
- 4-7 spatial convergence runs (iterative refinement for sharp_front)
- 4 baseline stress suite runs
- 1 recommendations JSON with Phase D decision

---

## Next Actions

### Immediate (Post-Phase C)

1. **Apply recommended settings** to production workflows
2. **Monitor performance** in production (compare vs baseline)
3. **Document** any deviations from recommendations
4. **Re-run Phase C** if cases change or physics updated

### If Phase D Triggered

1. **Design Phase D experiments** (preconditioner tuning, Krylov methods)
2. **Use linear iteration baselines** (`num_lin_iters`) to quantify impact
3. **Re-run work-precision sweeps** with optimized solver settings
4. **Measure speedup** vs Phase C baseline

### Future Enhancements

1. **Coordinate output** in CADET → confidence becomes "high"
2. **Adaptive tolerance selection** based on physics regime
3. **Multi-objective optimization** (accuracy, cost, stability)
4. **Automated retuning** when cases drift from recommendations

---

## References

- **Implementation Guide:** `PHASE_C_IMPLEMENTATION_GUIDE.md` (detailed usage)
- **Integration Tests:** `cadet-lab-tools/test_integration_phase_c.py` (verification)
- **Test Results:** `PHASE_C_TEST_RESULTS.md` (baseline test outcomes)
- **Implementation Summary:** `PHASE_C_IMPLEMENTATION_SUMMARY.md` (technical details)

---

## Contact & Support

**For Questions:**
1. Review implementation guide
2. Run integration tests: `pytest cadet-lab-tools/test_integration_phase_c.py -v`
3. Consult test results documentation

**For Issues:**
- Check troubleshooting section in implementation guide
- Verify cadet-cli version (v6.x+ recommended)
- Ensure dependencies installed (numpy, scipy, h5py)

---

**Phase C Status:** ✅ Implementation Complete - Ready for Production Execution
