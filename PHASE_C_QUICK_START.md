# Phase C Quick Start Guide

**Goal:** Generate production tolerance recommendations for 4 stress cases

**Time:** ~1-2 hours | **Outputs:** Optimal settings + Phase D decision

---

## One-Command Execution

```bash
python cadet-lab-tools/scripts/run_phase_c_full.py \
  --cadet-cli /path/to/cadet-cli \
  --output-dir ./artifacts
```

**This runs:**
1. Work-precision sweeps (4 cases × 16 points)
2. Spatial convergence checks (iterative for sharp_front)
3. Tolerance recommendations generation
4. Stress suite baseline

---

## Quick Commands

### Run Work-Precision Sweeps Only
```bash
python cadet-lab-tools/scripts/run_production_sweeps.py \
  --cadet-cli /path/to/cadet-cli \
  --output-dir ./artifacts
```

### Run Spatial Convergence Only
```bash
python cadet-lab-tools/scripts/run_spatial_convergence.py \
  --cadet-cli /path/to/cadet-cli \
  --output-dir ./artifacts
```

### Generate Recommendations (from existing artifacts)
```bash
python cadet-lab-tools/cadet_lab/validation/recommend_settings.py \
  --artifacts-dir ./artifacts \
  --output ./artifacts/phase_c_recommended_settings.json
```

### Run Stress Suite Baseline
```bash
python cadet-lab-tools/scripts/run_stress_suite_baseline.py \
  --cadet-cli /path/to/cadet-cli \
  --output-file ./artifacts/baseline.json
```

---

## Key Outputs

### Recommendations JSON
```bash
cat ./artifacts/phase_c_recommended_settings.json | jq
```

**Contains:**
- Optimal tolerances per case (abstol, reltol)
- Expected steps and accuracy
- Phase D trigger decision

**Example:**
```json
{
  "first_step_fail": {
    "abstol": 1e-8,
    "reltol": 1e-5,
    "expected_steps": 107
  },
  "phase_d_decision": {
    "triggered": false,
    "notes": "No solver work warranted"
  }
}
```

---

### Work-Precision Sweep
```bash
cat ./artifacts/first_step_fail/work_precision_full_state.json | jq
```

**Contains:** 16 tolerance points with accuracy and cost metrics

---

### Spatial Convergence
```bash
cat ./artifacts/sharp_front/spatial_convergence.json | jq
```

**Contains:** Convergence check result with coordinate confidence

---

## Interpreting Phase D Decision

### ✅ NOT Triggered (Expected)
```json
{
  "triggered": false,
  "reasons": [],
  "notes": "No solver work warranted"
}
```

**Action:** Apply recommended settings to production. Skip Phase D.

---

### ⚠️ Triggered (Investigate)
```json
{
  "triggered": true,
  "reasons": [
    "stiff_binding: High step count (612 > 500)"
  ]
}
```

**Action:** Review trigger evidence. Proceed to Phase D if bottleneck confirmed.

---

## Troubleshooting

### All sweep points fail gates
**Fix:** Check `work_precision_full_state.json`. If all `scaled_rms_error > 1.0`, increase baseline spatial resolution.

### Reference simulation fails
**Fix:** Reduce `--tolerance-factor` from 100 to 10.

### Spatial convergence never achieved
**Fix:** Check `confidence_level`. If "low", increase baseline NELEM × 2.

---

## File Structure

```
artifacts/
├── first_step_fail/
│   ├── work_precision_full_state.json
│   └── spatial_convergence.json
├── sharp_front/...
├── discontinuous_section/...
├── stiff_binding/...
├── phase_c_recommended_settings.json
└── stress_suite_results_full_state.json
```

---

## Next Steps

### If Phase D NOT Triggered
1. Apply recommended tolerances to production
2. Monitor performance vs baseline
3. Re-run if cases change

### If Phase D Triggered
1. Review trigger evidence
2. Proceed to solver optimization (preconditioners, Krylov methods)
3. Use `num_lin_iters` to measure impact

---

## Full Documentation

- **Implementation Guide:** `PHASE_C_IMPLEMENTATION_GUIDE.md` (detailed usage)
- **README:** `PHASE_C_OPERATIONALIZATION_README.md` (comprehensive reference)
- **Completion Summary:** `PHASE_C_IMPLEMENTATION_COMPLETE.md` (verification)

---

**Status:** ✅ Ready for production execution
