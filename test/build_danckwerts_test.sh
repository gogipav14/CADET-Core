#!/bin/bash
# Simple build script for the Danckwerts preconditioner test

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CADET_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Building Danckwerts Spectral Preconditioner Test"
echo "CADET Root: $CADET_ROOT"

# Create a temporary build directory
BUILD_DIR="$SCRIPT_DIR/build_danckwerts_test"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Compile the test
echo "Compiling test..."
g++ -std=c++11 \
    -I"$CADET_ROOT/include" \
    -I"$CADET_ROOT/src/libcadet" \
    -I"$CADET_ROOT/build/cadet" \
    -o test_danckwerts_preconditioner \
    "$SCRIPT_DIR/test_danckwerts_preconditioner.cpp" \
    "$CADET_ROOT/src/libcadet/linalg/DanckwertsSpectralPreconditioner.cpp" \
    "$CADET_ROOT/src/libcadet/linalg/DenseMatrix.cpp" \
    -llapack -lblas -lm

echo "Build complete. Executable: $BUILD_DIR/test_danckwerts_preconditioner"
echo ""
echo "Running test..."
./test_danckwerts_preconditioner
