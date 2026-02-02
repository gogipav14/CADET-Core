#!/usr/bin/env python3
"""Phase D Track 2a: GMRES Stress Testing Master Runner

Systematically stress-tests GMRES across 4 parameter sweeps:
1. Peclet number (dispersion to advection-dominated)
2. Multi-component (system size scaling)
3. Tolerance (loose to tight convergence)
4. Kinetics (slow to fast binding)

Decision gate: If lin_iters_per_step > 20 OR degradation > 2× → proceed to Track 2b
Otherwise: GMRES is excellent, no FFT preconditioner needed
"""

import argparse
from pathlib import Path
from datetime import datetime
import sys

from cadet_lab.benchmarks.gmres_stress_suite import (
    run_peclet_sweep,
    run_multicomponent_sweep,
    run_tolerance_sweep,
    run_kinetics_sweep,
    GMRESStressSuite,
    print_stress_summary,
)


def main():
    parser = argparse.ArgumentParser(
        description="Phase D Track 2a: GMRES Stress Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all sweeps
  python scripts/run_track2a_gmres_stress.py --cadet-cli /path/to/cadet-cli

  # Run specific sweep
  python scripts/run_track2a_gmres_stress.py --cadet-cli /path/to/cadet-cli --sweep peclet

  # Use different NCOL
  python scripts/run_track2a_gmres_stress.py --cadet-cli /path/to/cadet-cli --ncol 128
        """
    )

    parser.add_argument(
        "--cadet-cli",
        type=Path,
        required=True,
        help="Path to cadet-cli executable"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/track2a_gmres_stress"),
        help="Output directory for results (default: artifacts/track2a_gmres_stress)"
    )

    parser.add_argument(
        "--sweep",
        choices=["all", "peclet", "multicomp", "tolerance", "kinetics"],
        default="all",
        help="Which sweep to run (default: all)"
    )

    parser.add_argument(
        "--ncol",
        type=int,
        default=64,
        help="Number of column discretization elements (default: 64)"
    )

    args = parser.parse_args()

    # Validate cadet-cli
    if not args.cadet_cli.exists():
        print(f"ERROR: cadet-cli not found at {args.cadet_cli}")
        sys.exit(1)

    # Print banner
    print("=" * 80)
    print("PHASE D TRACK 2a: GMRES STRESS TESTING")
    print("=" * 80)
    print(f"Date: {datetime.now().isoformat()}")
    print(f"CADET CLI: {args.cadet_cli}")
    print(f"Output dir: {args.output_dir}")
    print(f"Sweep: {args.sweep}")
    print(f"NCOL: {args.ncol}")
    print("=" * 80)
    print()

    all_results = []

    # Run sweeps
    if args.sweep in ["all", "peclet"]:
        print("\n" + "#" * 80)
        print("# Sweep 1: Peclet Number (Dispersion → Advection)")
        print("#" * 80)
        peclet_results = run_peclet_sweep(
            cadet_cli_path=args.cadet_cli,
            output_dir=args.output_dir / "peclet_sweep",
            ncol=args.ncol,
        )
        all_results.extend(peclet_results)

    if args.sweep in ["all", "multicomp"]:
        print("\n" + "#" * 80)
        print("# Sweep 2: Multi-Component (System Size)")
        print("#" * 80)
        multicomp_results = run_multicomponent_sweep(
            cadet_cli_path=args.cadet_cli,
            output_dir=args.output_dir / "multicomp_sweep",
            ncol=args.ncol,
        )
        all_results.extend(multicomp_results)

    if args.sweep in ["all", "tolerance"]:
        print("\n" + "#" * 80)
        print("# Sweep 3: Tolerance (Loose → Tight)")
        print("#" * 80)
        tolerance_results = run_tolerance_sweep(
            cadet_cli_path=args.cadet_cli,
            output_dir=args.output_dir / "tolerance_sweep",
            ncol=args.ncol,
        )
        all_results.extend(tolerance_results)

    if args.sweep in ["all", "kinetics"]:
        print("\n" + "#" * 80)
        print("# Sweep 4: Binding Kinetics (Slow → Fast)")
        print("#" * 80)
        kinetics_results = run_kinetics_sweep(
            cadet_cli_path=args.cadet_cli,
            output_dir=args.output_dir / "kinetics_sweep",
            ncol=args.ncol,
        )
        all_results.extend(kinetics_results)

    # Create suite and save results
    suite = GMRESStressSuite(
        suite_name="Phase D Track 2a: GMRES Stress Testing",
        results=all_results,
        timestamp=datetime.now().isoformat(),
        metadata={
            "ncol": args.ncol,
            "sweep": args.sweep,
            "num_tests": len(all_results),
        }
    )

    # Save JSON
    json_path = args.output_dir / "gmres_stress_results.json"
    suite.save(json_path)
    print(f"\n✅ Results saved to: {json_path}")

    # Print summary
    print_stress_summary(suite)

    # Decision gate analysis
    print("\n" + "=" * 80)
    print("TRACK 2a DECISION GATE")
    print("=" * 80)

    bottlenecks = suite.find_bottlenecks(threshold=20.0)

    # Check for scaling degradation
    degradations = []
    for param in ["peclet", "n_comp", "abstol", "ka"]:
        analysis = suite.analyze_scaling(param)
        if "error" not in analysis and analysis.get("is_degrading", False):
            degradations.append((param, analysis["degradation_ratio"]))

    # Make decision
    if bottlenecks or degradations:
        print("\n⚠️  BOTTLENECK DETECTED - Proceed to Track 2b\n")

        if bottlenecks:
            print(f"Reason: {len(bottlenecks)} test(s) exceeded 20 iters/step threshold")
            for b in bottlenecks:
                print(f"  - {b.test_name}: {b.lin_iters_per_step:.2f} iters/step")

        if degradations:
            print(f"\nReason: Scaling degradation detected (>2× growth)")
            for param, ratio in degradations:
                print(f"  - {param}: {ratio:.2f}× degradation")

        print("\n➡️  Next: Implement FFT preconditioner prototype (Track 2b)")
        sys.exit(1)  # Exit with code 1 to signal bottleneck found

    else:
        print("\n✅ NO BOTTLENECK - GMRES is excellent!\n")
        print("All tests:")
        print("  - lin_iters_per_step < 20")
        print("  - No scaling degradation (< 2× growth)")
        print("\nConclusion: CADET's Schur complement preconditioner is already optimal.")
        print("No FFT preconditioner needed.")
        print("\n➡️  Track 2: COMPLETE (skip Track 2b)")
        print("➡️  Phase D: COMPLETE (Track 1 + Track 2a sufficient)")
        sys.exit(0)  # Exit with code 0 to signal success


if __name__ == "__main__":
    main()
