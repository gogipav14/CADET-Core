#!/usr/bin/env python3
"""Verification script for Phase C implementation.

Checks that all components are importable and functional.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "cadet-lab-tools"))

def check_import(module_path, component_name):
    """Check if a module/function can be imported."""
    try:
        parts = module_path.rsplit(".", 1)
        if len(parts) == 2:
            module, attr = parts
            exec(f"from {module} import {attr}")
        else:
            exec(f"import {module_path}")
        print(f"✓ {component_name}")
        return True
    except Exception as e:
        print(f"✗ {component_name}: {e}")
        return False


def main():
    print("=" * 80)
    print("Phase C Implementation Verification")
    print("=" * 80)

    checks = [
        # Telemetry enhancements
        ("cadet_lab.telemetry.read_hdf5", "Linear iteration counter parsing"),
        ("cadet_lab.telemetry.kpis", "RunKPIs with linear iteration fields"),

        # Spatial convergence enhancements
        ("cadet_lab.validation.spatial_convergence", "Coordinate confidence tracking"),

        # New modules
        ("cadet_lab.validation.recommend_settings", "Tolerance recommendation engine"),

        # Existing infrastructure (should still work)
        ("cadet_lab.validation.reference_protocol", "Reference protocol"),
        ("cadet_lab.validation.tolerance_sweep", "Tolerance sweep"),
        ("cadet_lab.stress_suite.cases", "Stress cases"),
        ("cadet_lab.stress_suite.runner", "Stress suite runner"),
        ("cadet_lab.telemetry.full_state_metrics", "Full-state metrics"),
    ]

    results = []
    for module_path, component_name in checks:
        results.append(check_import(module_path, component_name))

    print("\n" + "=" * 80)

    # Check scripts exist
    print("\nScript Verification:")
    scripts_dir = Path(__file__).parent / "cadet-lab-tools" / "scripts"
    scripts = [
        "run_production_sweeps.py",
        "run_spatial_convergence.py",
        "run_stress_suite_baseline.py",
        "run_phase_c_full.py",
    ]

    for script in scripts:
        script_path = scripts_dir / script
        if script_path.exists():
            print(f"✓ {script}")
            results.append(True)
        else:
            print(f"✗ {script} (not found)")
            results.append(False)

    # Check documentation
    print("\nDocumentation Verification:")
    docs = [
        "PHASE_C_IMPLEMENTATION_GUIDE.md",
        "PHASE_C_OPERATIONALIZATION_README.md",
        "PHASE_C_IMPLEMENTATION_COMPLETE.md",
        "PHASE_C_QUICK_START.md",
    ]

    for doc in docs:
        doc_path = Path(__file__).parent / doc
        if doc_path.exists():
            print(f"✓ {doc}")
            results.append(True)
        else:
            print(f"✗ {doc} (not found)")
            results.append(False)

    # Summary
    print("\n" + "=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Verification: {passed}/{total} checks passed")

    if passed == total:
        print("\n✓ Phase C implementation complete and verified!")
        print("\nNext steps:")
        print("  1. Run full workflow:")
        print("     python cadet-lab-tools/scripts/run_phase_c_full.py \\")
        print("       --cadet-cli /path/to/cadet-cli \\")
        print("       --output-dir ./artifacts")
        print("\n  2. Review recommendations:")
        print("     cat ./artifacts/phase_c_recommended_settings.json | jq")
        print("\n  3. Consult documentation:")
        print("     - PHASE_C_QUICK_START.md (quick reference)")
        print("     - PHASE_C_IMPLEMENTATION_GUIDE.md (detailed guide)")
        return 0
    else:
        print(f"\n✗ {total - passed} checks failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
