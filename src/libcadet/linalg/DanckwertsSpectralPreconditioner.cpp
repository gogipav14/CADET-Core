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

#include "linalg/DanckwertsSpectralPreconditioner.hpp"
#include "cadet/Exceptions.hpp"

#include <cmath>
#include <algorithm>
#include <iostream>
#include <limits>

namespace cadet
{

namespace linalg
{

namespace
{
	// Constants for Newton-Raphson solver
	const double NEWTON_TOL = 1e-12;
	const unsigned int NEWTON_MAX_ITER = 100;
	const double PI = 3.14159265358979323846;
}

DanckwertsSpectralPreconditioner::DanckwertsSpectralPreconditioner() CADET_NOEXCEPT :
	_nPoints(0), _nModes(0), _colLength(0.0), _velocity(0.0), _dispersion(0.0),
	_peclet(0.0), _initialized(false)
{
}

DanckwertsSpectralPreconditioner::~DanckwertsSpectralPreconditioner() CADET_NOEXCEPT
{
}

void DanckwertsSpectralPreconditioner::initialize(unsigned int nPoints, double colLength,
	double velocity, double dispersion, unsigned int nModes)
{
	if (nPoints == 0)
		throw InvalidParameterException("Number of grid points must be positive");
	if (colLength <= 0.0)
		throw InvalidParameterException("Column length must be positive");
	if (dispersion <= 0.0)
		throw InvalidParameterException("Dispersion coefficient must be positive");

	_nPoints = nPoints;
	_colLength = colLength;
	_velocity = velocity;
	_dispersion = dispersion;
	_peclet = (velocity * colLength) / dispersion;

	// Default: use min(nPoints, 32) modes for efficiency
	if (nModes == 0)
		_nModes = std::min(nPoints, 32u);
	else
		_nModes = std::min(nModes, nPoints);

	// Allocate storage
	_eigenvalues.resize(_nModes);
	_betaValues.resize(_nModes);
	_eigenvectors.resize(_nPoints, _nModes);
	_eigenvectorsT.resize(_nModes, _nPoints);
	_sqrtWeights.resize(_nPoints);
	_invSqrtWeights.resize(_nPoints);
	_workspaceAlpha.resize(_nModes);
	_workspaceBeta.resize(_nModes);
	_workspaceWeighted.resize(_nPoints);

	// Compute spectral decomposition
	update(velocity, dispersion);

	_initialized = true;
}

void DanckwertsSpectralPreconditioner::update(double velocity, double dispersion)
{
	_velocity = velocity;
	_dispersion = dispersion;
	_peclet = (_velocity * _colLength) / _dispersion;

	// Compute transcendental roots β_k and eigenvalues λ_k
	for (unsigned int k = 0; k < _nModes; ++k)
	{
		_betaValues[k] = findBetaK(k + 1, _peclet);  // k+1 because modes are 1-indexed
		_eigenvalues[k] = computeEigenvalue(_betaValues[k]);
	}

	// Assemble eigenvector matrices
	assembleEigenvectors();

}

double DanckwertsSpectralPreconditioner::findBetaK(unsigned int k, double Pe) const
{
	// Initial guess: β_k ≈ k·π for large k, but needs correction for small k and large Pe
	double beta0;
	if (k == 1 && Pe > 10.0)
	{
		// For first mode at high Pe, use asymptotic estimate
		beta0 = std::sqrt(0.75) * Pe;
	}
	else
	{
		// Standard approach: roots lie between (k-1)·π and k·π
		beta0 = (k - 0.5) * PI;
	}

	// Newton-Raphson iteration to solve:
	// f(β) = tan(β) + 4·Pe·β / (3·Pe² + 4·β²) = 0
	double beta = beta0;
	for (unsigned int iter = 0; iter < NEWTON_MAX_ITER; ++iter)
	{
		// Avoid singularities at β = π/2, 3π/2, ...
		double cosB = std::cos(beta);
		if (std::abs(cosB) < 1e-10)
		{
			// Near singularity, shift slightly
			beta += 0.01;
			cosB = std::cos(beta);
		}

		const double sinB = std::sin(beta);
		const double tanB = sinB / cosB;
		const double beta2 = beta * beta;
		const double Pe2 = Pe * Pe;

		// f(β) = tan(β) + 4·Pe·β / (3·Pe² + 4·β²)
		const double denom = 3.0 * Pe2 + 4.0 * beta2;
		const double f = tanB + (4.0 * Pe * beta) / denom;

		// f'(β) = sec²(β) + 4·Pe·(3·Pe² - 4·β²) / (3·Pe² + 4·β²)²
		const double secB2 = 1.0 / (cosB * cosB);
		const double numerator = 3.0 * Pe2 - 4.0 * beta2;
		const double df = secB2 + (4.0 * Pe * numerator) / (denom * denom);

		// Newton step
		const double deltaBeta = -f / df;
		beta += deltaBeta;

		// Convergence check
		if (std::abs(deltaBeta) < NEWTON_TOL * std::abs(beta))
			break;

		// Ensure beta stays in valid range [(k-1)·π, k·π]
		const double betaMin = (k - 1) * PI + 0.01;
		const double betaMax = k * PI - 0.01;
		beta = std::max(betaMin, std::min(beta, betaMax));
	}

	return beta;
}

double DanckwertsSpectralPreconditioner::computeEigenvalue(double betaK) const
{
	// λ_k = -v²/(4D) - D·β_k²/L²
	const double term1 = -(_velocity * _velocity) / (4.0 * _dispersion);
	const double term2 = -_dispersion * (betaK * betaK) / (_colLength * _colLength);
	return term1 + term2;
}

void DanckwertsSpectralPreconditioner::assembleEigenvectors()
{
	// Eigenfunctions: φ_k(z) = N_k · exp(Pe·ξ/2) · [cos(β_k·ξ) - c_k·sin(β_k·ξ)]
	// where ξ = z/L, c_k = 3·Pe/(2·β_k), and N_k is normalization constant

	const double dz = _colLength / static_cast<double>(_nPoints - 1);

	// Step 1: Compute weight vectors w_i = exp(-Pe·z_i/L)
	for (unsigned int i = 0; i < _nPoints; ++i)
	{
		const double z = i * dz;
		const double xi = z / _colLength;
		const double weight = std::exp(-_peclet * xi);
		_sqrtWeights[i] = std::sqrt(weight);
		_invSqrtWeights[i] = 1.0 / _sqrtWeights[i];
	}

	// Step 2: Compute raw eigenvectors Φ (unnormalized)
	for (unsigned int k = 0; k < _nModes; ++k)
	{
		const double betaK = _betaValues[k];
		const double cK = (3.0 * _peclet) / (2.0 * betaK);

		for (unsigned int i = 0; i < _nPoints; ++i)
		{
			const double z = i * dz;
			const double xi = z / _colLength;
			const double expTerm = std::exp(0.5 * _peclet * xi);
			const double cosTerm = std::cos(betaK * xi);
			const double sinTerm = std::sin(betaK * xi);

			_eigenvectors.native(i, k) = expTerm * (cosTerm - cK * sinTerm);
		}
	}

	// Step 3: Apply weighted QR factorization
	// Form weighted matrix: Φ̃ = diag(√w) * Φ
	for (unsigned int k = 0; k < _nModes; ++k)
	{
		for (unsigned int i = 0; i < _nPoints; ++i)
		{
			_eigenvectors.native(i, k) *= _sqrtWeights[i];
		}
	}

	// Step 4: QR factorization using LAPACK dgeqrf
	// Φ̃ = Q * R
	std::vector<double> tau(_nModes);  // Householder reflector coefficients
	std::vector<double> work(1);
	lapackInt_t m = static_cast<lapackInt_t>(_nPoints);
	lapackInt_t n = static_cast<lapackInt_t>(_nModes);
	lapackInt_t lwork = -1;
	lapackInt_t info = 0;

	// Query optimal workspace size
	LapackFactorQRDense(&m, &n, _eigenvectors.data(), &m, tau.data(), work.data(), &lwork, &info);

	if (info == 0)
	{
		lwork = static_cast<lapackInt_t>(work[0]);
		work.resize(lwork);

		// Perform QR factorization
		LapackFactorQRDense(&m, &n, _eigenvectors.data(), &m, tau.data(), work.data(), &lwork, &info);
	}

	if (info != 0)
	{
		std::cerr << "[Danckwerts Spectral] QR factorization failed with info = " << info << std::endl;
		return;
	}

	// Step 5: Generate explicit Q matrix using LAPACK dorgqr
	lwork = -1;
	lapackInt_t k = n;  // Number of reflectors

	// Query optimal workspace size
	LapackGenerateQFromQR(&m, &n, &k, _eigenvectors.data(), &m, tau.data(), work.data(), &lwork, &info);

	if (info == 0)
	{
		lwork = static_cast<lapackInt_t>(work[0]);
		work.resize(lwork);

		// Generate Q matrix (overwrites _eigenvectors)
		LapackGenerateQFromQR(&m, &n, &k, _eigenvectors.data(), &m, tau.data(), work.data(), &lwork, &info);
	}

	if (info != 0)
	{
		std::cerr << "[Danckwerts Spectral] Q generation failed with info = " << info << std::endl;
		return;
	}

	// Step 6: Compute transpose Q^T for efficient application
	for (unsigned int i = 0; i < _nPoints; ++i)
	{
		for (unsigned int k = 0; k < _nModes; ++k)
		{
			_eigenvectorsT.native(k, i) = _eigenvectors.native(i, k);
		}
	}

}

bool DanckwertsSpectralPreconditioner::apply(double timestep, double const* residual, double* solution)
{
	if (!_initialized)
	{
		std::cerr << "[Danckwerts Spectral] Error: Preconditioner not initialized" << std::endl;
		return false;
	}

	// Step 1: Apply weight: r̃ = diag(√w) * r
	for (unsigned int i = 0; i < _nPoints; ++i)
	{
		_workspaceWeighted[i] = _sqrtWeights[i] * residual[i];
	}

	// Step 2: Project onto orthonormal basis: α = Q^T * r̃
	_eigenvectorsT.multiplyVector(_workspaceWeighted.data(), _workspaceAlpha.data());

	// Step 3: Scale by diagonal eigenvalue operator: β_k = α_k / (1 - dt·λ_k)
	for (unsigned int k = 0; k < _nModes; ++k)
	{
		const double scaling = 1.0 / (1.0 - timestep * _eigenvalues[k]);
		_workspaceBeta[k] = _workspaceAlpha[k] * scaling;
	}

	// Step 4: Transform back to weighted space: z̃ = Q * β
	_eigenvectors.multiplyVector(_workspaceBeta.data(), _workspaceWeighted.data());

	// Step 5: Remove weight: z = diag(1/√w) * z̃
	for (unsigned int i = 0; i < _nPoints; ++i)
	{
		solution[i] = _invSqrtWeights[i] * _workspaceWeighted[i];
	}

	return true;
}

} // namespace linalg

} // namespace cadet
