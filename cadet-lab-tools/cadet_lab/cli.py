"""CLI entry point for cadet-lab tools.

Registered in pyproject.toml as: cadet-lab = "cadet_lab.cli:main"

Usage:
    cadet-lab nilt solve <h5_config> [-o output.h5] [--format h5|json]
    cadet-lab nilt compare <h5_config> [--cadet-cli PATH]
    cadet-lab nilt validate <h5_config>
    cadet-lab nilt classify <h5_config>
    cadet-lab nilt list
"""

import argparse
import sys
from pathlib import Path


def _cmd_nilt_solve(args):
    """Solve using NILT and write output."""
    from .nilt.solver import NiltSolver
    from .nilt.output import write_cadet_h5, write_json

    solver = NiltSolver(
        t_end=args.t_end or 0.0,  # Will be overridden by HDF5 end_time
        N_max=args.n_max,
    )
    solution = solver.solve_from_h5(args.h5_config)

    # Print summary
    cls = solution.classification
    print(f"Problem type: {cls.problem_type}")
    print(f"Transfer function: {cls.transfer_function_name}")
    print(f"Production ready: {cls.production_ready}")
    if cls.warnings:
        for w in cls.warnings:
            print(f"  Warning: {w}")
    print(f"Converged: {solution.convergence.passed}")
    print(f"N: {solution.params.N}")
    if solution.convergence.epsilon_im is not None:
        print(f"eps_im: {solution.convergence.epsilon_im:.2e}")
    if solution.convergence.final_delta is not None:
        print(f"E_N: {solution.convergence.final_delta:.2e}")
    print(f"Wall time: {solution.wall_time_us:.1f} us")
    print(f"Time points: {len(solution.t)}")

    # Write output
    if args.output:
        output_path = Path(args.output)
    else:
        stem = Path(args.h5_config).stem
        ext = ".json" if args.format == "json" else ".h5"
        output_path = Path(f"{stem}_nilt{ext}")

    if args.format == "json":
        write_json(solution, output_path)
    else:
        write_cadet_h5(solution, output_path)

    print(f"Output written to: {output_path}")


def _cmd_nilt_compare(args):
    """Compare NILT and CADET solutions."""
    from .nilt.solver import NiltSolver
    from .nilt.extract_params import extract_nilt_params
    from .nilt.compare_to_cadet import compare_nilt_to_cadet_output
    from .harness.run_case import run_case

    # Solve with NILT
    solver = NiltSolver(t_end=0.0)
    solution = solver.solve_from_h5(args.h5_config)

    print(f"NILT solve: N={solution.params.N}, "
          f"eps_im={solution.metadata.get('eps_im', 'N/A'):.2e}, "
          f"wall_time={solution.wall_time_us:.1f} us")

    # Run CADET
    cadet_cli = args.cadet_cli
    if cadet_cli is None:
        print("Error: --cadet-cli is required for comparison")
        sys.exit(1)

    print(f"Running CADET with: {cadet_cli}")
    run_result = run_case(args.h5_config, cadet_cli)

    if not run_result.success:
        print(f"CADET failed: {run_result.failure_reason}")
        sys.exit(1)

    print(f"CADET solve: wall_time={run_result.wall_time:.3f} s")

    # Compare
    comparison = compare_nilt_to_cadet_output(
        solution.t, solution.y, run_result.output_file,
    )

    print(f"\nComparison metrics:")
    print(f"  RMSE:              {comparison.rmse:.2e}")
    print(f"  L2 norm:           {comparison.l2_norm:.2e}")
    print(f"  L-inf norm:        {comparison.linf_norm:.2e}")
    print(f"  Relative L2 error: {comparison.relative_l2_error:.2e}")

    # Speedup
    if run_result.wall_time > 0:
        nilt_us = solution.metadata.get(
            "timing_median_us", solution.wall_time_us
        )
        speedup = (run_result.wall_time * 1e6) / nilt_us
        print(f"\nSpeedup (per-solve): {speedup:.0f}x")


def _cmd_nilt_validate(args):
    """Run convergence validation tests."""
    from .nilt.extract_params import extract_nilt_params
    from .nilt.classify import classify_problem
    from .nilt.solver import _build_transfer_function
    from .nilt.convergence import epsilon_im_test, n_doubling_test

    params = extract_nilt_params(args.h5_config)
    classification = classify_problem(params)

    print(f"Problem type: {classification.problem_type}")
    print(f"Transfer function: {classification.transfer_function_name}")

    if classification.problem_type == "unsupported":
        print("Cannot validate: unsupported problem type")
        sys.exit(1)

    F = _build_transfer_function(params, classification)
    t_end = params["end_time"]

    # Epsilon-Im test
    print(f"\n--- Epsilon-Im Test ---")
    eim_result = epsilon_im_test(F, t_end=t_end, threshold=1e-2)
    print(f"  Passed: {eim_result.passed}")
    if eim_result.epsilon_im is not None:
        print(f"  eps_im: {eim_result.epsilon_im:.2e}")
    print(f"  {eim_result.message}")

    # N-doubling test
    print(f"\n--- N-Doubling Test ---")
    nd_result = n_doubling_test(F, t_end=t_end, threshold=1e-6)
    print(f"  Passed: {nd_result.passed}")
    if nd_result.delta_sequence:
        for i, (n, d) in enumerate(
            zip(nd_result.n_sequence or [], nd_result.delta_sequence)
        ):
            print(f"  N={n}: E_N={d:.2e}")
    print(f"  {nd_result.message}")


def _cmd_nilt_classify(args):
    """Classify a CADET config for NILT applicability."""
    from .nilt.extract_params import extract_nilt_params
    from .nilt.classify import classify_problem

    params = extract_nilt_params(args.h5_config)
    classification = classify_problem(params)

    print(f"Problem type:        {classification.problem_type}")
    print(f"Transfer function:   {classification.transfer_function_name}")
    print(f"Production ready:    {classification.production_ready}")
    if classification.warnings:
        print(f"Warnings:")
        for w in classification.warnings:
            print(f"  - {w}")

    print(f"\nExtracted parameters:")
    for key in ("velocity", "dispersion", "length", "col_porosity",
                "par_porosity", "par_radius", "film_diffusion",
                "pore_diffusion", "n_comp", "end_time"):
        print(f"  {key}: {params.get(key)}")
    print(f"  binding_model: {params.get('binding_model')}")
    bp = params.get("binding_params", {})
    if bp:
        for k, v in bp.items():
            print(f"  binding.{k}: {v}")


def _cmd_nilt_list(args):
    """List available transfer functions."""
    from .nilt.benchmarks import get_benchmark_functions

    print("Available NILT transfer functions:\n")

    # Built-in transfer functions
    functions = [
        ("advection_dispersion_transfer",
         "Advection-dispersion (Danckwerts BCs)",
         "transport_only", True),
        ("langmuir_column_transfer",
         "Linearized Langmuir column (retardation + kinetics)",
         "transport_binding_linear", False),
        ("grm_langmuir_transfer",
         "Full GRM with kinetic Langmuir binding",
         "grm_langmuir", False),
        ("grm_sma_transfer",
         "GRM with linearized SMA binding",
         "grm_sma", False),
        ("grm_moment_transfer",
         "GRM moment-based approximation (no binding)",
         "grm_moment", False),
    ]

    for name, desc, ptype, prod_ready in functions:
        status = "production" if prod_ready else "experimental"
        print(f"  {name}")
        print(f"    {desc}")
        print(f"    Type: {ptype}, Status: {status}")
        print()

    # Pre-configured benchmarks
    print("Pre-configured benchmarks:\n")
    for name, F, t_range, has_analytical, alpha_c in get_benchmark_functions():
        print(f"  {name}")
        print(f"    t_range: [{t_range[0]}, {t_range[1]}], alpha_c: {alpha_c}")
        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="cadet-lab",
        description="CADET Lab Tools — telemetry and NILT solver",
    )
    subparsers = parser.add_subparsers(dest="command", help="Top-level commands")

    # nilt command group
    nilt_parser = subparsers.add_parser("nilt", help="NILT solver commands")
    nilt_sub = nilt_parser.add_subparsers(dest="nilt_command", help="NILT subcommands")

    # nilt solve
    solve_parser = nilt_sub.add_parser("solve", help="Solve using NILT")
    solve_parser.add_argument("h5_config", help="CADET HDF5 config file")
    solve_parser.add_argument("-o", "--output", help="Output file path")
    solve_parser.add_argument(
        "--format", choices=["h5", "json"], default="h5",
        help="Output format (default: h5)",
    )
    solve_parser.add_argument(
        "--t-end", type=float, default=None,
        help="Override end time from config",
    )
    solve_parser.add_argument(
        "--n-max", type=int, default=32768,
        help="Maximum FFT size (default: 32768)",
    )
    solve_parser.set_defaults(func=_cmd_nilt_solve)

    # nilt compare
    compare_parser = nilt_sub.add_parser("compare", help="Compare NILT vs CADET")
    compare_parser.add_argument("h5_config", help="CADET HDF5 config file")
    compare_parser.add_argument(
        "--cadet-cli", help="Path to cadet-cli executable",
    )
    compare_parser.set_defaults(func=_cmd_nilt_compare)

    # nilt validate
    validate_parser = nilt_sub.add_parser("validate", help="Run convergence tests")
    validate_parser.add_argument("h5_config", help="CADET HDF5 config file")
    validate_parser.set_defaults(func=_cmd_nilt_validate)

    # nilt classify
    classify_parser = nilt_sub.add_parser("classify", help="Classify problem type")
    classify_parser.add_argument("h5_config", help="CADET HDF5 config file")
    classify_parser.set_defaults(func=_cmd_nilt_classify)

    # nilt list
    list_parser = nilt_sub.add_parser("list", help="List transfer functions")
    list_parser.set_defaults(func=_cmd_nilt_list)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "nilt" and getattr(args, "nilt_command", None) is None:
        nilt_parser.print_help()
        sys.exit(1)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
