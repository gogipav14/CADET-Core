// =============================================================================
//  CADET
//
//  Copyright © 2008-present: The CADET-Core Authors
//            Please see the AUTHORS.md file.
//
//  All rights reserved. This program and the accompanying materials
//  are made available under the terms of the GNU Public License v3.0 (or, at
//  your option, any later version) which accompanies this distribution, and
//  is available at http://www.gnu.org/licenses/gpl.html
// =============================================================================

#include <catch.hpp>

#define CADET_LOGGING_DISABLE
#include "Logging.hpp"

#include "common/Driver.hpp"
#include "JsonTestModels.hpp"
#include "io/JsonParameterProvider.hpp"

#include <json.hpp>

/**
 * @brief Creates a minimal LRM model JSON configuration with WRITE_SOLVER_STATISTICS enabled
 */
nlohmann::json createMinimalLRMWithSolverStats()
{
	nlohmann::json config;

	// Model section
	config["model"]["NUNITS"] = 3;
	config["model"]["connections"]["NSWITCHES"] = 1;
	config["model"]["connections"]["switch_000"]["SECTION"] = 0;
	config["model"]["connections"]["switch_000"]["CONNECTIONS"] = {0, 1, -1, -1, 1e-5, 1, 2, -1, -1, 1e-5};

	// Unit 0: Inlet
	config["model"]["unit_000"]["UNIT_TYPE"] = "INLET";
	config["model"]["unit_000"]["NCOMP"] = 1;
	config["model"]["unit_000"]["INLET_TYPE"] = "PIECEWISE_CUBIC_POLY";
	config["model"]["unit_000"]["sec_000"]["CONST_COEFF"] = {1.0};
	config["model"]["unit_000"]["sec_000"]["LIN_COEFF"] = {0.0};
	config["model"]["unit_000"]["sec_000"]["QUAD_COEFF"] = {0.0};
	config["model"]["unit_000"]["sec_000"]["CUBE_COEFF"] = {0.0};

	// Unit 1: LRM column
	config["model"]["unit_001"]["UNIT_TYPE"] = "LUMPED_RATE_MODEL_WITHOUT_PORES";
	config["model"]["unit_001"]["NCOMP"] = 1;
	config["model"]["unit_001"]["COL_LENGTH"] = 0.1;
	config["model"]["unit_001"]["COL_POROSITY"] = 0.4;
	config["model"]["unit_001"]["CROSS_SECTION_AREA"] = 1e-4;
	config["model"]["unit_001"]["COL_DISPERSION"] = 1e-7;
	config["model"]["unit_001"]["VELOCITY"] = 1e-3;
	config["model"]["unit_001"]["INIT_C"] = {0.0};
	config["model"]["unit_001"]["INIT_Q"] = {0.0};
	config["model"]["unit_001"]["ADSORPTION_MODEL"] = "LINEAR";
	config["model"]["unit_001"]["NBOUND"] = {1};
	config["model"]["unit_001"]["adsorption"]["IS_KINETIC"] = 1;
	config["model"]["unit_001"]["adsorption"]["LIN_KA"] = {1.0};
	config["model"]["unit_001"]["adsorption"]["LIN_KD"] = {1.0};
	config["model"]["unit_001"]["discretization"]["NCOL"] = 10;
	config["model"]["unit_001"]["discretization"]["USE_ANALYTIC_JACOBIAN"] = 1;

	// Unit 2: Outlet
	config["model"]["unit_002"]["UNIT_TYPE"] = "OUTLET";
	config["model"]["unit_002"]["NCOMP"] = 1;

	// Solver section
	config["model"]["solver"]["GS_TYPE"] = 1;
	config["model"]["solver"]["MAX_KRYLOV"] = 0;
	config["model"]["solver"]["MAX_RESTARTS"] = 10;
	config["model"]["solver"]["SCHUR_SAFETY"] = 1e-8;

	config["solver"]["NTHREADS"] = 1;
	config["solver"]["USER_SOLUTION_TIMES"] = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0};
	config["solver"]["sections"]["NSEC"] = 1;
	config["solver"]["sections"]["SECTION_TIMES"] = {0.0, 5.0};
	config["solver"]["sections"]["SECTION_CONTINUITY"] = std::vector<int>{};
	config["solver"]["time_integrator"]["ABSTOL"] = 1e-8;
	config["solver"]["time_integrator"]["ALGTOL"] = 1e-10;
	config["solver"]["time_integrator"]["RELTOL"] = 1e-6;
	config["solver"]["time_integrator"]["INIT_STEP_SIZE"] = 1e-6;
	config["solver"]["time_integrator"]["MAX_STEPS"] = 10000;

	// Return configuration with WRITE_SOLVER_STATISTICS enabled
	config["return"]["SPLIT_COMPONENTS_DATA"] = 0;
	config["return"]["SPLIT_PORTS_DATA"] = 0;
	config["return"]["WRITE_SOLUTION_TIMES"] = 1;
	config["return"]["WRITE_SOLVER_STATISTICS"] = 1;  // Enable solver statistics output

	config["return"]["unit_000"]["WRITE_SOLUTION_INLET"] = 0;
	config["return"]["unit_000"]["WRITE_SOLUTION_OUTLET"] = 0;

	config["return"]["unit_001"]["WRITE_SOLUTION_INLET"] = 0;
	config["return"]["unit_001"]["WRITE_SOLUTION_OUTLET"] = 1;
	config["return"]["unit_001"]["WRITE_SOLUTION_BULK"] = 0;
	config["return"]["unit_001"]["WRITE_SOLUTION_SOLID"] = 0;

	config["return"]["unit_002"]["WRITE_SOLUTION_INLET"] = 0;
	config["return"]["unit_002"]["WRITE_SOLUTION_OUTLET"] = 0;

	return config;
}

TEST_CASE("Solver statistics are collected and non-negative", "[SolverStatistics],[Simulation],[CI]")
{
	// Create minimal model with solver stats enabled
	nlohmann::json config = createMinimalLRMWithSolverStats();

	// Parse configuration
	cadet::JsonParameterProvider pp(config);

	// Create and configure driver
	cadet::Driver drv;
	drv.configure(pp);

	// Run simulation
	drv.run();

	// Get solver statistics
	cadet::SolverStatistics stats = drv.simulator()->getSolverStatistics();

	// Verify all statistics are non-negative
	REQUIRE(stats.numSteps >= 0);
	REQUIRE(stats.numRhsEvals >= 0);
	REQUIRE(stats.numLinSolSetups >= 0);
	REQUIRE(stats.numErrTestFails >= 0);
	REQUIRE(stats.numNonlinSolvConvFails >= 0);
	REQUIRE(stats.numNonlinSolvIters >= 0);

	// For a successful simulation, we expect at least some steps and RHS evaluations
	REQUIRE(stats.numSteps > 0);
	REQUIRE(stats.numRhsEvals > 0);
}

TEST_CASE("Solver statistics are reasonable for simple simulation", "[SolverStatistics],[Simulation],[CI]")
{
	// Create minimal model with solver stats enabled
	nlohmann::json config = createMinimalLRMWithSolverStats();

	// Parse configuration
	cadet::JsonParameterProvider pp(config);

	// Create and configure driver
	cadet::Driver drv;
	drv.configure(pp);

	// Run simulation
	drv.run();

	// Get solver statistics
	cadet::SolverStatistics stats = drv.simulator()->getSolverStatistics();

	// For a well-behaved simple linear simulation:
	// - Steps should be reasonable (not too many)
	// - Error test failures should be low
	// - Convergence failures should be very low or zero
	REQUIRE(stats.numSteps < 10000);  // Should not need many steps for this simple problem
	REQUIRE(stats.numErrTestFails < stats.numSteps);  // Should not have more failures than steps
	REQUIRE(stats.numNonlinSolvConvFails < 100);  // Very few convergence failures expected
}

TEST_CASE("Solver statistics disabled by default", "[SolverStatistics],[Simulation],[CI]")
{
	// Create minimal model WITHOUT solver stats enabled
	nlohmann::json config = createMinimalLRMWithSolverStats();
	config["return"].erase("WRITE_SOLVER_STATISTICS");  // Remove the flag (defaults to false)

	// Parse configuration
	cadet::JsonParameterProvider pp(config);

	// Create and configure driver
	cadet::Driver drv;
	drv.configure(pp);

	// Run simulation - should still work
	drv.run();

	// Statistics should still be collected internally (just not written to output)
	cadet::SolverStatistics stats = drv.simulator()->getSolverStatistics();
	REQUIRE(stats.numSteps > 0);
}
