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
 * Defines a spectral preconditioner for the 1D convection-diffusion operator
 * with Danckwerts boundary conditions using precomputed eigendecomposition
 */

#ifndef LIBCADET_DANCKWERTSSPECTRAL_PRECONDITIONER_HPP_
#define LIBCADET_DANCKWERTSSPECTRAL_PRECONDITIONER_HPP_

#include "linalg/DenseMatrix.hpp"

#include <vector>
#include <cmath>

namespace cadet
{

namespace linalg
{

/**
 * @brief Spectral preconditioner for 1D convection-diffusion with Danckwerts BCs
 * @details This preconditioner uses the analytical eigendecomposition of the
 *          convection-diffusion operator with Danckwerts (Robin inlet, Neumann outlet)
 *          boundary conditions. The eigenvalues satisfy:
 *
 *          λ_k = -v²/(4D) - D·β_k²/L²
 *
 *          where β_k are roots of the transcendental equation:
 *
 *          tan(β_k) = -4·Pe·β_k / (3·Pe² + 4·β_k²)
 *
 *          The preconditioner approximates M⁻¹ ≈ Φ·diag(1/(1 - dt·λ_k))·Φᵀ
 *          where Φ is the matrix of eigenvectors.
 *
 *          See DANCKWERTS_EIGENVALUES_DERIVATION.md for complete mathematical derivation.
 */
class DanckwertsSpectralPreconditioner
{
public:

	DanckwertsSpectralPreconditioner() CADET_NOEXCEPT;
	~DanckwertsSpectralPreconditioner() CADET_NOEXCEPT;

	/**
	 * @brief Initializes the preconditioner by computing eigendecomposition
	 * @details Solves the transcendental equation for β_k, computes eigenvalues,
	 *          and assembles the eigenvector matrix on the given grid.
	 *
	 * @param [in] nPoints Number of grid points
	 * @param [in] colLength Column length L
	 * @param [in] velocity Interstitial velocity v
	 * @param [in] dispersion Axial dispersion coefficient D
	 * @param [in] nModes Number of spectral modes to use (default: min(nPoints, 32))
	 */
	void initialize(unsigned int nPoints, double colLength, double velocity, double dispersion, unsigned int nModes = 0);

	/**
	 * @brief Applies the preconditioner to a residual vector
	 * @details Computes z = M⁻¹·r where M is the approximation to the linearized operator.
	 *
	 * @param [in] timestep Time step dt for the backward Euler operator (I - dt·L)
	 * @param [in] residual Input residual vector r
	 * @param [out] solution Output vector z = M⁻¹·r
	 * @return True if successful, false otherwise
	 */
	bool apply(double timestep, double const* residual, double* solution);

	/**
	 * @brief Updates the preconditioner for new physical parameters
	 * @details Recomputes eigenvalues and eigenvectors without reallocating memory.
	 *
	 * @param [in] velocity New interstitial velocity v
	 * @param [in] dispersion New axial dispersion coefficient D
	 */
	void update(double velocity, double dispersion);

	/**
	 * @brief Returns the number of spectral modes used
	 * @return Number of modes
	 */
	inline unsigned int numModes() const CADET_NOEXCEPT { return _nModes; }

	/**
	 * @brief Returns the Peclet number Pe = vL/D
	 * @return Peclet number
	 */
	inline double pecletNumber() const CADET_NOEXCEPT { return _peclet; }

	/**
	 * @brief Returns whether the preconditioner has been initialized
	 * @return True if initialized, false otherwise
	 */
	inline bool isInitialized() const CADET_NOEXCEPT { return _initialized; }

protected:

	/**
	 * @brief Solves the transcendental equation for the k-th eigenvalue
	 * @details Uses Newton-Raphson iteration to find β_k satisfying:
	 *          tan(β_k) + 4·Pe·β_k / (3·Pe² + 4·β_k²) = 0
	 *
	 * @param [in] k Mode index (1-based)
	 * @param [in] Pe Peclet number
	 * @return β_k value
	 */
	double findBetaK(unsigned int k, double Pe) const;

	/**
	 * @brief Computes the dimensional eigenvalue from β_k
	 * @details λ_k = -v²/(4D) - D·β_k²/L²
	 *
	 * @param [in] betaK Value of β_k
	 * @return Eigenvalue λ_k
	 */
	double computeEigenvalue(double betaK) const;

	/**
	 * @brief Assembles the eigenvector matrix Φ
	 * @details The k-th eigenvector is:
	 *          φ_k(z) = N_k · exp(Pe·ξ/2) · [cos(β_k·ξ) - (3·Pe)/(2·β_k)·sin(β_k·ξ)]
	 *          where ξ = z/L and N_k is a normalization constant.
	 */
	void assembleEigenvectors();

	// Grid and physical parameters
	unsigned int _nPoints;     //!< Number of grid points
	unsigned int _nModes;      //!< Number of spectral modes
	double _colLength;         //!< Column length L
	double _velocity;          //!< Interstitial velocity v
	double _dispersion;        //!< Axial dispersion coefficient D
	double _peclet;            //!< Peclet number Pe = vL/D
	bool _initialized;         //!< Initialization flag

	// Spectral decomposition
	std::vector<double> _eigenvalues;   //!< Eigenvalues λ_k (size: nModes)
	std::vector<double> _betaValues;    //!< Transcendental roots β_k (size: nModes)
	DenseMatrix _eigenvectors;          //!< Eigenvector matrix Φ (nPoints × nModes)
	DenseMatrix _eigenvectorsT;         //!< Transposed eigenvector matrix Φᵀ (nModes × nPoints)

	// Weighted orthonormalization
	std::vector<double> _sqrtWeights;      //!< Square root of weights √w_i (size: nPoints)
	std::vector<double> _invSqrtWeights;   //!< Inverse square root of weights 1/√w_i (size: nPoints)

	// Workspace for apply()
	std::vector<double> _workspaceAlpha;    //!< Spectral coefficients α = Φᵀ·r (size: nModes)
	std::vector<double> _workspaceBeta;     //!< Scaled coefficients β = diag(...)·α (size: nModes)
	std::vector<double> _workspaceWeighted; //!< Weighted residual buffer (size: nPoints)
};

} // namespace linalg

} // namespace cadet

#endif  // LIBCADET_DANCKWERTSSPECTRAL_PRECONDITIONER_HPP_
