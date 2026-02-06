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

/**
 * @file
 * Unit test for DanckwertsSpectralPreconditioner
 */

#include <iostream>
#include <cmath>
#include <vector>
#include <algorithm>

#include "linalg/DanckwertsSpectralPreconditioner.hpp"

using namespace cadet::linalg;

namespace
{
	const double PI = 3.14159265358979323846;
	const double TOLERANCE = 1e-6;

	bool approxEqual(double a, double b, double tol = TOLERANCE)
	{
		return std::abs(a - b) < tol;
	}

	bool testTranscendentalRoots()
	{
		std::cout << "\n=== Test 1: Transcendental Equation Roots ===" << std::endl;

		// Test case from derivation document
		const std::vector<double> peValues = {0.1, 1.0, 10.0, 100.0};

		// Expected β₁ values from derivation document (approximate)
		const std::vector<double> expectedBeta1 = {3.094, 2.664, 1.644, 1.223};

		DanckwertsSpectralPreconditioner precond;

		bool allPassed = true;
		for (size_t i = 0; i < peValues.size(); ++i)
		{
			const double Pe = peValues[i];
			const double L = 1.0;
			const double D = 1.0;
			const double v = Pe * D / L;

			// Initialize with 4 modes
			precond.initialize(64, L, v, D, 4);

			// Check first eigenvalue β₁
			const double beta1 = precond._betaValues[0];
			const double expected = expectedBeta1[i];
			const double error = std::abs(beta1 - expected) / expected;

			std::cout << "Pe = " << Pe << ": β₁ = " << beta1
			          << " (expected ≈ " << expected << ", error = "
			          << (error * 100.0) << "%)" << std::endl;

			// Allow 5% error due to approximations in expected values
			if (error > 0.05)
			{
				std::cerr << "ERROR: β₁ value deviates too much from expected" << std::endl;
				allPassed = false;
			}
		}

		return allPassed;
	}

	bool testEigenvalueSign()
	{
		std::cout << "\n=== Test 2: Eigenvalue Signs (Dissipative Operator) ===" << std::endl;

		const double L = 0.1;     // 10 cm column
		const double v = 0.001;   // 1 mm/s velocity
		const double D = 1e-6;    // 1e-6 m²/s dispersion
		const unsigned int nPoints = 32;
		const unsigned int nModes = 16;

		DanckwertsSpectralPreconditioner precond;
		precond.initialize(nPoints, L, v, D, nModes);

		bool allNegative = true;
		for (unsigned int k = 0; k < nModes; ++k)
		{
			const double lambda_k = precond._eigenvalues[k];
			std::cout << "λ_" << (k+1) << " = " << lambda_k << std::endl;

			if (lambda_k >= 0.0)
			{
				std::cerr << "ERROR: Eigenvalue " << k << " is non-negative: "
				          << lambda_k << std::endl;
				allNegative = false;
			}
		}

		if (allNegative)
			std::cout << "✓ All eigenvalues are negative (dissipative)" << std::endl;

		return allNegative;
	}

	bool testPreconditionerApplication()
	{
		std::cout << "\n=== Test 3: Preconditioner Application ===" << std::endl;

		const double L = 0.1;
		const double v = 0.001;
		const double D = 1e-6;
		const double dt = 0.1;
		const unsigned int nPoints = 32;

		DanckwertsSpectralPreconditioner precond;
		precond.initialize(nPoints, L, v, D, nPoints);

		// Create a simple test residual (smooth function)
		std::vector<double> residual(nPoints);
		std::vector<double> solution(nPoints);

		const double dx = L / static_cast<double>(nPoints - 1);
		for (unsigned int i = 0; i < nPoints; ++i)
		{
			const double x = i * dx;
			residual[i] = std::sin(2.0 * PI * x / L);
		}

		// Apply preconditioner
		bool success = precond.apply(dt, residual.data(), solution.data());

		if (!success)
		{
			std::cerr << "ERROR: Preconditioner application failed" << std::endl;
			return false;
		}

		// Check that solution is non-zero
		double norm = 0.0;
		for (unsigned int i = 0; i < nPoints; ++i)
		{
			norm += solution[i] * solution[i];
		}
		norm = std::sqrt(norm / nPoints);

		std::cout << "Input residual L2 norm: " << std::sqrt(std::inner_product(
			residual.begin(), residual.end(), residual.begin(), 0.0) / nPoints) << std::endl;
		std::cout << "Output solution L2 norm: " << norm << std::endl;

		if (norm < 1e-12)
		{
			std::cerr << "ERROR: Solution is essentially zero" << std::endl;
			return false;
		}

		std::cout << "✓ Preconditioner applied successfully" << std::endl;
		return true;
	}

	bool testOrthogonality()
	{
		std::cout << "\n=== Test 4: Eigenvector Orthogonality (Weighted) ===" << std::endl;

		const double L = 0.1;
		const double v = 0.001;
		const double D = 1e-6;
		const double Pe = v * L / D;
		const unsigned int nPoints = 64;
		const unsigned int nModes = 8;

		DanckwertsSpectralPreconditioner precond;
		precond.initialize(nPoints, L, v, D, nModes);

		// Check weighted orthogonality: ⟨φᵢ, φⱼ⟩_w = ∫ φᵢ(z)·φⱼ(z)·exp(-Pe·z/L) dz
		const double dx = L / static_cast<double>(nPoints - 1);

		double maxOffDiag = 0.0;
		for (unsigned int i = 0; i < std::min(nModes, 4u); ++i)
		{
			for (unsigned int j = i; j < std::min(nModes, 4u); ++j)
			{
				double innerProduct = 0.0;
				for (unsigned int k = 0; k < nPoints; ++k)
				{
					const double x = k * dx;
					const double xi = x / L;
					const double weight = std::exp(-Pe * xi);
					const double phi_i = precond._eigenvectors.native(k, i);
					const double phi_j = precond._eigenvectors.native(k, j);

					// Trapezoidal rule
					double trapWeight = 1.0;
					if (k == 0 || k == nPoints - 1)
						trapWeight = 0.5;

					innerProduct += trapWeight * phi_i * phi_j * weight * dx;
				}

				if (i == j)
				{
					std::cout << "⟨φ_" << i << ", φ_" << j << "⟩_w = "
					          << innerProduct << " (should be ~1)" << std::endl;
				}
				else
				{
					std::cout << "⟨φ_" << i << ", φ_" << j << "⟩_w = "
					          << innerProduct << " (should be ~0)" << std::endl;
					maxOffDiag = std::max(maxOffDiag, std::abs(innerProduct));
				}
			}
		}

		std::cout << "Max off-diagonal inner product: " << maxOffDiag << std::endl;

		if (maxOffDiag > 0.1)
		{
			std::cerr << "WARNING: Eigenvectors may not be well orthogonal" << std::endl;
			return false;
		}

		std::cout << "✓ Eigenvectors show good weighted orthogonality" << std::endl;
		return true;
	}
}

int main(int argc, char** argv)
{
	std::cout << "========================================" << std::endl;
	std::cout << "Danckwerts Spectral Preconditioner Test" << std::endl;
	std::cout << "========================================" << std::endl;

	int failCount = 0;

	if (!testTranscendentalRoots())
		++failCount;

	if (!testEigenvalueSign())
		++failCount;

	if (!testPreconditionerApplication())
		++failCount;

	if (!testOrthogonality())
		++failCount;

	std::cout << "\n========================================" << std::endl;
	if (failCount == 0)
	{
		std::cout << "✓ All tests PASSED" << std::endl;
		std::cout << "========================================" << std::endl;
		return 0;
	}
	else
	{
		std::cout << "✗ " << failCount << " test(s) FAILED" << std::endl;
		std::cout << "========================================" << std::endl;
		return 1;
	}
}
