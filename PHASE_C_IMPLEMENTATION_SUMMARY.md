# Phase C Implementation Summary

**Date:** 2026-01-31
**Status:** ✅ Complete
**Branch:** claude/review-moljax-papers-VFmeZ

## Overview

Successfully implemented Phase C: Full-State Accuracy Gating & Tolerance Policy for the CADET stress suite. This adds comprehensive validation infrastructure for work-precision analysis, spatial convergence checking, and adaptive step-size policies.

## Implementation Details

### Phase C.1: Telemetry Foundation ✅

**Files Modified:**
- `cadet-lab-tools/cadet_lab/telemetry/read_hdf5.py`
  - Extended `SolutionData` dataclass with 4 new fields:
    - `bulk_profiles: Dict[str, np.ndarray]`
    - `particle_profiles: Dict[tuple, np.ndarray]` (keyed by `(unit_id, partype)`)
    - `solid_profiles: Dict[tuple, np.ndarray]`
    - `coordinates: Dict[str, dict]`
  - Added `read_full_state` parameter to `read_solution()`
  - Implemented 4 new reading functions:
    - `_read_bulk_profiles()` - reads SOLUTION_BULK with existence assertions
    - `_read_particle_profiles()` - reads SOLUTION_PARTICLE_PARTYPE_XXX
    - `_read_solid_profiles()` - reads SOLUTION_SOLID_PARTYPE_XXX
    - `_read_coordinates()` - reads AXIAL_COORDINATES and PARTICLE_COORDINATES_XXX
  - All readers include clear error messages when datasets missing

- `cadet-lab-tools/cadet_lab/config_gen/minimal_grm.py`
  - Added `enable_full_state_output: bool = False` parameter
  - Updated return configuration to set flags based on parameter:
    - `WRITE_SOLUTION_BULK`
    - `WRITE_SOLUTION_PARTICLE`
    - `WRITE_SOLUTION_SOLID`
    - `WRITE_COORDINATES`

**Key Design:** Full-state output is optional, controlled by single parameter maintaining single source of truth.

---

### Phase C.2: Full-State Metrics ✅

**Files Created:**
- `cadet-lab-tools/cadet_lab/telemetry/full_state_metrics.py` (350 lines)
  - `FullStateMetrics` dataclass with 11 fields
  - `compute_scaled_rms()` - SUNDIALS-compliant scaled RMS formula
  - `compute_linf()` - L-infinity (max absolute) error
  - `compare_full_state()` - aggregates metrics across bulk/particle/solid phases

- `cadet-lab-tools/cadet_lab/telemetry/tests/test_full_state_metrics.py`
  - 18 comprehensive unit tests
  - Tests zero error, constant offsets, multi-dimensional arrays
  - Tests phase aggregation logic
  - **All tests pass ✅**

**Key Formulas:**
- Scaled RMS: `sqrt(mean((y - y_ref)^2 / (atol + rtol * max(|y|, |y_ref|))^2))`
- Linf: `max|y - y_ref|`
- Global metrics: DOF-weighted mean for RMS, max for Linf

---

### Phase C.3: Reference Protocol ✅

**Files Created:**
- `cadet-lab-tools/cadet_lab/validation/reference_protocol.py` (230 lines)
  - `create_reference_config()` - supports TWO modes:
    - **time mode**: Tighten tolerances only (ABSTOL /= factor, RELTOL /= factor)
    - **space mode**: Refine spatial resolution only (NELEM *= factor, PAR_NELEM *= factor)
  - `run_reference()` - generates and runs reference with optional caching
  - Both modes enable full-state output flags

**Key Design:** Separate time/space modes (NOT combined) per user correction #1.

---

### Phase C.4: Tolerance Sweep ✅

**Files Created:**
- `cadet-lab-tools/cadet_lab/validation/tolerance_sweep.py` (280 lines)
  - `TolerancePoint` dataclass - single sweep point with accuracy/cost metrics
  - `WorkPrecisionResult` dataclass - full sweep result with save/load
  - `run_tolerance_sweep()` - cartesian product sweep (default 4×4 = 16 points)
  - Default grids:
    - abstol: [1e-9, 3e-9, 1e-8, 3e-8]
    - reltol: [1e-6, 3e-6, 1e-5, 3e-5]

**Artifact Format:** `work_precision_full_state.json`
```json
{
  "case_name": "stiff_binding",
  "reference": {"tolerances": {...}, "resolution": {...}},
  "sweep_points": [
    {"abstol": 1e-9, "reltol": 1e-6, "num_steps": 365,
     "linf_error": 2.3e-5, "scaled_rms_error": 0.8, "success": true},
    ...
  ]
}
```

---

### Phase C.5: Step-Size Advisor ✅

**Files Created:**
- `cadet-lab-tools/cadet_lab/validation/step_advisor.py` (120 lines)
  - `detect_excessive_err_fails()` - **direct threshold check on num_err_test_fails**
  - `run_with_step_advisor()` - adaptive retry with reduced INIT_STEP_SIZE
  - Optionally sets MAX_STEP_SIZE for discontinuous cases

**Key Design:** Uses ONLY `num_err_test_fails >= threshold` (user correction #4), NO heuristics.

---

### Phase C.6: Spatial Convergence ✅

**Files Created:**
- `cadet-lab-tools/cadet_lab/validation/spatial_convergence.py` (380 lines)
  - `SpatialConvergenceResult` dataclass
  - `run_spatial_convergence_check()` - baseline vs refined comparison
  - `_interpolate_to_baseline_grid()` - **coordinate-based interpolation**
  - `_interpolate_axial()` - 1D axial interpolation using AXIAL_COORDINATES
  - `_interpolate_2d()` - 2D axial×radial interpolation using PARTICLE_COORDINATES_XXX

**Key Design:** Uses scipy.interpolate.interp1d with coordinate mapping (user correction #2), NOT index-based.

**Artifact Format:** `spatial_convergence.json`
```json
{
  "case_name": "sharp_front",
  "baseline_resolution": {"nelem_col": 8, "nelem_par": 1},
  "refined_resolution": {"nelem_col": 16, "nelem_par": 2},
  "linf_delta": 1.2e-4,
  "scaled_rms_delta": 5.3e-5,
  "convergence_achieved": true,
  "threshold": 1e-3
}
```

---

### Phase C.7: Integration ✅

**Files Modified:**
- `cadet-lab-tools/cadet_lab/stress_suite/runner.py`
  - Added `full_state_mode: bool = False` parameter to `run_stress_suite()`
  - Extended `StressSuiteResult` with `full_state_metrics` field
  - Passes `enable_full_state_output=True` to case generators when in full_state_mode
  - Collects full-state presence info (has_bulk, has_particle, has_solid, has_coordinates)

- `cadet-lab-tools/cadet_lab/validation/__init__.py`
  - Exports all new functions and dataclasses

---

## File Summary

| Category | File | Lines | Status |
|----------|------|-------|--------|
| **Telemetry** | `read_hdf5.py` | +150 | Modified |
| | `full_state_metrics.py` | 350 | New |
| | `tests/test_full_state_metrics.py` | 280 | New |
| **Config Gen** | `minimal_grm.py` | +20 | Modified |
| **Validation** | `reference_protocol.py` | 230 | New |
| | `tolerance_sweep.py` | 280 | New |
| | `step_advisor.py` | 120 | New |
| | `spatial_convergence.py` | 380 | New |
| | `__init__.py` | 30 | New |
| **Stress Suite** | `runner.py` | +30 | Modified |

**Total:** ~1,870 lines of new/modified code

---

## Verification

### Unit Tests
```bash
cd cadet-lab-tools
python3 -m pytest cadet_lab/telemetry/tests/test_full_state_metrics.py -v
# Result: 18 passed in 0.19s ✅
```

### Import Check
```bash
python3 -c "
from cadet_lab.telemetry.read_hdf5 import read_solution, SolutionData
from cadet_lab.telemetry.full_state_metrics import compare_full_state
from cadet_lab.validation import (
    create_reference_config,
    run_reference,
    run_tolerance_sweep,
    run_with_step_advisor,
    run_spatial_convergence_check,
)
from cadet_lab.stress_suite.runner import run_stress_suite
print('All imports successful!')
"
# Result: All imports successful! ✅
```

---

## Next Steps

### Integration Testing (Requires CADET CLI)

1. **Test full-state reading:**
   ```python
   from cadet_lab.config_gen.minimal_grm import create_minimal_grm_config
   from cadet_lab.harness.run_case import run_case
   from cadet_lab.telemetry.read_hdf5 import read_solution

   # Generate config with full-state output
   config = create_minimal_grm_config(
       output_path="test_fullstate.h5",
       enable_full_state_output=True,
   )

   # Run and read
   result = run_case(config, cadet_cli_path="path/to/cadet-cli")
   data = read_solution(result.output_file, read_full_state=True)

   # Verify
   assert len(data.bulk_profiles) > 0
   assert len(data.particle_profiles) > 0
   assert len(data.solid_profiles) > 0
   assert len(data.coordinates["axial"]) > 0
   ```

2. **Test reference protocol:**
   ```python
   from cadet_lab.validation import run_reference
   from cadet_lab.stress_suite.cases import case_first_step_fail

   # Generate time-mode reference
   ref_output = run_reference(
       case_generator=case_first_step_fail,
       case_kwargs={"_case_name": "first_step_fail"},
       cadet_cli_path="path/to/cadet-cli",
       output_dir="./test_ref",
       mode="time",
       tolerance_factor=10.0,
   )

   # Verify tolerances tightened, resolution unchanged
   ```

3. **Test tolerance sweep:**
   ```python
   from cadet_lab.validation import run_tolerance_sweep

   wp_result = run_tolerance_sweep(
       case_generator=case_first_step_fail,
       case_kwargs={"_case_name": "first_step_fail"},
       reference_output=ref_output,
       cadet_cli_path="path/to/cadet-cli",
       output_dir="./test_sweep",
       abstol_grid=[1e-8, 1e-7],  # Small grid for testing
       reltol_grid=[1e-5, 1e-4],
   )

   wp_result.save("work_precision_test.json")
   assert len(wp_result.sweep_points) == 4
   ```

4. **Test step advisor:**
   ```python
   from cadet_lab.validation import run_with_step_advisor

   result, num_retries = run_with_step_advisor(
       input_file="first_step_fail.h5",
       cadet_cli_path="path/to/cadet-cli",
       output_dir="./test_advisor",
       err_fail_threshold=5,
   )

   # Should have retried if initial had >=5 err_test_fails
   ```

5. **Test spatial convergence:**
   ```python
   from cadet_lab.validation import run_spatial_convergence_check

   sc_result = run_spatial_convergence_check(
       case_generator=case_first_step_fail,
       case_kwargs={"_case_name": "first_step_fail"},
       cadet_cli_path="path/to/cadet-cli",
       output_dir="./test_spatial",
   )

   sc_result.save("spatial_convergence_test.json")
   assert sc_result.convergence_achieved
   ```

6. **Test stress suite with full-state:**
   ```bash
   cd cadet-lab-tools
   python3 -c "
   from cadet_lab.stress_suite.runner import run_stress_suite

   results = run_stress_suite(
       cadet_cli_path='path/to/cadet-cli',
       full_state_mode=True,
       output_dir='./stress_fullstate',
   )

   results.save('stress_suite_results_full_state.json')
   print(f'Full-state metrics available: {results.full_state_metrics is not None}')
   "
   ```

---

## Design Decisions Implemented

1. ✅ **Full-state output mode:** Optional parameter (not separate function)
2. ✅ **Particle type handling:** Dictionary keys as `(unit_id, partype)` tuples
3. ✅ **Reference protocol modes:** TWO separate modes (time-only OR space-only), NOT combined
4. ✅ **Spatial convergence:** Coordinate-based interpolation using AXIAL_COORDINATES and PARTICLE_COORDINATES_XXX
5. ✅ **Output verification:** Assert dataset existence, fail loudly if missing
6. ✅ **Step advisor trigger:** Direct threshold on num_err_test_fails, NO heuristics
7. ✅ **Tolerance grid:** Fixed 4×4 default (16 points, predictable cost)
8. ✅ **Reference caching:** Optional cache_dir to avoid expensive reruns

---

## Known Limitations

1. **Requires CADET CLI:** All validation functions require access to cadet-cli for execution
2. **Spatial interpolation:** Assumes structured grids; may need extension for unstructured meshes
3. **Component handling:** Current implementation handles multi-component arrays but may need refinement for specific edge cases
4. **Performance:** Full-state data can be large; consider compression for long-term storage

---

## Achievements

- ✅ All 7 phases complete
- ✅ 18/18 unit tests passing
- ✅ All modules importable
- ✅ No CADET-Core solver modifications (infrastructure only)
- ✅ Backward compatible (full-state mode is opt-in)
- ✅ Clear error messages with actionable diagnostics
- ✅ Comprehensive documentation in code

**Phase C is production-ready pending integration testing with CADET CLI.**
